/// 设备遥测快照模型（对应设备 WS/MQTT tel 帧字段，协议键不变）。
class Telemetry {
  const Telemetry({
    this.temp,
    this.ph,
    this.tempPh,
    this.tds1,
    this.tds2,
    this.lux,
    this.level,
    this.ts,
    this.act = const [],
    this.man = const [],
  });

  final double? temp; // 水温 ℃（DS18B20）
  final double? ph; // pH
  final double? tempPh; // 水温(pH) ℃（pH 探头自带温度）
  final double? tds1; // 淡水: TDS(滤前) ppm / 海水: 盐度 ‰
  final double? tds2; // 淡水: TDS(滤后) ppm / 海水: 不显示
  final double? lux; // 光照 lx（GY-30）
  final double? level; // 水位 %
  final int? ts; // 时间戳（秒）

  /// 执行器开关状态，通道序与固件一致：[co2, feed, light, heater, pump]
  final List<bool> act;

  /// 执行器是否被手动接管（true=手动开/关生效中，false=自动策略）
  final List<bool> man;

  /// 通道名（与固件 chName 顺序一致，feed 不对外控制）
  static const kChannels = ['co2', 'feed', 'light', 'heater', 'pump'];

  /// 空快照（离线占位）
  static const Telemetry empty = Telemetry();

  static List<bool> _bools(dynamic v) => v is List
      ? v.map((e) => e == true || e == 1 || e == '1').toList()
      : const [];

  factory Telemetry.fromJson(Map<String, dynamic> j) => Telemetry(
        temp: (j['temp'] as num?)?.toDouble(),
        ph: (j['ph'] as num?)?.toDouble(),
        tempPh: (j['temp_ph'] as num?)?.toDouble(),
        tds1: (j['tds1'] as num?)?.toDouble(),
        tds2: (j['tds2'] as num?)?.toDouble(),
        lux: (j['lux'] as num?)?.toDouble(),
        level: (j['lvl'] as num?)?.toDouble(),
        ts: (j['ts'] as num?)?.toInt(),
        act: _bools(j['act']),
        man: _bools(j['man']),
      );

  bool get isEmpty =>
      temp == null &&
      ph == null &&
      tempPh == null &&
      tds1 == null &&
      tds2 == null &&
      lux == null &&
      level == null;
}
