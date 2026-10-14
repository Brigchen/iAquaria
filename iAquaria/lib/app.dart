/// 全局应用状态（轻量 ChangeNotifier，避免引入额外状态库）：
/// - 缸列表与当前活动缸（多缸切换）
/// - 最新遥测快照（来自 WebSocket 直连设备流）
/// - 告警横幅事件
library;

import 'dart:async';
import 'dart:convert';

import 'package:flutter/foundation.dart';

import '../models/bio.dart';
import '../models/records.dart';
import '../models/telemetry.dart';
import '../models/tank.dart';
import '../services/alert_engine.dart';
import '../services/device_service.dart';
import '../services/local_data_service.dart';
import '../services/storage_service.dart';

class AppStore extends ChangeNotifier {
  AppStore._();
  static final AppStore instance = AppStore._();

  final StorageService st = StorageService.instance;

  List<Tank> tanks = [];
  Tank? activeTank;
  Telemetry telemetry = Telemetry.empty;

  /// 设备直连状态："connecting" / "connected" / "disconnected" / "error"
  /// / "cloud" / "cloud-connecting" / "cloud-error" / "cloud-nodata" / "manual"
  String linkState = 'disconnected';

  /// 是否处于云端链路（连接中 / 已连接 / 云连接失败重试中均算，
  /// 此时局域网摄像头不可达、设备控制只读）。
  /// cloud-error / cloud-nodata 可能带详情后缀：<state>|<原因>
  bool get isCloudLink =>
      linkState == 'cloud' ||
      linkState == 'cloud-connecting' ||
      linkState.startsWith('cloud-error') ||
      linkState.startsWith('cloud-nodata');

  /// 云端最新照片（ESP32-CAM 定时上传，云端查看模式显示）
  Uint8List? cloudPhoto;
  DateTime? cloudPhotoAt;
  AlertEvent? lastAlert;

  /// 底部 Tab 跳转请求（跨页导航：提醒横幅「去处理」→ 计划页等）。
  /// HomePage 在 builder 内同步此值到自身 _tab。
  int homeTab = 0;

  /// 数据版本号：云同步合并改写本地数据后自增并通知，
  /// 计划页据此重载完成统计（FutureBuilder 数据随通知自动重取）
  int dataVer = 0;

  /// 云同步合并改写本地数据后的统一通知入口（dataVer+1 并广播刷新）
  void notifyDataChanged() {
    dataVer++;
    notifyListeners();
  }

  /// 待处理任务 id（配合 homeTab=2：跳到计划页后自动弹出该任务处理面板）
  String? pendingTaskId;

  /// 请求跳到计划页并处理指定任务（提醒横幅「去处理」入口）
  void requestTask(String taskId) {
    pendingTaskId = taskId;
    homeTab = 2; // 底部 Tab：0 概览 / 1 日志 / 2 计划 / 3 鱼缸
    notifyListeners();
  }

  /// 当前缸生物清单（AI 识别回写 + 手动修正，持久化）
  List<BioSpecies> bio = [];

  /// 当前缸本机最近一次参数值（自动+人工测量同源），
  /// 无实时链路（人工缸/断连）时指标卡回退显示
  Map<String, double> localLatest = const {};

  /// 当前缸 AI 分析记录（最新在前，持久化）
  List<AnalysisRecord> analysis = [];

  StreamSubscription? _telSub;
  StreamSubscription? _stateSub;
  StreamSubscription? _evtSub;
  StreamSubscription<Uint8List>? _photoSub;
  AlertEngine? _engine;

  /// 启动加载：读缸档案 → 恢复活动缸 → 直连设备
  Future<void> init() async {
    tanks = await st.tanks();
    final id = await st.activeTankId();
    activeTank =
        tanks.where((t) => t.id == id).firstOrNull ?? tanks.firstOrNull;
    notifyListeners();
    if (activeTank != null) {
      await _connect(activeTank!);
      // 首次运行预置默认告警规则（开箱即用，可改可关）
      final rules = await st.alertRules(activeTank!.id);
      if (rules.isEmpty) await _seedRules(activeTank!.id);
    }
  }

  Future<void> _seedRules(String tankId) async {
    final isSalt = activeTank?.waterType == Tank.waterSalt;
    final rules = <AlertRule>[
      AlertRule(
        id: 'r_temp',
        tankId: tankId,
        metric: 'temp',
        mode: AlertRule.modeRange,
        minVal: 24,
        maxVal: 28,
      ),
      AlertRule(
        id: 'r_ph',
        tankId: tankId,
        metric: 'ph',
        mode: AlertRule.modeRange,
        minVal: 6.4,
        maxVal: 7.6,
      ),
      AlertRule(
        id: 'r_tds1',
        tankId: tankId,
        metric: 'tds1',
        mode: AlertRule.modeBaseline,
        baseline: isSalt ? 33 : 250,
        pct: 30,
        silentFrom: '23:00',
        silentTo: '07:00',
      ),
      AlertRule(
        id: 'r_lvl',
        tankId: tankId,
        metric: 'lvl',
        mode: AlertRule.modeRange,
        minVal: 20,
        maxVal: 95,
      ),
    ];
    await st.saveAlertRules(rules);
  }

  Future<void> _connect(Tank tank) async {
    _telSub?.cancel();
    _stateSub?.cancel();
    _evtSub?.cancel();
    _photoSub?.cancel();
    cloudPhoto = null;
    cloudPhotoAt = null;
    // 生物清单与 AI 分析记录随缸切换加载（手动管理缸同样可用）
    bio = await st.bioOf(tank.id);
    analysis = await st.analysisOf(tank.id);
    // 本机最近参数值（指标卡在无实时链路时回退显示）
    localLatest = await LocalDataService.instance.latest(tank.id);
    notifyListeners();
    final dev = DeviceService.instance;
    final ip = tank.esp32Ip.trim();
    final topic = tank.cloudTopic.trim();
    // 纯人工缸：无设备 IP 也无云查看 ID，无任何数据源
    if (ip.isEmpty && topic.isEmpty) {
      await dev.disconnect();
      linkState = 'manual';
      notifyListeners();
      return;
    }
    _stateSub = dev.state.listen((s) {
      linkState = s;
      notifyListeners();
    });
    _telSub = dev.telemetry.listen((tel) {
      telemetry = tel;
      notifyListeners();
      // 局域网/云端遥测统一落本地（趋势/回退/导出共用），不阻塞 UI
      LocalDataService.instance
          .addAuto(tank.id, tel, dev.isCloudMode ? 'cloud' : 'lan');
      _evaluateAlerts(tel);
    });
    // 设备自动运行事件（CO2/加温/补水/灯光/喂食）→ 自动写入养护日志
    _evtSub = dev.events.listen((e) => _logActEvent(tank.id, e));
    // 云端照片（ESP32-CAM 定时上传，云端查看模式显示）
    _photoSub = dev.cloudPhoto.listen((jpeg) {
      cloudPhoto = jpeg;
      cloudPhotoAt = DateTime.now();
      notifyListeners();
    });
    if (ip.isEmpty) {
      // 无设备 IP 但配置了云查看 ID：直接云端订阅（只读查看）
      linkState = 'cloud-connecting';
      await dev.connectCloudOnly(topic);
      notifyListeners();
    } else {
      // 云查看主题非空时：局域网断开 8 秒后自动切云端订阅（只读）
      await dev.connect(ip, cloudTopic: topic);
    }
  }

  /// 更新当前缸生物清单（概览页生物面板编辑 / AI 识别回写），持久化并广播。
  /// 有实质修改时先把旧清单按时间点存入历史（可回看/恢复）。
  Future<void> updateBio(List<BioSpecies> list) async {
    final tank = activeTank;
    if (tank == null) return;
    // 内容有变化才记历史：旧清单快照 + 修改时间
    final oldJson = jsonEncode(BioSpecies.listToJson(bio));
    final newJson = jsonEncode(BioSpecies.listToJson(list));
    if (oldJson != newJson) {
      await st.pushBioHistory(tank.id, bio);
    }
    bio = list;
    notifyListeners();
    await st.saveBio(tank.id, list);
  }

  /// 人工水质测量落库：本地数据 + 养护日志（水质检测类型），指标卡回退值同步刷新
  Future<void> addManualMeasurement(
      String tankId, Map<String, double> vals, String note) async {
    final data = LocalDataService.instance;
    await data.addManual(tankId, vals);
    await st.addJournal(JournalEntry(
      id: 'man_${DateTime.now().millisecondsSinceEpoch}',
      tankId: tankId,
      type: JournalEntry.typeWater,
      note: note.isEmpty ? '人工水质检测' : note,
      ts: DateTime.now(),
    ));
    localLatest = await data.latest(tankId);
    notifyListeners();
  }

  /// 追加一条 AI 分析记录（最新在前），持久化并广播
  Future<void> addAnalysisRecord(AnalysisRecord rec) async {
    analysis = [rec, ...analysis];
    if (analysis.length > 200) analysis.removeRange(200, analysis.length);
    notifyListeners();
    final tank = activeTank;
    if (tank != null) await st.addAnalysis(tank.id, rec);
  }

  Future<void> _logActEvent(String tankId, ActEvent e) async {
    // 喂食归入「喂食」，其余执行器动作归入「设备」类型
    final type =
        e.ch == 'feed' ? JournalEntry.typeFeed : JournalEntry.typeDevice;
    await st.addJournal(JournalEntry(
      id: 'evt_${e.ts.millisecondsSinceEpoch}_${e.ch}',
      tankId: tankId,
      type: type,
      note: e.desc,
      ts: e.ts,
      auto: true,
    ));
    notifyListeners();
  }

  Future<void> _evaluateAlerts(Telemetry tel) async {
    if (activeTank == null) return;
    final rules = await st.alertRules(activeTank!.id);
    _engine = AlertEngine(rules);
    final fired = _engine!.evaluate(tel);
    if (fired.isNotEmpty) {
      lastAlert = fired.last;
      // 告警自动写入养护日志
      await st.addJournal(JournalEntry(
        id: 'alert_${fired.last.ts.millisecondsSinceEpoch}',
        tankId: activeTank!.id,
        type: JournalEntry.typeOther,
        note: '自动告警：${fired.last.message}',
        ts: fired.last.ts,
        auto: true,
      ));
      notifyListeners();
    }
  }

  /// 切换活动缸：重连对应设备，遥测流自动随缸切换
  Future<void> switchTank(Tank tank) async {
    activeTank = tank;
    telemetry = Telemetry.empty;
    lastAlert = null;
    await st.setActiveTankId(tank.id);
    notifyListeners();
    await _connect(tank);
  }

  Future<void> addTank(Tank tank) async {
    tanks = [...tanks, tank];
    try {
      await st.saveTanks(tanks);
    } catch (_) {
      // 持久化失败也要回滚内存，避免“下拉有缸但重启全丢/概览不同步”
      tanks = tanks.where((t) => t.id != tank.id).toList();
      rethrow;
    }
    await switchTank(tank);
  }

  /// 编辑鱼缸档案（名称/IP/摄像头/云主题等），保存后若是活动缸则重连设备
  Future<void> updateTank(Tank updated) async {
    tanks = [for (final t in tanks) t.id == updated.id ? updated : t];
    await st.saveTanks(tanks);
    if (activeTank?.id == updated.id) {
      activeTank = updated;
      notifyListeners();
      await _connect(updated); // IP/云主题可能已改，重连
    } else {
      notifyListeners();
    }
  }

  /// 删除鱼缸：持久化后切换到剩余第一缸（无缸则回到未添加状态）
  Future<void> deleteTank(Tank tank) async {
    tanks = tanks.where((t) => t.id != tank.id).toList();
    await st.saveTanks(tanks);
    if (activeTank?.id == tank.id) {
      activeTank = tanks.isEmpty ? null : tanks.first;
      telemetry = Telemetry.empty;
      lastAlert = null;
      if (activeTank != null) {
        await st.setActiveTankId(activeTank!.id);
      } else {
        await st.clearActiveTankId();
      }
      notifyListeners();
      if (activeTank != null) {
        await _connect(activeTank!);
      } else {
        await DeviceService.instance.disconnect();
      }
    } else {
      notifyListeners();
    }
  }

  /// 序列化导出（备份用）
  Future<String> exportAll() async => jsonEncode({
        'tanks': tanks.map((t) => t.toJson()).toList(),
        'activeTankId': activeTank?.id,
      });
}

extension _FirstOrNull<T> on Iterable<T> {
  T? get firstOrNull => isEmpty ? null : first;
}
