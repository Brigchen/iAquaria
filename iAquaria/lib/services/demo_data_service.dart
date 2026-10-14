/// 演示数据服务（示意/截图用）：一键写入示例养护日志、周期计划、生物清单，
/// 并模拟遥测帧（10 秒一帧随机游走），让概览数据卡、计划提醒、告警在
/// 无真实设备/设备离线时也有完整的示意效果。
///
/// 行为约定：
/// - 各类数据仅在对应集合为空时播种（避免重复堆积）；
/// - 关闭开关只停止模拟遥测，已写入的记录保留——日志长按可删，
///   任务/生物可在页面内删除；
/// - 播种与遥测都走正式数据通道（StorageService / DeviceService.ingestTel），
///   与真实数据无差别，云同步开启时会照常同步。
library;

import 'dart:async';
import 'dart:math';

import '../app.dart';
import '../models/bio.dart';
import '../models/records.dart';
import 'device_service.dart';
import 'storage_service.dart';

class DemoDataService {
  DemoDataService._();
  static final DemoDataService instance = DemoDataService._();

  Timer? _telTimer;
  final Random _rnd = Random();
  double _temp = 25.6,
      _ph = 7.15,
      _tph = 25.5,
      _tds1 = 228,
      _tds2 = 138,
      _lux = 160,
      _lvl = 86;

  Future<bool> enabled() async =>
      (await StorageService.instance.getString('demo_mode')) == '1';

  Future<void> setEnabled(bool v) async {
    await StorageService.instance.setString('demo_mode', v ? '1' : '0');
    final tank = AppStore.instance.activeTank;
    if (v) {
      if (tank != null) await _seed(tank.id);
      _startTel();
    } else {
      _stopTel();
    }
  }

  /// App 启动恢复：若演示模式开着则恢复模拟遥测（不重复播种）
  Future<void> resume() async {
    if (await enabled()) _startTel();
  }

  // ───────────── 模拟遥测（随机游走，水族缸合理区间） ─────────────

  void _startTel() {
    _stopTel();
    _pushTel();
    _telTimer = Timer.periodic(const Duration(seconds: 10), (_) => _pushTel());
  }

  void _stopTel() {
    _telTimer?.cancel();
    _telTimer = null;
  }

  double _walk(double v, double step, double lo, double hi) =>
      (v + (_rnd.nextDouble() - 0.5) * 2 * step).clamp(lo, hi);

  void _pushTel() {
    _temp = _walk(_temp, 0.06, 25.2, 26.0);
    _ph = _walk(_ph, 0.03, 6.9, 7.4);
    _tph = _walk(_tph, 0.08, 24.5, 26.2);
    _tds1 = _walk(_tds1, 4, 210, 250);
    _tds2 = _walk(_tds2, 3, 120, 160);
    _lux = _walk(_lux, 30, 80, 420);
    _lvl = _walk(_lvl, 0.5, 78, 92);
    DeviceService.instance.ingestTel({
      'temp': double.parse(_temp.toStringAsFixed(2)),
      'ph': double.parse(_ph.toStringAsFixed(2)),
      'temp_ph': double.parse(_tph.toStringAsFixed(2)),
      'tds1': _tds1.round(),
      'tds2': _tds2.round(),
      'lux': _lux.round(),
      'lvl': double.parse(_lvl.toStringAsFixed(1)),
      'ts': DateTime.now().millisecondsSinceEpoch ~/ 1000,
      // 通道序与固件一致 [co2, feed, light, heater, pump]：白天 CO2/灯/泵开
      'act': [true, false, true, false, true],
      'man': [false, false, false, false, false],
    });
  }

  // ───────────── 播种示例数据（各集合为空才写） ─────────────

  Future<void> _seed(String tankId) async {
    final st = StorageService.instance;
    final now = DateTime.now();
    var changed = false;

    // 1) 养护日志：近 14 天约 16 条（类型/时间分布贴近真实使用）
    //    已有 demo 日志则跳过；有真实日志时追加（demo_ 前缀可识别、不覆盖）
    if (!(await st.journals(tankId)).any((e) => e.id.startsWith('demo_j_'))) {
      final notes = <(int, String, String, bool)>[
        (0, JournalEntry.typeFeed, '日常喂食，饲料适量，鱼群抢食正常', false),
        (0, JournalEntry.typeDevice, 'CO2 计泡约 1 泡/秒，灯光 10:00-20:00 定时', true),
        (
          1,
          JournalEntry.typeWater,
          '水质检测：pH 7.2 / 水温(pH) 25.4℃ / TDS 233ppm，稳定',
          false
        ),
        (2, JournalEntry.typeFeed, '日常喂食', false),
        (3, JournalEntry.typeChange, '换水约 1/4，困水 24h，等温缓慢注入', false),
        (4, JournalEntry.typeMaintain, '擦缸壁、修剪水草残叶', false),
        (5, JournalEntry.typeFeed, '日常喂食', false),
        (
          6,
          JournalEntry.typeWater,
          '水质检测：pH 7.1 / 水温(pH) 25.2℃ / TDS 228ppm',
          false
        ),
        (7, JournalEntry.typeFeed, '日常喂食，少量多次', false),
        (8, JournalEntry.typeDevice, '加热棒待机（水温 25.6℃ 未触发）', true),
        (9, JournalEntry.typeChange, '换水 1/5，清洗前置滤棉', false),
        (10, JournalEntry.typeFeed, '日常喂食', false),
        (11, JournalEntry.typeMaintain, '检查止逆阀与细化器，更换 CO2 细化片', false),
        (
          12,
          JournalEntry.typeWater,
          '水质检测：pH 7.3 / 水温(pH) 25.6℃ / TDS 236ppm',
          false
        ),
        (13, JournalEntry.typeFeed, '日常喂食', false),
        (14, JournalEntry.typeOther, '观察鱼只状态良好，无异常游动/白点', false),
      ];
      for (final it in notes) {
        final ts =
            now.subtract(Duration(days: it.$1, hours: 9 + _rnd.nextInt(9)));
        await st.addJournal(JournalEntry(
          id: 'demo_j_${ts.millisecondsSinceEpoch}',
          tankId: tankId,
          type: it.$2,
          note: it.$3,
          ts: ts,
          auto: it.$4,
        ));
      }
      changed = true;
    }

    // 2) 周期计划：含今日到期（喂食）与昨日逾期（换水）→ 触发提醒横幅/去处理
    //    已有 demo 任务则跳过；有真实任务时追加（demo_ 前缀可识别、不覆盖）
    final allTasks = await st.tasksAll();
    if (!allTasks.any((t) => t.tankId == tankId && t.id.startsWith('demo_t'))) {
      final today = DateTime(now.year, now.month, now.day);
      DateTime at(int dayOffset, int h, int m) =>
          today.add(Duration(days: dayOffset, hours: h, minutes: m));
      final ms = now.millisecondsSinceEpoch;
      await st.saveTasks([
        ...allTasks,
        TaskEntity(
            id: 'demo_t1',
            tankId: tankId,
            title: '喂食',
            cycleDays: 1,
            nextDue: at(0, 8, 30),
            time: '08:30',
            upd: ms), // 今日到期
        TaskEntity(
            id: 'demo_t2',
            tankId: tankId,
            title: '换水 1/4',
            cycleDays: 7,
            nextDue: at(-1, 20, 0),
            time: '20:00',
            upd: ms), // 已逾期 → 演示提醒/去处理
        TaskEntity(
            id: 'demo_t3',
            tankId: tankId,
            title: '水质检测',
            cycleDays: 3,
            nextDue: at(1, 19, 0),
            time: '19:00',
            upd: ms),
        TaskEntity(
            id: 'demo_t4',
            tankId: tankId,
            title: '滤材清洗',
            cycleDays: 30,
            nextDue: at(18, 15, 0),
            upd: ms),
      ]);
      changed = true;
    }

    // 3) 生物概览：4 条（含鱼类计数，概览卡显示 种类数/鱼只数）
    if ((await st.bioOf(tankId)).isEmpty) {
      final list = <BioSpecies>[
        BioSpecies(group: '鱼', name: '斑马鱼', count: 8),
        BioSpecies(group: '鱼', name: '樱桃灯', count: 6),
        BioSpecies(group: '甲壳', name: '黑壳虾', count: 12),
        BioSpecies(group: '水草', name: '金鱼藻', count: 5),
      ];
      await st.saveBio(tankId, list);
      AppStore.instance.bio = list;
      changed = true;
    }

    if (changed) AppStore.instance.notifyDataChanged();
  }
}
