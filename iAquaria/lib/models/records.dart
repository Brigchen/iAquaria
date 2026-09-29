/// 养护日志条目。
class JournalEntry {
  JournalEntry({
    required this.id,
    required this.tankId,
    required this.type,
    required this.note,
    required this.ts,
    this.auto = false,
  });

  static const String typeWater = '水质检测';
  static const String typeChange = '换水';
  static const String typeFeed = '喂食';
  static const String typeMaintain = '维护';
  static const String typeDevice = '设备';
  static const String typeOther = '其他';

  final String id;
  final String tankId;
  final String type; // 水质检测/换水/喂食/维护/设备/其他
  final String note;
  final DateTime ts;

  /// 是否自动生成（告警事件、设备投喂等）
  final bool auto;

  Map<String, dynamic> toJson() => {
        'id': id,
        'tankId': tankId,
        'type': type,
        'note': note,
        'ts': ts.toIso8601String(),
        'auto': auto,
      };

  factory JournalEntry.fromJson(Map<String, dynamic> j) => JournalEntry(
        id: j['id'] as String,
        tankId: (j['tankId'] as String?) ?? '',
        type: (j['type'] as String?) ?? typeOther,
        note: (j['note'] as String?) ?? '',
        ts: DateTime.tryParse((j['ts'] as String?) ?? '') ?? DateTime.now(),
        auto: (j['auto'] as bool?) ?? false,
      );
}

/// 周期养护任务。
class TaskEntity {
  TaskEntity({
    required this.id,
    required this.tankId,
    required this.title,
    required this.cycleDays,
    required this.nextDue,
    this.time,
    this.paused = false,
  });

  final String id;
  final String tankId;
  final String title; // 喂食/换水/滤材清洗/水质检测/设备保养
  final int cycleDays; // 周期天数
  final DateTime nextDue; // 下次到期
  final String? time; // 每日计划时刻 "HH:mm"（null=不限时刻，全天任务）
  final bool paused;

  bool get overdue => nextDue.isBefore(DateTime.now());

  Map<String, dynamic> toJson() => {
        'id': id,
        'tankId': tankId,
        'title': title,
        'cycleDays': cycleDays,
        'nextDue': nextDue.toIso8601String(),
        'time': time,
        'paused': paused,
      };

  factory TaskEntity.fromJson(Map<String, dynamic> j) => TaskEntity(
        id: j['id'] as String,
        tankId: (j['tankId'] as String?) ?? '',
        title: (j['title'] as String?) ?? '',
        cycleDays: (j['cycleDays'] as num?)?.toInt() ?? 7,
        nextDue: DateTime.tryParse((j['nextDue'] as String?) ?? '') ?? DateTime.now(),
        time: j['time'] as String?,
        paused: (j['paused'] as bool?) ?? false,
      );
}

/// 阈值告警规则（区间 / 基线±百分比 两种模式，均自定义）。
class AlertRule {
  AlertRule({
    required this.id,
    required this.tankId,
    required this.metric,
    required this.mode,
    this.minVal,
    this.maxVal,
    this.baseline,
    this.pct,
    this.holdN = 3,
    this.cooldownMin = 30,
    this.silentFrom,
    this.silentTo,
    this.enabled = true,
  });

  static const String modeRange = 'range'; // 固定区间
  static const String modeBaseline = 'baseline'; // 基线 ± pct%

  final String id;
  final String tankId;
  final String metric; // temp/ph/orp/tds1/tds2/lux/lvl
  final String mode;
  final double? minVal;
  final double? maxVal;
  final double? baseline;
  final double? pct;
  final int holdN; // 持续确认次数（去抖）
  final int cooldownMin; // 同规则冷却分钟
  final String? silentFrom; // 免打扰开始 HH:mm
  final String? silentTo; // 免打扰结束 HH:mm（早于开始按跨天）
  final bool enabled;

  Map<String, dynamic> toJson() => {
        'id': id,
        'tankId': tankId,
        'metric': metric,
        'mode': mode,
        'minVal': minVal,
        'maxVal': maxVal,
        'baseline': baseline,
        'pct': pct,
        'holdN': holdN,
        'cooldownMin': cooldownMin,
        'silentFrom': silentFrom,
        'silentTo': silentTo,
        'enabled': enabled,
      };

  factory AlertRule.fromJson(Map<String, dynamic> j) => AlertRule(
        id: j['id'] as String,
        tankId: (j['tankId'] as String?) ?? '',
        metric: (j['metric'] as String?) ?? 'temp',
        mode: (j['mode'] as String?) ?? modeRange,
        minVal: (j['minVal'] as num?)?.toDouble(),
        maxVal: (j['maxVal'] as num?)?.toDouble(),
        baseline: (j['baseline'] as num?)?.toDouble(),
        pct: (j['pct'] as num?)?.toDouble(),
        holdN: (j['holdN'] as num?)?.toInt() ?? 3,
        cooldownMin: (j['cooldownMin'] as num?)?.toInt() ?? 30,
        silentFrom: j['silentFrom'] as String?,
        silentTo: j['silentTo'] as String?,
        enabled: (j['enabled'] as bool?) ?? true,
      );
}
