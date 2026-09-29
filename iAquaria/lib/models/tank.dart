/// 鱼缸档案模型。
///
/// 数据链路：每个鱼缸对应一台 ESP32 主板，App 通过 WebSocket 直连
/// ws://<esp32Ip>/ws 获取遥测数据（无 MQTT Broker、无云服务器）。
class Tank {
  Tank({
    required this.id,
    required this.name,
    this.esp32Ip = '',
    this.location = '',
    this.capacityL = 0,
    this.waterType = Tank.waterFresh,
    this.camUrl = '',
    this.cloudTopic = '',
    this.archived = false,
    this.createdAt,
  });

  static const String waterFresh = '淡水';
  static const String waterSalt = '海水';
  static const String waterPlanted = '草缸';

  final String id;
  final String name;

  /// ESP32 主板 IP 地址（必填），App 直连 ws://<ip>/ws
  final String esp32Ip;

  final String location;
  final int capacityL;

  /// 水型：淡水 / 海水 / 草缸 —— 决定传感器显示（TDS 或 盐度）
  final String waterType;

  /// 摄像头基地址（可选，独立设备），如 http://192.168.3.191（ESP32-CAM）
  final String camUrl;

  /// 云查看主题（可选）：如 iaquaria/iaqua-83d4 —— 设备在云 Broker 上行时，
  /// App 局域网断开会自动订阅该主题（只读查看遥测/事件）
  final String cloudTopic;

  final bool archived;
  final DateTime? createdAt;

  Map<String, dynamic> toJson() => {
        'id': id,
        'name': name,
        'esp32Ip': esp32Ip,
        'location': location,
        'capacityL': capacityL,
        'waterType': waterType,
        'camUrl': camUrl,
        'cloudTopic': cloudTopic,
        'archived': archived,
        'createdAt': createdAt?.toIso8601String(),
      };

  factory Tank.fromJson(Map<String, dynamic> j) => Tank(
        id: j['id'] as String,
        name: (j['name'] as String?) ?? '新鱼缸',
        // 兼容旧数据：旧版本无 esp32Ip 字段，置空后由用户在鱼缸页补充
        esp32Ip: (j['esp32Ip'] as String?) ?? '',
        location: (j['location'] as String?) ?? '',
        capacityL: (j['capacityL'] as num?)?.toInt() ?? 0,
        waterType: (j['waterType'] as String?) ?? waterFresh,
        camUrl: (j['camUrl'] as String?) ?? '',
        cloudTopic: (j['cloudTopic'] as String?) ?? '',
        archived: (j['archived'] as bool?) ?? false,
        createdAt: DateTime.tryParse((j['createdAt'] as String?) ?? ''),
      );

  Tank copyWith({
    String? name,
    String? esp32Ip,
    String? location,
    int? capacityL,
    String? waterType,
    String? camUrl,
    String? cloudTopic,
    bool? archived,
  }) =>
      Tank(
        id: id,
        name: name ?? this.name,
        esp32Ip: esp32Ip ?? this.esp32Ip,
        location: location ?? this.location,
        capacityL: capacityL ?? this.capacityL,
        waterType: waterType ?? this.waterType,
        camUrl: camUrl ?? this.camUrl,
        cloudTopic: cloudTopic ?? this.cloudTopic,
        archived: archived ?? this.archived,
        createdAt: createdAt,
      );
}
