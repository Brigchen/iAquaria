/// 设备直连服务：每个鱼缸对应一台 ESP32 主板，App 通过 WebSocket 直连
/// ws://<esp32Ip>/ws 获取遥测、下发命令 —— 无 MQTT Broker、无云服务器。
///
/// 帧协议（与 Web 面板 / 上位机一致）：
/// - 设备 → App：{"ev":"hello","fw":..,"rev":N} | {"ev":"tel","d":{...}} | {"ev":"ack",...}
///   | {"ev":"cfg","cfg":{...}} | {"ev":"evt","ch":"heater","on":true,"src":"auto"}
///   | {"ev":"hist","hours":24,"ts":[..],"temp":[..],..}
/// - App → 设备：{"cmd":"tel"} | {"cmd":"cfg"} | {"cmd":"cfg.setMany","rev":N,"sets":[..]}
///   | {"cmd":"hist","hours":168} | {"cmd":"ctrl",..} | {"cmd":"feed","ms":800}
///
/// 断线自动重连（5s 间隔），切换鱼缸时自动断开旧设备连接。
/// 局域网断开时自动切云端模式：订阅遥测/事件/照片回灌本服务，同时
/// ctrl/feed 白名单命令经云端 /cmd 主题下行（远程应急控制）。
library;

import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';

import '../models/telemetry.dart';
import 'mqtt_cloud_service.dart';

/// 执行器状态翻转事件（设备自动控制 / 手动控制 / 喂食脉冲）
class ActEvent {
  ActEvent(
      {required this.ch,
      required this.on,
      required this.src,
      required this.ts});
  final String ch; // co2 / feed / light / heater / pump
  final bool on;
  final String src; // auto / manual / feed
  final DateTime ts;

  String get desc {
    const names = {
      'co2': 'CO2',
      'feed': '喂食',
      'light': '灯光',
      'heater': '加温',
      'pump': '补水泵',
    };
    final n = names[ch] ?? ch;
    return '$n ${on ? "开启" : "关闭"}（${src == "auto" ? "自动" : src == "manual" ? "手动" : "喂食脉冲"}）';
  }
}

/// 历史查询结果：ts 为 epoch 秒数组，各序列与 ts 等长（缺测=null）
class HistResult {
  HistResult({required this.hours, required this.ts, required this.series});
  final int hours;
  final List<int> ts;
  final Map<String, List<double?>> series; // temp/ph/temp_ph/tds1/tds2/lux/lvl
}

class DeviceService {
  DeviceService._();
  static final DeviceService instance = DeviceService._();

  static const Duration _connectTimeout = Duration(seconds: 5);
  static const Duration _retryInterval = Duration(seconds: 5);

  WebSocket? _ws;
  StreamSubscription? _sockSub;
  Timer? _retryTimer;
  Timer? _cloudTimer; // WS 断开后延迟启动云端订阅的兜底
  Timer? _probeTimer; // 云端模式下低频静默探测局域网是否恢复
  Timer? _telWatch; // 云端订阅后 20s 无遥测看门狗（云查看 ID 填错时主题不匹配）
  bool _nodataShown = false; // 已广播 cloud-nodata 提示（收到遥测后需恢复状态）
  bool _cloudMode = false; // 已切入云端（连接中/已连接），WS 状态不得覆盖云端状态
  String _ip = '';
  String _cloudTopic = ''; // 活动缸的云查看主题（非空时启用云端 fallback）
  bool _manualClose = false;
  int _rev = 0; // 设备配置版本号（hello/tel 帧更新，cfg.setMany 校验用）
  final List<Map<String, dynamic>> _pendingCmds = []; // 连接建立前缓存的命令

  final StreamController<Telemetry> _telController =
      StreamController.broadcast();
  final StreamController<String> _stateController =
      StreamController.broadcast();
  final StreamController<ActEvent> _evtController =
      StreamController.broadcast();
  final StreamController<Uint8List> _photoController =
      StreamController.broadcast();
  final StreamController<Map<String, dynamic>> _cfgController =
      StreamController.broadcast();
  final StreamController<Map<String, dynamic>> _ackController =
      StreamController.broadcast();
  final StreamController<HistResult> _histController =
      StreamController.broadcast();

  String _lastState = ''; // 最近一次广播的连接状态（状态条点击刷新的依据）
  DateTime? _lastTelAt; // 最近一次收到遥测（局域网/云端），云端假死检测用
  DateTime? _lastCloudRestart; // 上次强制重启云订阅时间（限频，防真离线时反复重订）

  /// 遥测数据流
  Stream<Telemetry> get telemetry => _telController.stream;

  /// 最近一次广播的连接状态（同 UI linkState；refreshLink 依据）
  String get lastState => _lastState;

  /// 统一状态广播入口：记录 + 推送
  void _emit(String s) {
    _lastState = s;
    _stateController.add(s);
  }

  /// 连接状态流："connecting" / "connected" / "disconnected" / "error"
  Stream<String> get state => _stateController.stream;

  /// 执行器事件流（CO2/加温/补水/灯光/喂食的开启关闭）
  Stream<ActEvent> get events => _evtController.stream;

  /// 配置流（连接握手与 cfg.setMany 后设备主动推送完整配置）
  Stream<Map<String, dynamic>> get config => _cfgController.stream;

  Map<String, dynamic>? _lastCfg;

  /// 最近一次设备配置快照（握手后自动推送；表单读 cloud.dev_id 等用）
  Map<String, dynamic>? get lastCfg => _lastCfg;

  /// 命令回执流（cfg.setMany / ctrl / feed 等，ok=false 时 msg 为错误原因）
  Stream<Map<String, dynamic>> get ack => _ackController.stream;

  /// 历史查询结果流（发 queryHist 后异步返回）
  Stream<HistResult> get hist => _histController.stream;

  /// 当前连接的设备 IP（未连接时为空）
  String get currentIp => _ip;

  /// 是否处于云端模式（云端直连或局域网断开后的云端兜底）
  bool get isCloudMode => _cloudMode;

  /// 设备配置版本号（cfg.setMany 时回传，设备校验防止并发覆盖）
  int get rev => _rev;

  /// 直连指定 ESP32 主板；cloudTopic 非空时，局域网断开 8 秒后自动切云端订阅
  Future<bool> connect(String ip, {String cloudTopic = ''}) async {
    final host = ip.trim();
    if (host.isEmpty) {
      if (!_cloudMode) _emit('error');
      return false;
    }
    // 内部重连（_scheduleRetry / _scheduleProbe）只传 ip、不传 cloudTopic，
    // 此时必须保留已有云主题，不能被空串覆盖，否则云端兜底永远不触发。
    final newTopic = cloudTopic.trim();
    _retryTimer?.cancel();
    // 注意：不能在此取消 _cloudTimer —— 5 秒一次的内部重连会反复进入本方法。
    // 换设备先彻底断开旧连接（disconnect 会清空 _cloudTopic），
    // 所以云主题必须在 disconnect() 【之后】再写入，否则首次连接时主题被清空。
    if (host != _ip) await disconnect();
    _manualClose = false;
    _ip = host;
    if (newTopic.isNotEmpty) _cloudTopic = newTopic;
    await _closeSocket();
    // 云端模式下的局域网恢复探测为静默连接，不广播 connecting/error，
    // 避免「设备连接中/失败」覆盖「云端查看中」状态。
    if (!_cloudMode) _emit('connecting');
    WebSocket ws;
    try {
      ws = await WebSocket.connect('ws://$host/ws').timeout(_connectTimeout);
    } catch (_) {
      if (_cloudMode) {
        _scheduleProbe(); // 云端模式：继续低频静默探测，不动状态
      } else {
        _emit('error');
        _scheduleRetry();
        _maybeStartCloud();
      }
      return false;
    }
    _ws = ws;
    // 局域网恢复：退出云端模式与后台探测
    if (_cloudMode) {
      _cloudMode = false;
      _probeTimer?.cancel();
    }
    _cloudTimer?.cancel(); // 直连已成功：撤防云端兜底
    MqttCloudService.instance.stop(); // 局域网恢复，退出云端模式
    _emit('connected');
    // 补发连接建立前缓存的命令（hist/cfg/ctrl 等）
    _flushPendingCmds();
    // 连接后立即拉一次快照，不必等设备的周期广播
    try {
      ws.add(jsonEncode({'cmd': 'tel'}));
    } catch (_) {}
    _attachSocket(ws);
    return true;
  }

  /// 绑定 WS 数据/断线监听（首次直连与云端模式下探测恢复共用）
  void _attachSocket(WebSocket ws) {
    _sockSub = ws.listen(
      (data) => _onFrame(data),
      onDone: () {
        if (_manualClose) return;
        if (_cloudMode) {
          // 探测恢复后又短暂掉线：回到云端状态，继续静默探测
          _emit('cloud');
          _scheduleProbe();
          return;
        }
        _emit('disconnected');
        _scheduleRetry();
        _maybeStartCloud();
      },
      onError: (_) {
        if (_manualClose) return;
        if (_cloudMode) {
          _scheduleProbe();
          return;
        }
        _emit('error');
        _scheduleRetry();
        _maybeStartCloud();
      },
    );
  }

  /// 下发命令帧（如 {"cmd":"ctrl","ch":"light","on":true}）。
  /// - 局域网：WS 已 open 直接发送；尚未 open（连接中/重连中）时入队，
  ///   握手后自动补发，避免静默丢失。
  /// - 云端模式：WS 不参与，仅 ctrl/feed 白名单命令经云端 /cmd 主题下发
  ///   （设备端白名单一致，其余命令设备也不放行），用于远程应急控制。
  Future<void> sendCmd(Map<String, dynamic> cmd) async {
    final ws = _ws;
    if (ws == null || ws.readyState != WebSocket.open) {
      if (_cloudMode) {
        // 云端下行（应急控制）：仅放行与设备端白名单一致的 ctrl/feed
        final c = '${cmd['cmd'] ?? ''}';
        if (c == 'ctrl' || c == 'feed') {
          MqttCloudService.instance.publishCmd(cmd);
        }
        return;
      }
      if (_pendingCmds.length >= 8) _pendingCmds.removeAt(0);
      _pendingCmds.add(cmd);
      return;
    }
    try {
      ws.add(jsonEncode(cmd));
    } catch (_) {}
  }

  /// 连接就绪后补发缓存命令（tel/cfg/hist 等）
  void _flushPendingCmds() {
    final ws = _ws;
    if (ws == null || ws.readyState != WebSocket.open) return;
    final cmds = List<Map<String, dynamic>>.from(_pendingCmds);
    _pendingCmds.clear();
    for (final c in cmds) {
      try {
        ws.add(jsonEncode(c));
      } catch (_) {}
    }
  }

  /// 请求设备当前配置（结果经 config 流返回）
  void requestCfg() => sendCmd({'cmd': 'cfg'});

  /// 批量修改设备配置：sets 为 [{"path":"ctrl.heater.sp_c","value":25.5},..]
  /// rev 为配置版本号（来自 hello/tel/cfg 帧），不一致时设备拒绝并提示刷新
  void setCfgMany(int rev, List<Map<String, dynamic>> sets) =>
      sendCmd({'cmd': 'cfg.setMany', 'rev': rev, 'sets': sets});

  /// 查询历史趋势：hours ∈ {24, 168, 720, 8760}（结果经 hist 流返回）
  void queryHist(int hours) => sendCmd({'cmd': 'hist', 'hours': hours});

  /// 手动控制执行器：ch ∈ co2/light/heater/pump；on 为 true/false，
  /// 或 mode:"auto" 恢复自动
  void ctrl(String ch, {bool? on, bool auto = false}) {
    final cmd = <String, dynamic>{'cmd': 'ctrl', 'ch': ch};
    if (auto) {
      cmd['mode'] = 'auto';
    } else if (on != null) {
      cmd['on'] = on;
    }
    sendCmd(cmd);
  }

  /// 喂食脉冲
  void feed({int ms = 800}) => sendCmd({'cmd': 'feed', 'ms': ms});

  /// 云查看直连（无局域网 IP 的人工缸也可用）：只要配置了云查看主题即
  /// 订阅设备上行的遥测/事件/照片，并支持云端下行应急控制（ctrl/feed），
  /// 失败每 20 秒自动重试。
  Future<bool> connectCloudOnly(String cloudTopic) async {
    final t = cloudTopic.trim();
    await disconnect(); // 清空旧连接与云订阅
    if (t.isEmpty) return false;
    _manualClose = false;
    _cloudTopic = t;
    _enterCloudMode(); // 广播 cloud-connecting（探测因无 IP 自动不启用）
    await _startCloudWithRetry();
    return MqttCloudService.instance.active;
  }

  /// 手动断开（切换缸 / 删除缸时调用），不触发重连，同时退出云端模式
  Future<void> disconnect() async {
    _manualClose = true;
    _cloudMode = false;
    _retryTimer?.cancel();
    _cloudTimer?.cancel();
    _probeTimer?.cancel();
    _cloudTopic = '';
    await MqttCloudService.instance.stop();
    await _closeSocket();
    _ip = '';
  }

  // ───── 云端 fallback 与数据回灌（MqttCloudService 调用） ─────

  /// WS 断开后布防云端兜底：8 秒后仍未恢复直连则切云端订阅（查看 + 应急控制）。
  ///
  /// 关键：本方法是【幂等一次布防】——定时器一旦启动，后续 5 秒一次的 WS
  /// 重连失败不得将其重置。鸿蒙断网时 WebSocket.connect 会立即抛异常（无路由，
  /// 不等 5 秒超时），若每次失败都重排 8 秒定时器，云端将永远轮不到触发。
  /// 撤防时机：直连成功（connect 内）或手动 disconnect。
  void _maybeStartCloud() {
    if (_cloudTopic.isEmpty || _manualClose || _ip.isEmpty || _cloudMode) {
      return;
    }
    if (_cloudTimer?.isActive ?? false) return; // 已布防，不被重连重置
    _cloudTimer = Timer(const Duration(seconds: 8), () {
      if (_manualClose || _cloudTopic.isEmpty || _cloudMode) return;
      _enterCloudMode();
      _startCloudWithRetry();
    });
  }

  /// 尝试云订阅；失败则每 20 秒重试，直到成功或手动断开 / 局域网友连恢复。
  /// 失败时状态带真实原因：cloud-error|<原因>，状态条直接展示。
  Future<void> _startCloudWithRetry() async {
    if (_manualClose || _cloudTopic.isEmpty || !_cloudMode) return;
    _emit('cloud-connecting');
    final ok = await MqttCloudService.instance.start(_cloudTopic);
    if (ok || _manualClose || _cloudTopic.isEmpty || !_cloudMode) return;
    final err = MqttCloudService.instance.lastError;
    _emit(err.isEmpty ? 'cloud-error|' : 'cloud-error|$err');
    _cloudTimer?.cancel();
    _cloudTimer = Timer(const Duration(seconds: 20), _startCloudWithRetry);
  }

  /// 进入云端模式：停高频重连、广播「切换云端中」、启动局域网恢复探测
  void _enterCloudMode() {
    _cloudMode = true;
    _retryTimer?.cancel();
    _emit('cloud-connecting');
    _scheduleProbe();
  }

  /// 云端模式下每 20 秒静默尝试一次局域网友连（不广播中间状态）；
  /// 一旦成功即退出云端模式恢复直连与控制能力。
  void _scheduleProbe() {
    _probeTimer?.cancel();
    if (!_cloudMode || _manualClose || _ip.isEmpty) return;
    _probeTimer = Timer(const Duration(seconds: 20), () {
      if (_cloudMode && !_manualClose && _ip.isNotEmpty) connect(_ip);
    });
  }

  /// 云端遥测回灌（与 WS tel 帧同构），UI 无感。
  /// 若此前提示过「无数据」（ID 填错后改对/设备恢复上线），此处恢复云端正常状态。
  void ingestTel(Map<String, dynamic> d) {
    _lastTelAt = DateTime.now();
    _lastCloudRestart = null; // 链路健康，重置强制重订限频
    if (_nodataShown) {
      _nodataShown = false;
      _emit('cloud');
    }
    _telController.add(Telemetry.fromJson(d));
  }

  /// 云端执行器事件回灌
  void ingestEvt(String ch, bool on, String src) {
    _evtController.add(ActEvent(ch: ch, on: on, src: src, ts: DateTime.now()));
  }

  /// 云端照片回灌（ESP32-CAM 定时上传的 JPEG；retained，订阅即收到最新一张）
  void ingestPhoto(Uint8List jpeg) {
    _photoController.add(jpeg);
  }

  /// 云端照片流（云订阅建立后立即收到 retained 最新帧）
  Stream<Uint8List> get cloudPhoto => _photoController.stream;

  /// 云端订阅状态（true=已进入云端查看，false=退出）。
  ///
  /// 进入后启动【周期】看门狗（每 20s）：
  /// - 订阅后从未收到遥测（retained 应立即回放）→ 提示云查看 ID 可能填错；
  /// - 此前有数据但 >75s 无更新（正常 30s 一帧）→ 判定云订阅假死
  ///   （autoReconnect 静默放弃 / Broker 半开连接），强制重订一次。
  ///   重订按 5 分钟限频：设备真离线时不反复制造订阅流量。
  /// 这修复「仪器有连接但一直显示云端查看中且数据不更新」的问题。
  void cloudActive(bool up) {
    _telWatch?.cancel();
    _telWatch = null;
    if (up) {
      _nodataShown = false;
      _lastTelAt = null; // 新订阅从零计时（retained 帧应数秒内到达）
      _telWatch = Timer.periodic(const Duration(seconds: 20), (_) {
        if (_manualClose || !_cloudMode) return;
        if (!MqttCloudService.instance.active) return;
        final last = _lastTelAt;
        if (last == null) {
          // 订阅建立后从未收到遥测：多为云查看 ID 与设备实际 ID 不符
          if (!_nodataShown) {
            _nodataShown = true;
            _emit('cloud-nodata|已连上云端但 20 秒未收到设备数据，'
                '请核对鱼缸页「云查看设备 ID」是否与设备实际 ID 一致（设备 Web 管理页可查）');
          }
          return;
        }
        if (DateTime.now().difference(last) <= const Duration(seconds: 75)) {
          return; // 数据新鲜
        }
        final lastR = _lastCloudRestart;
        if (lastR != null &&
            DateTime.now().difference(lastR) < const Duration(minutes: 5)) {
          return; // 限频：避免设备真离线时每 20s 重订
        }
        _lastCloudRestart = DateTime.now();
        _cloudTimer?.cancel();
        _startCloudWithRetry(); // 强制重订（状态条短暂显示"切换云端中"）
      });
    } else {
      _nodataShown = false;
      _lastTelAt = null;
    }
    _emit(up ? 'cloud' : 'disconnected');
  }

  /// 状态条点击「立即刷新」：按当前链路状态立即重探，不等周期定时器。
  /// - 已直连：请求一帧遥测快照（立即刷新数据）
  /// - 云端态：先静默试一次局域网直连（成功即切回直连），失败则强制重订云端
  /// - 连接失败/断开态：立即重连一次（失败自动恢复 5s 周期重试 + 云端布防）
  Future<void> refreshLink() async {
    if (_lastState == 'connected') {
      sendCmd({'cmd': 'tel'});
      return;
    }
    if (_lastState == 'manual' || _manualClose) return;
    if (_cloudMode) {
      if (_ip.isNotEmpty) {
        final ok = await connect(_ip); // 成功 → 内部已切直连并广播 connected
        if (ok) return;
      }
      _cloudTimer?.cancel();
      await _startCloudWithRetry(); // 重订云端（状态条显示进展/失败原因）
      return;
    }
    if (_ip.isNotEmpty) {
      _retryTimer?.cancel();
      await connect(_ip);
    }
  }

  void _onFrame(dynamic data) {
    if (data is! String) return;
    try {
      final frame = jsonDecode(data);
      if (frame is! Map) return;
      final ev = frame['ev'];
      if (ev == 'hello') {
        _rev = (frame['rev'] is num) ? (frame['rev'] as num).toInt() : _rev;
        // 握手完成后再要一次快照与配置，覆盖设备刚启动的场景
        sendCmd({'cmd': 'tel'});
        sendCmd({'cmd': 'cfg'});
      } else if (ev == 'tel') {
        final d = frame['d'];
        if (d is Map) {
          if (d['rev'] is num) _rev = (d['rev'] as num).toInt();
          _telController.add(Telemetry.fromJson(Map<String, dynamic>.from(d)));
        }
      } else if (ev == 'evt') {
        _evtController.add(ActEvent(
          ch: '${frame['ch'] ?? ''}',
          on: frame['on'] == true,
          src: '${frame['src'] ?? 'auto'}',
          ts: DateTime.now(),
        ));
      } else if (ev == 'cfg') {
        final c = frame['cfg'];
        if (c is Map) {
          _lastCfg = Map<String, dynamic>.from(c);
          _cfgController.add(_lastCfg!);
        }
      } else if (ev == 'ack') {
        _ackController.add(Map<String, dynamic>.from(frame));
      } else if (ev == 'hist') {
        _histController.add(_parseHist(frame));
      }
    } catch (_) {
      // 非 JSON 帧忽略
    }
  }

  HistResult _parseHist(Map frame) {
    final tsRaw = frame['ts'];
    final ts = <int>[];
    if (tsRaw is List) {
      for (final v in tsRaw) {
        final n = (v is num) ? v.toInt() : int.tryParse('$v');
        if (n != null) ts.add(n);
      }
    }
    const keys = ['temp', 'ph', 'temp_ph', 'tds1', 'tds2', 'lux', 'lvl'];
    final series = <String, List<double?>>{};
    for (final k in keys) {
      final raw = frame[k];
      final list = <double?>[];
      if (raw is List) {
        for (final v in raw) {
          list.add((v is num) ? v.toDouble() : null);
        }
      }
      series[k] = list;
    }
    final h = frame['hours'];
    return HistResult(
        hours: (h is num) ? h.toInt() : 24, ts: ts, series: series);
  }

  void _scheduleRetry() {
    _retryTimer?.cancel();
    if (_manualClose || _ip.isEmpty) return;
    _retryTimer = Timer(_retryInterval, () {
      if (!_manualClose && _ip.isNotEmpty) connect(_ip);
    });
  }

  Future<void> _closeSocket() async {
    _sockSub?.cancel();
    _sockSub = null;
    final ws = _ws;
    _ws = null;
    if (ws == null) return;
    try {
      await ws.close();
    } catch (_) {}
  }
}
