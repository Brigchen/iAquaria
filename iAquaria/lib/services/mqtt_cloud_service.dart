/// 云查看服务：局域网 WS 断开时，自动订阅设备在云 Broker（EMQX Serverless 等
/// MQTT over TLS）上行到遥测/事件主题，并支持云端下行应急控制。
///
/// - App 经 WebSocket over TLS（wss，默认 8084）连接云 Broker
/// - 订阅 iaquaria/<dev_id>/tel（retained 遥测，30s 一帧）与 /evt（执行器事件）
/// - 下行发布 iaquaria/<dev_id>/cmd（QoS1）：设备端白名单仅放行 ctrl/feed，
///   执行结果经 30s 周期遥测帧 act[] 回传（应急够用，非实时）
/// - 解析后回灌 DeviceService 的流，UI 与局域网直连一致，无感切换
library;

import 'dart:async';
import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:mqtt_client/mqtt_client.dart';
import 'package:mqtt_client/mqtt_server_client.dart';

import 'device_service.dart';
import 'storage_service.dart';

class MqttCloudService {
  MqttCloudService._();
  static final MqttCloudService instance = MqttCloudService._();

  MqttServerClient? _client;
  String _topic = '';
  bool _starting = false;

  /// 本次云订阅以来是否收到过设备遥测帧（用于「已连云端但无数据」诊断提示）。
  /// 注意：主题不匹配（云查看 ID 填错）时 Broker 连接与订阅均成功但永远无数据。
  bool gotTel = false;

  /// 最近一次云连接失败原因（成功后清空），用于状态条直接展示
  String lastError = '';

  bool get active => _client != null;

  /// 启动云订阅（topic 如 iaquaria/iaqua-84d4；未配置 Broker 时返回 false）。
  /// 返回 true=已连上 Broker 并完成订阅；false=未配置或连接失败（调用方可重试）。
  Future<bool> start(String topic) async {
    final t = topic.trim();
    if (t.isEmpty || _starting) return false;
    if (active && _topic == t) return true;
    await stop();
    final st = StorageService.instance;
    // 清洗误粘贴：去协议头、锚点(#)与空白。空 path 的 WSS 请求无法路由到
    // EMQX 的 /mqtt 端点（服务器不返回 101 → "was not upgraded"），
    // PC 端实测：wss://host:8084 必败，wss://host:8084/mqtt 可连，故统一补 /mqtt。
    var host = (await st.cloudHost()).trim();
    host = host.replaceFirst(RegExp(r'^wss?://', caseSensitive: false), '');
    host = host.split('#').first.trim();
    if (host.isEmpty) {
      lastError = '设置页未配置 Broker 地址';
      return false;
    }
    _starting = true;
    try {
      final port = await st.cloudPort();
      final user = (await st.cloudUser()).trim();
      final pass = await st.cloudPass();

      // 已带非空路径（如 host:8084/mqtt）则原样保留，否则补 EMQX 标准路径
      final slash = host.indexOf('/');
      final addr = (slash >= 0 && slash < host.length - 1) ? host : '$host/mqtt';
      final c = MqttServerClient(
          'wss://$addr', 'iaquaria-app-${DateTime.now().millisecondsSinceEpoch % 1000000}');
      c.port = port > 0 ? port : 8084;
      c.useWebSocket = true; // wss:// 前缀 → TLS WebSocket
      c.autoReconnect = true; // 运行中掉线由库自动重连（EMQX 心跳超时等）
      c.setProtocolV311();
      c.keepAlivePeriod = 30;
      c.onBadCertificate = (_) => true; // 公共 CA 兜底
      c.connectionMessage = MqttConnectMessage()
          .withClientIdentifier(c.clientIdentifier)
          .startClean()
          .authenticateAs(user, pass) // 匿名 Broker 时留空即可
          .withWillQos(MqttQos.atMostOnce);
      await c.connect();
      if (c.connectionStatus?.state != MqttConnectionState.connected) {
        c.disconnect();
        lastError = 'Broker 拒绝连接（${c.connectionStatus?.state}），检查用户名/密码';
        return false;
      }
      lastError = '';
      _client = c;
      _topic = t;
      gotTel = false; // 新一轮订阅，重置遥测接收标志
      c.subscribe('$t/tel', MqttQos.atMostOnce);
      c.subscribe('$t/evt', MqttQos.atMostOnce);
      c.subscribe('$t/img', MqttQos.atMostOnce); // ESP32-CAM 定时云照片（retained）
      c.updates!.listen(_onMsg);
      // 通知 DeviceService 进入云端查看状态（App 状态条显示云端模式）
      DeviceService.instance.cloudActive(true);
      return true;
    } catch (e) {
      // 打印并记录真实原因（DNS/网络/TLS），状态条直接展示，便于远程测试定位
      debugPrint('[MQTT-CLOUD] 连接失败: $e');
      lastError = e.toString().replaceAll(RegExp(r'\s+'), ' ').trim();
      if (lastError.length > 400) lastError = lastError.substring(0, 400);
      await stop();
      return false;
    } finally {
      _starting = false;
    }
  }

  Future<void> stop() async {
    final c = _client;
    _client = null;
    _topic = '';
    if (c != null) {
      try {
        c.disconnect();
      } catch (_) {}
      DeviceService.instance.cloudActive(false);
    }
  }

  /// 发布云端下行命令到 iaquaria/<dev_id>/cmd（QoS1，如 ctrl/feed）。
  /// 设备端白名单放行 ctrl/feed，其余命令静默丢弃。返回 false=未连接或发布失败。
  bool publishCmd(Map<String, dynamic> j) {
    final c = _client;
    if (c == null || _topic.isEmpty) return false;
    if (c.connectionStatus?.state != MqttConnectionState.connected) return false;
    try {
      final b = MqttClientPayloadBuilder();
      b.addString(jsonEncode(j));
      c.publishMessage('$_topic/cmd', MqttQos.atLeastOnce, b.payload!);
      return true;
    } catch (_) {
      return false;
    }
  }

  void _onMsg(List<MqttReceivedMessage<MqttMessage>> msgs) {
    for (final m in msgs) {
      try {
        final pub = m.payload as MqttPublishMessage;
        final text =
            MqttPublishPayload.bytesToStringAsString(pub.payload.message);
        final j = jsonDecode(text);
        if (j is! Map) continue;
        if (m.topic.endsWith('/tel')) {
          gotTel = true; // 已收到设备遥测（retained 立即回放或 30s 周期帧）
          // 云端遥测 JSON 与 WS tel 帧的 d 字段同构
          DeviceService.instance
              .ingestTel(Map<String, dynamic>.from(j.cast<String, dynamic>()));
        } else if (m.topic.endsWith('/evt')) {
          // 设备 /evt 上行有两类：执行器事件（无 ev 字段）与命令回执
          // cmd_ack（ev=cmd_ack）。回执无 ch/on，不能当执行器事件回灌，
          // 否则会凭空多出一条「关闭（自动）」的假事件
          if ('${j['ev'] ?? ''}' == 'cmd_ack') continue;
          DeviceService.instance.ingestEvt('${j['ch'] ?? ''}',
              j['on'] == true, '${j['src'] ?? 'auto'}');
        } else if (m.topic.endsWith('/img')) {
          // {"ts":epoch,"fmt":"jpeg","b64":"..."} → JPEG 字节
          final b64 = '${j['b64'] ?? ''}';
          if (b64.isNotEmpty) {
            final jpeg = base64Decode(b64);
            DeviceService.instance.ingestPhoto(Uint8List.fromList(jpeg));
          }
        }
      } catch (_) {
        // 非 JSON 载荷忽略
      }
    }
  }
}
