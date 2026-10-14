/// 指标显示映射（水型驱动）——与 Kotlin 版 Metrics 逻辑完全对齐：
/// - 淡水/草缸：tds1/tds2 显示为 TDS(滤前)/TDS(滤后)，单位 ppm
/// - 海水：485 滤前通道换装盐度探头，协议键仍为 tds1，显示为单个"盐度"，单位 ‰；
///   海水缸不显示 tds2
library;

class Metrics {
  Metrics._();

  static const String waterFresh = '淡水';
  static const String waterSalt = '海水';
  static const String waterPlanted = '草缸';

  static bool isSalt(String? waterType) => waterType == waterSalt;

  static String label(String metric, {String? waterType}) {
    switch (metric) {
      case 'tds1':
        return isSalt(waterType) ? '盐度' : 'TDS(滤前)';
      case 'tds2':
        return isSalt(waterType) ? '盐度(滤后)' : 'TDS(滤后)';
      case 'temp':
        return '水温';
      case 'ph':
        return 'pH';
      case 'temp_ph':
        return '水温(pH)';
      case 'lux':
        return '光照';
      case 'lvl':
        return '水位';
      default:
        return metric;
    }
  }

  static String unit(String metric, {String? waterType}) {
    switch (metric) {
      case 'temp':
        return '℃';
      case 'temp_ph':
        return '℃';
      case 'tds1':
      case 'tds2':
        return isSalt(waterType) ? '‰' : 'ppm';
      case 'lux':
        return 'lx';
      case 'lvl':
        return '%';
      default:
        return '';
    }
  }

  /// 全量协议指标键
  static const List<String> allKeys = [
    'temp',
    'ph',
    'temp_ph',
    'tds1',
    'tds2',
    'lux',
    'lvl'
  ];

  /// 当前水型下可显示/可配置的指标（海水缸只有单个盐度 = tds1，不含 tds2）
  static List<String> visibleKeys(String? waterType) =>
      isSalt(waterType) ? allKeys.where((k) => k != 'tds2').toList() : allKeys;

  /// 添加缸时的传感器配置提示
  static String sensorHint(String waterType) {
    if (waterType == waterSalt) {
      return '海水缸：485 滤前通道配置盐度探头，App 内显示为单个"盐度"，单位 ‰';
    }
    return '淡水/草缸：485 双通道配置 TDS 探头（滤前/滤后），单位 ppm';
  }
}
