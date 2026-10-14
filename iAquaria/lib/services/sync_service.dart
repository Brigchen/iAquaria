/// 日志与计划云同步服务：复用云查看的 MQTT Broker（EMQX Serverless），
/// 在多台手机/平板间双向同步「养护日志 + 周期计划」。
///
/// 协议：合并快照 + 墓碑（retain 消息，无服务器、无增量日志）
/// - 每端把本机数据打包发布到 iaquaria/sync/<tankId>/state（retained，QoS1）：
///   {"src":设备标识,"j":[日志≤300条],"t":[任务全量(含upd)],"dj":[日志墓碑],"dt":[任务墓碑]}
/// - 收到他端快照（src≠自己）按以下规则合并进本地：
///   · 日志：id 不在本机且不在墓碑 → 新增（不可变条目，无需版本比较）
///   · 任务：id 不在墓碑 → 本机无则新增；都有则 upd 新者胜
///   · 墓碑 dj/dt：合并进本机墓碑并删除对应本地条目（传播删除）
/// - 合并后本机数据有变化 → 防抖回发合并结果 → 全网收敛到同一份并集
///
/// 触发时机：云端链路建立（onCloudUp）订阅+交换一次；本机日志/任务写入
/// （StorageService 回调 markDirty）3 秒防抖回发。仅云端在线时同步，
/// 局域网直连不产生任何云端流量。
///
/// 约束：同步仅覆盖最新 300 条日志；墓碑上限 200 条（超出部分极旧删除
/// 可能被陈旧 retained 快照复活，家庭场景可接受）。
library;

import 'dart:async';
import 'dart:convert';

import 'package:flutter/foundation.dart';

import '../app.dart';
import '../models/records.dart';
import 'mqtt_cloud_service.dart';
import 'storage_service.dart';

class SyncService {
  SyncService._();
  static final SyncService instance = SyncService._();

  static const int _maxJournals = 300; // 快照携带的日志条数上限
  static const int _maxTombs = 200; // 墓碑保留上限

  String _tankId = ''; // 当前同步的缸（随活动缸）
  bool _awaitFirst = false; // 订阅后等 retained 快照（先收后发，防覆盖并集）
  Timer? _firstTimer;
  Timer? _debounce;
  Set<String> _tombJ = {}; // 日志删除墓碑（id）
  Set<String> _tombT = {}; // 任务删除墓碑（id）

  String _cid = ''; // 本机标识（快照 src；避免自己发布的快照再合并一遍）

  /// 本机设备标识：首次生成后持久化（多端不能相同）
  Future<String> cid() async {
    if (_cid.isNotEmpty) return _cid;
    final st = StorageService.instance;
    _cid = await st.getString('sync_cid') ?? '';
    if (_cid.isEmpty) {
      _cid = 'app-${DateTime.now().millisecondsSinceEpoch % 100000000}';
      await st.setString('sync_cid', _cid);
    }
    return _cid;
  }

  /// 云同步开关（默认开；设置页可关）
  Future<bool> enabled() async =>
      (await StorageService.instance.getString('sync_enabled')) != '0';

  Future<void> setEnabled(bool v) async {
    final st = StorageService.instance;
    await st.setString('sync_enabled', v ? '1' : '0');
    if (v) {
      await onCloudUp(); // 云端在线则立即订阅交换；不在线等下次云端建立
    } else {
      onCloudDown();
    }
  }

  // ───────────── 云端链路生命周期（MqttCloudService 回调） ─────────────

  /// 云端连上：开关开启且有活动缸时，订阅同步主题并交换快照。
  /// 先订阅等 retained（最多 4s），收到他端快照合并后再回发——
  /// 若直接先发本机子集，retained 会被子集覆盖造成他端丢数据。
  Future<void> onCloudUp() async {
    onCloudDown(); // 清理旧状态（重复连接安全）
    if (!await enabled()) return;
    final tank = AppStore.instance.activeTank;
    if (tank == null) return;
    _tankId = tank.id;
    await _loadTombs(tank.id);
    MqttCloudService.instance.subscribeSync('iaquaria/sync/${tank.id}/state');
    _awaitFirst = true;
    _firstTimer = Timer(const Duration(seconds: 4), () {
      // 未收到任何快照（首个使用本缸的设备）：直接发布本机数据
      if (_awaitFirst) {
        _awaitFirst = false;
        _publish();
      }
    });
  }

  /// 云端断开 / 停止同步
  void onCloudDown() {
    _firstTimer?.cancel();
    _firstTimer = null;
    _debounce?.cancel();
    _debounce = null;
    _awaitFirst = false;
    _tankId = '';
  }

  /// 收到同步快照（MqttCloudService._onMsg 路由）
  Future<void> onSnapshot(String tankId, Map<String, dynamic> j) async {
    if (!await enabled()) return;
    if (tankId != _tankId) return;
    final src = '${j['src'] ?? ''}';
    if (src == await cid()) return; // 自己发布的（或 retained 回放）

    _awaitFirst = false;
    _firstTimer?.cancel();
    var changed = false;

    // 1) 日志合并：按 id 并集，跳过墓碑
    try {
      final localAll = await StorageService.instance.journals(tankId);
      final ids = localAll.map((e) => e.id).toSet();
      final arr = (j['j'] as List?) ?? const [];
      for (final item in arr) {
        if (item is! Map) continue;
        final m = Map<String, dynamic>.from(item);
        final id = '${m['id'] ?? ''}';
        if (id.isEmpty || ids.contains(id) || _tombJ.contains(id)) continue;
        m['tankId'] = tankId; // 保险：快照里 tankId 与主题一致
        await StorageService.instance
            .addJournalSilent(JournalEntry.fromJson(m));
        ids.add(id);
        changed = true;
      }
    } catch (e) {
      debugPrint('[SYNC] 日志合并失败: $e');
    }

    // 2) 任务合并：upd 新者胜
    try {
      final localTasks = await StorageService.instance.tasksAll();
      final arr = (j['t'] as List?) ?? const [];
      for (final item in arr) {
        if (item is! Map) continue;
        final inc = TaskEntity.fromJson(Map<String, dynamic>.from(item));
        if (inc.id.isEmpty || _tombT.contains(inc.id)) continue;
        if (inc.tankId != tankId) continue;
        final idx = localTasks.indexWhere((t) => t.id == inc.id);
        if (idx < 0) {
          localTasks.add(inc);
          changed = true;
        } else if (inc.upd > localTasks[idx].upd) {
          localTasks[idx] = inc;
          changed = true;
        }
      }
      if (changed) await StorageService.instance.saveTasks(localTasks);
    } catch (e) {
      debugPrint('[SYNC] 任务合并失败: $e');
    }

    // 3) 墓碑合并：传播他端的删除
    try {
      final dj = ((j['dj'] as List?) ?? const []).map((e) => '$e').toSet();
      final dt = ((j['dt'] as List?) ?? const []).map((e) => '$e').toSet();
      final newJ = dj.difference(_tombJ);
      final newT = dt.difference(_tombT);
      if (newJ.isNotEmpty || newT.isNotEmpty) {
        _tombJ.addAll(newJ);
        _tombT.addAll(newT);
        await _saveTombs(tankId);
        if (newJ.isNotEmpty) {
          await StorageService.instance.removeJournalsByIds(tankId, newJ);
        }
        if (newT.isNotEmpty) {
          final remain = (await StorageService.instance.tasksAll())
              .where((t) => !newT.contains(t.id))
              .toList();
          await StorageService.instance.saveTasks(remain);
        }
        changed = true;
      }
    } catch (e) {
      debugPrint('[SYNC] 墓碑合并失败: $e');
    }

    if (!changed) return;
    // 回发合并结果（防抖，避免多端同时在线时乒乓；收敛后第二轮回发无变化即停）
    _schedulePublish(delay: const Duration(seconds: 2));
    // 刷新 UI（日志/计划页 FutureBuilder 随 store 通知重取数据）
    AppStore.instance.notifyDataChanged();
  }

  // ───────────── 本机变更入口（StorageService 回调） ─────────────

  /// 本机日志/任务有写入：防抖回发合并快照
  void markDirty(String tankId) {
    if (tankId.isEmpty || tankId != _tankId) return;
    _schedulePublish();
  }

  void _schedulePublish({Duration delay = const Duration(seconds: 3)}) {
    _debounce?.cancel();
    _debounce = Timer(delay, _publish);
  }

  /// 发布本机合并快照（retained）：日志最新 300 条 + 任务全量 + 墓碑
  Future<void> _publish() async {
    _debounce?.cancel();
    _debounce = null;
    final tankId = _tankId;
    if (tankId.isEmpty || !MqttCloudService.instance.active) return;
    if (!await enabled()) return;
    try {
      final st = StorageService.instance;
      final journals = await st.journals(tankId);
      final tasks =
          (await st.tasksAll()).where((t) => t.tankId == tankId).toList();
      final payload = jsonEncode({
        'src': await cid(),
        'ts': DateTime.now().millisecondsSinceEpoch,
        'j': journals.take(_maxJournals).map((e) => e.toJson()).toList(),
        't': tasks.map((t) => t.toJson()).toList(),
        'dj': _tombJ.take(_maxTombs).toList(),
        'dt': _tombT.take(_maxTombs).toList(),
      });
      MqttCloudService.instance
          .publishSync('iaquaria/sync/$tankId/state', payload, retain: true);
    } catch (e) {
      debugPrint('[SYNC] 快照发布失败: $e');
    }
  }

  // ───────────── 墓碑持久化（防重启后被 retained 快照复活） ─────────────

  Future<void> _loadTombs(String tankId) async {
    _tombJ = {};
    _tombT = {};
    try {
      final raw = await StorageService.instance.getString('sync_del_$tankId');
      if (raw == null || raw.isEmpty) return;
      final m = jsonDecode(raw) as Map;
      _tombJ = ((m['j'] as List?) ?? const []).map((e) => '$e').toSet();
      _tombT = ((m['t'] as List?) ?? const []).map((e) => '$e').toSet();
    } catch (_) {}
  }

  Future<void> _saveTombs(String tankId) async {
    await StorageService.instance.setString(
        'sync_del_$tankId',
        jsonEncode({
          'j': _tombJ.take(_maxTombs).toList(),
          't': _tombT.take(_maxTombs).toList(),
        }));
  }
}
