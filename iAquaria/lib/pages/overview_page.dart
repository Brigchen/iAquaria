/// 概览页：滚动告警条 + 摄像头实时画面（快照轮询）+ 实时指标网格 + 设备状态
/// + 历史趋势图（24h/7d/30d/1y，与设备 Web 面板同源同约定）。
library;

import 'dart:async';
import 'dart:io';
import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:path_provider/path_provider.dart';

import '../app.dart';
import '../core/metrics.dart';
import '../core/version.dart';
import '../core/theme.dart';
import '../services/camera_service.dart';
import '../services/device_service.dart';
import '../services/local_data_service.dart';
import '../widgets/bio_panel.dart';
import '../widgets/device_control_panel.dart';
import '../widgets/trend_chart.dart';

class OverviewPage extends StatefulWidget {
  const OverviewPage({super.key});

  @override
  State<OverviewPage> createState() => _OverviewPageState();
}

class _OverviewPageState extends State<OverviewPage> {
  static const _rangeHours = [24, 168, 720, 8760];
  static const _rangeNames = ['24小时', '7天', '30天', '1年'];

  int _rangeIdx = 0;
  HistResult? _hist;
  bool _histLoading = false; // 仅局域网向设备补拉时为 true
  Timer? _histTimeout; // 查询超时兜底（设备离线时避免永久转圈）
  StreamSubscription<HistResult>? _histSub;
  String? _loadedTank; // 已加载趋势的缸/范围（避免重复读取）
  int? _loadedHours;

  @override
  void initState() {
    super.initState();
    // 设备 hist 帧（局域网补拉结果）：回填本地并展示
    _histSub = DeviceService.instance.hist.listen(_onDeviceHist);
  }

  @override
  void dispose() {
    _histSub?.cancel();
    _histTimeout?.cancel();
    super.dispose();
  }

  /// 状态条点击：立即重探当前链路（不等周期定时器）。
  /// 已直连→拉一帧快照；云端态→先试局域网恢复、失败则重订云端；
  /// 断开/失败→立即重连。结果由状态条自身的状态变化呈现。
  Future<void> _refreshLink(BuildContext context) async {
    final store = AppStore.instance;
    if (store.linkState == 'manual') {
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(
          content: Text('手动管理缸无设备连接'), behavior: SnackBarBehavior.floating));
      return;
    }
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(
        content:
            Text(store.linkState == 'connected' ? '正在请求最新数据…' : '正在重新检测设备连接…'),
        behavior: SnackBarBehavior.floating,
        duration: const Duration(seconds: 2)));
    await DeviceService.instance.refreshLink();
  }

  /// 局域网查询设备历史成功：种子本地数据 + 立即展示
  Future<void> _onDeviceHist(HistResult h) async {
    if (!mounted || h.hours != _rangeHours[_rangeIdx]) return;
    final tank = AppStore.instance.activeTank;
    final dev = DeviceService.instance;
    // 仅当前活动缸且仍直连同一设备时才回填（防止切缸后旧帧误写入新缸）
    if (tank == null ||
        tank.esp32Ip.trim().isEmpty ||
        dev.currentIp != tank.esp32Ip.trim()) {
      return;
    }
    await LocalDataService.instance.seedHist(tank.id, h);
    if (!mounted) return;
    setState(() {
      _hist = h;
      _histLoading = false;
    });
  }

  /// 趋势加载：先读本机（瞬时、不下载）；局域网在线且本机数据稀疏时
  /// 向设备补拉一次并回填本地，之后不再频繁下载
  Future<void> _loadTrend() async {
    final tank = AppStore.instance.activeTank;
    if (tank == null) return;
    final hours = _rangeHours[_rangeIdx];
    if (_loadedTank == tank.id && _loadedHours == hours && _hist != null) {
      return;
    }
    _loadedTank = tank.id;
    _loadedHours = hours;
    final local = await LocalDataService.instance.readSeries(tank.id, hours);
    if (!mounted) return;
    setState(() => _hist = local);
    // 局域网直连在线：本机该区间数据不足（首次使用/长期离线）时补拉一次
    final dev = DeviceService.instance;
    final ip = tank.esp32Ip.trim();
    if (ip.isNotEmpty && dev.currentIp == ip && local.ts.length < 8) {
      _histTimeout?.cancel();
      _histTimeout = Timer(const Duration(seconds: 12), () {
        if (mounted && _histLoading) setState(() => _histLoading = false);
      });
      setState(() => _histLoading = true);
      dev.queryHist(hours);
    }
  }

  @override
  Widget build(BuildContext context) {
    final store = AppStore.instance;
    return AnimatedBuilder(
      animation: store,
      builder: (context, _) {
        final tank = store.activeTank;
        if (tank == null) {
          return const Center(child: Text('还没有鱼缸，请到「鱼缸」Tab 添加'));
        }
        final tel = store.telemetry;
        final wt = tank.waterType;
        final hasDevice = tank.esp32Ip.trim().isNotEmpty;
        final hasSource = hasDevice || tank.cloudTopic.trim().isNotEmpty;
        // 无实时数据（人工缸/断连/未连接）：指标卡回退显示本机最近一次记录
        final fallback =
            tel.isEmpty ? store.localLatest : const <String, double>{};
        double? fv(double? v, String k) => v ?? fallback[k];

        // 指标卡片：海水缸只显示单个盐度（tds1），不显示 tds2
        final cards = <_CardData>[
          _CardData('水温', fv(tel.temp, 'temp'), '℃'),
          _CardData('pH', fv(tel.ph, 'ph'), ''),
          _CardData(Metrics.label('temp_ph'), fv(tel.tempPh, 'temp_ph'), '℃'),
          _CardData(Metrics.label('tds1', waterType: wt), fv(tel.tds1, 'tds1'),
              Metrics.unit('tds1', waterType: wt)),
          if (!Metrics.isSalt(wt))
            _CardData(Metrics.label('tds2', waterType: wt),
                fv(tel.tds2, 'tds2'), Metrics.unit('tds2', waterType: wt)),
          _CardData('水位', fv(tel.level, 'lvl'), '%'),
          _CardData('光照', fv(tel.lux, 'lux'), 'lx'),
        ];

        // 趋势图序列：水型过滤（海水无 tds2）
        final hist = _hist;
        final series = <String, List<double?>>{};
        if (hist != null) {
          for (final s in kSeriesStyles) {
            if (s.key == 'tds2' && Metrics.isSalt(wt)) continue;
            series[s.key] = hist.series[s.key] ?? const [];
          }
        }

        // 首次/切缸/切范围后加载趋势（本机优先）
        WidgetsBinding.instance.addPostFrameCallback((_) => _loadTrend());

        return ListView(
          padding: const EdgeInsets.fromLTRB(14, 4, 14, 20),
          children: [
            // 滚动告警条（视频上方）
            if (store.lastAlert != null)
              _MarqueeAlert(message: store.lastAlert!.message),
            // 摄像头实时画面（快照轮询；云端模式显示设备定时上传的云照片）
            if (tank.camUrl.trim().isNotEmpty || store.isCloudLink)
              _CamView(camBase: tank.camUrl)
            else
              const _CamPlaceholder(hint: '在「鱼缸」页为当前缸填写摄像头地址后显示实时画面'),
            const SizedBox(height: 8),
            // 设备直连状态条（点击立即刷新链路）
            _StateBar(
                state: store.linkState, onTap: () => _refreshLink(context)),
            const SizedBox(height: 8),
            // 生物概览（水质参数上方；AI 识别回写 + 手动修正）
            const BioPanel(),
            // 指标网格
            ..._grid(cards),
            // 无实时链路且本机有记录时提示数据来源
            if (tel.isEmpty && fallback.isNotEmpty)
              const Padding(
                padding: EdgeInsets.only(top: 2, left: 4),
                child: Text('当前无实时数据，显示本机最近一次记录（含人工测量）',
                    style: TextStyle(fontSize: 11, color: AppTheme.muted)),
              ),
            const SizedBox(height: 8),
            // 历史趋势图（本机数据；设备缸局域网在线时数据稀疏才向设备补拉）
            _buildTrend(tank.id, series, hist, hasSource),
            const SizedBox(height: 8),
            // 设备控制（与 Web 面板同源：手动接管 / 交还自动 / 投喂）。
            // 云端查看缸（只填云查看 ID）收到遥测后同样显示，支持云端应急控制
            if (hasDevice ||
                (tank.cloudTopic.trim().isNotEmpty && !tel.isEmpty))
              DeviceControlPanel(tel: tel, linkState: store.linkState),
          ],
        );
      },
    );
  }

  Widget _buildTrend(String tankId, Map<String, List<double?>> series,
      HistResult? hist, bool hasSource) {
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: const Color(0xFFe2e8f0)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Expanded(
                child: Text('历史趋势',
                    style:
                        TextStyle(fontSize: 13.5, fontWeight: FontWeight.w700)),
              ),
              if (_histLoading)
                const SizedBox(
                    width: 14,
                    height: 14,
                    child: CircularProgressIndicator(strokeWidth: 2)),
            ],
          ),
          const SizedBox(height: 6),
          // 时间范围切换（对齐设备 Web 面板）
          Row(
            children: [
              for (var i = 0; i < _rangeNames.length; i++) ...[
                if (i > 0) const SizedBox(width: 6),
                Expanded(
                  child: GestureDetector(
                    onTap: () {
                      if (i == _rangeIdx) return;
                      setState(() {
                        _rangeIdx = i;
                        _hist = null;
                        _histLoading = false;
                        _loadedHours = null; // 触发重新读取本机
                      });
                    },
                    child: Container(
                      padding: const EdgeInsets.symmetric(vertical: 6),
                      decoration: BoxDecoration(
                        color: i == _rangeIdx
                            ? AppTheme.tealDark
                            : const Color(0xFFf1f5f9),
                        borderRadius: BorderRadius.circular(8),
                      ),
                      alignment: Alignment.center,
                      child: Text(_rangeNames[i],
                          style: TextStyle(
                            fontSize: 12,
                            color:
                                i == _rangeIdx ? Colors.white : AppTheme.muted,
                            fontWeight: i == _rangeIdx
                                ? FontWeight.w700
                                : FontWeight.w400,
                          )),
                    ),
                  ),
                ),
              ],
            ],
          ),
          const SizedBox(height: 10),
          if (hist != null && hist.ts.isNotEmpty)
            TrendChart(ts: hist.ts, series: series, hours: hist.hours)
          else if (_histLoading)
            SizedBox(
                height: 120,
                child: Center(
                    child: Text('正在从设备补拉 ${_rangeNames[_rangeIdx]}历史…',
                        style: const TextStyle(
                            fontSize: 12, color: AppTheme.muted))))
          else
            SizedBox(
                height: 120,
                child: Center(
                    child: Text(
                        hasSource
                            ? '暂无历史数据（联网后自动同步本机，设备每 30 分钟记录）'
                            : '暂无历史数据（人工测量记录后在此生成趋势）',
                        style: const TextStyle(
                            fontSize: 12, color: AppTheme.muted)))),
        ],
      ),
    );
  }

  List<Widget> _grid(List<_CardData> cards) {
    final rows = <Widget>[];
    for (var i = 0; i < cards.length; i += 2) {
      rows.add(Row(
        children: [
          Expanded(child: _MetricCard(data: cards[i])),
          const SizedBox(width: 8),
          Expanded(
            child: i + 1 < cards.length
                ? _MetricCard(data: cards[i + 1])
                : const SizedBox(),
          ),
        ],
      ));
      rows.add(const SizedBox(height: 8));
    }
    return rows;
  }
}

// ───────────────────────── 滚动告警条 ─────────────────────────
class _MarqueeAlert extends StatefulWidget {
  const _MarqueeAlert({required this.message});
  final String message;

  @override
  State<_MarqueeAlert> createState() => _MarqueeAlertState();
}

class _MarqueeAlertState extends State<_MarqueeAlert>
    with SingleTickerProviderStateMixin {
  late final AnimationController _ctrl =
      AnimationController(vsync: this, duration: const Duration(seconds: 9))
        ..repeat();

  @override
  void dispose() {
    _ctrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.only(bottom: 8),
      height: 34,
      decoration: BoxDecoration(
        color: const Color(0xFFfef2f2),
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: AppTheme.danger.withOpacity(.4)),
      ),
      child: Row(children: [
        const Padding(
            padding: EdgeInsets.symmetric(horizontal: 8),
            child: Icon(Icons.notifications_active,
                color: AppTheme.danger, size: 18)),
        Expanded(
          child: ClipRect(
            child: AnimatedBuilder(
              animation: _ctrl,
              builder: (context, _) {
                // 从右向左循环滚动
                return Align(
                  alignment: Alignment(_ctrl.value * 2 - 1, 0),
                  child: Text(
                    widget.message,
                    maxLines: 1,
                    style:
                        const TextStyle(fontSize: 12.5, color: AppTheme.danger),
                  ),
                );
              },
            ),
          ),
        ),
      ]),
    );
  }
}

// ───────────────────────── 摄像头实时画面 ─────────────────────────

/// 摄像头状态：connecting=后台探测中 / online=已连接（显示视频窗口）/ offline=不在线
enum _CamState { connecting, online, offline }

class _CamView extends StatefulWidget {
  const _CamView({required this.camBase});
  final String camBase;

  @override
  State<_CamView> createState() => _CamViewState();
}

class _CamViewState extends State<_CamView> {
  // 帧封面缓存（按摄像头地址键控）：内存 + 本地文件双级。
  // 打开页面默认不拉流（多终端同时拉流会挤占设备端 HTTP 服务与带宽），
  // 仅显示最近一帧封面；点右上角播放键才启动 1.4s/帧轮询
  static final Map<String, Uint8List> _frameCache = {};
  static final Map<String, DateTime> _frameCacheAt = {};
  static final Set<String> _cacheLoaded = {}; // 已从磁盘恢复过封面的摄像头
  static final Map<String, DateTime> _lastSaveAt = {}; // 写盘节流

  bool _fetching = false;
  bool _playing = false; // 默认不拉流，点播放才开始
  Timer? _timer;
  int _failCount = 0;
  _CamState _state = _CamState.connecting;

  @override
  void initState() {
    super.initState();
    _loadCoverFromDisk();
  }

  @override
  void didUpdateWidget(_CamView old) {
    super.didUpdateWidget(old);
    // 切缸（摄像头地址变化）：停止旧缸拉流，恢复新缸封面
    if (old.camBase != widget.camBase) {
      _stop();
      _loadCoverFromDisk();
    }
  }

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }

  /// 启动播放：立即取首帧，随后 1.4s/帧
  void _start() {
    setState(() {
      _playing = true;
      _failCount = 0;
      _state = _CamState.connecting;
    });
    _timer?.cancel();
    _timer = Timer.periodic(const Duration(milliseconds: 1400), (_) => _grab());
    _grab();
  }

  /// 停止拉流回封面态（手动暂停 / 连续失败 / 切缸）
  void _stop() {
    _timer?.cancel();
    _timer = null;
    if (mounted) setState(() => _playing = false);
  }

  Future<void> _grab() async {
    if (!_playing || _fetching || !mounted) return;
    // 云端模式（含切换中/云失败重试）：局域网摄像头不可达，停止轮询
    if (AppStore.instance.isCloudLink) {
      _stop();
      return;
    }
    _fetching = true;
    try {
      final jpeg = await CameraService.instance.capture(widget.camBase);
      _failCount = 0;
      _frameCache[widget.camBase] = jpeg;
      _frameCacheAt[widget.camBase] = DateTime.now();
      if (mounted) {
        setState(() => _state = _CamState.online);
        _saveCoverToDisk(jpeg); // 异步写盘作下次封面（5s 节流）
      }
    } catch (_) {
      _failCount++;
      // 连续 3 次失败（约 4 秒）判定不在线：停止轮询回封面态，避免后台空耗
      if (_failCount >= 3 && mounted) {
        setState(() => _state = _CamState.offline);
        _stop();
      }
    } finally {
      _fetching = false;
    }
  }

  /// 从磁盘恢复上次会话的最后一帧作封面（App 重启后也有封面）
  Future<void> _loadCoverFromDisk() async {
    final key = widget.camBase;
    if (_cacheLoaded.contains(key)) return;
    _cacheLoaded.add(key);
    try {
      final f = await _coverFile();
      if (await f.exists()) {
        _frameCache[key] = await f.readAsBytes();
        _frameCacheAt[key] = await f.lastModified();
      }
    } catch (_) {}
    if (mounted) setState(() {});
  }

  Future<void> _saveCoverToDisk(Uint8List jpeg) async {
    // 节流：每 5 秒最多写一次，避免播放期间频繁磁盘 IO
    final now = DateTime.now();
    final last = _lastSaveAt[widget.camBase];
    if (last != null && now.difference(last).inSeconds < 5) return;
    _lastSaveAt[widget.camBase] = now;
    try {
      final f = await _coverFile();
      await f.writeAsBytes(jpeg, flush: false);
    } catch (_) {}
  }

  Future<File> _coverFile() async {
    final docs = await getApplicationDocumentsDirectory();
    final dir = Directory('${docs.path}${Platform.pathSeparator}iAquaria');
    if (!dir.existsSync()) dir.createSync(recursive: true);
    return File(
        '${dir.path}${Platform.pathSeparator}cam_last_${widget.camBase.hashCode.abs()}.jpg');
  }

  @override
  Widget build(BuildContext context) {
    // 云端查看模式（含切换中）：局域网摄像头不可达，显示 ESP32-CAM 定时上传的云照片
    final store = AppStore.instance;
    if (store.isCloudLink) {
      final photo = store.cloudPhoto;
      final at = store.cloudPhotoAt;
      if (photo != null) {
        return Container(
          margin: const EdgeInsets.only(bottom: 8),
          decoration: BoxDecoration(
            color: Colors.black,
            borderRadius: BorderRadius.circular(14),
            border: Border.all(color: const Color(0xFFe2e8f0)),
          ),
          clipBehavior: Clip.antiAlias,
          child: Stack(alignment: Alignment.bottomLeft, children: [
            AspectRatio(
              aspectRatio: 4 / 3,
              child:
                  Image.memory(photo, gaplessPlayback: true, fit: BoxFit.cover),
            ),
            Positioned(
              top: 6,
              left: 6,
              child: Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                decoration: BoxDecoration(
                  color: Colors.black.withOpacity(.45),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Text(
                  '云端照片 ${at != null ? "${at.hour.toString().padLeft(2, "0")}:${at.minute.toString().padLeft(2, "0")}" : ""}',
                  style: const TextStyle(color: Colors.white, fontSize: 11),
                ),
              ),
            ),
          ]),
        );
      }
      return Container(
        margin: const EdgeInsets.only(bottom: 8),
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
        decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.circular(10),
          border: Border.all(color: const Color(0xFFe2e8f0)),
        ),
        child: Row(children: [
          const Icon(Icons.cloud_outlined, size: 16, color: Colors.indigo),
          const SizedBox(width: 8),
          Text(
              store.linkState == 'cloud'
                  ? '云端模式：等待摄像头定时上传的照片…'
                  : store.linkState.startsWith('cloud-error')
                      ? '云端连接失败，20 秒后自动重试…'
                      : store.linkState.startsWith('cloud-nodata')
                          ? '云端已连接但未收到设备数据，请核对云查看设备 ID…'
                          : '正在切换云端查看…',
              style: const TextStyle(fontSize: 12, color: AppTheme.muted)),
        ]),
      );
    }
    // ───── 封面态（默认）：不拉流，显示最近一帧（内存/磁盘缓存） ─────
    if (!_playing) {
      final frame = _frameCache[widget.camBase];
      final at = _frameCacheAt[widget.camBase];
      final offline = _state == _CamState.offline;
      final stamp = at != null
          ? '${at.hour.toString().padLeft(2, "0")}:${at.minute.toString().padLeft(2, "0")}'
          : '';
      return Container(
        margin: const EdgeInsets.only(bottom: 8),
        decoration: BoxDecoration(
          color: Colors.black,
          borderRadius: BorderRadius.circular(14),
          border: Border.all(color: const Color(0xFFe2e8f0)),
        ),
        clipBehavior: Clip.antiAlias,
        child: Stack(alignment: Alignment.bottomLeft, children: [
          AspectRatio(
            aspectRatio: 4 / 3,
            child: frame != null
                ? Image.memory(frame, gaplessPlayback: true, fit: BoxFit.cover)
                : const Center(
                    child: Column(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Icon(Icons.videocam_off_outlined,
                            size: 36, color: Colors.white38),
                        SizedBox(height: 8),
                        Text('点右上角 ▶ 查看实时画面',
                            style:
                                TextStyle(color: Colors.white54, fontSize: 12)),
                      ],
                    ),
                  ),
          ),
          if (frame != null)
            Positioned(
              bottom: 6,
              left: 6,
              child: Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                decoration: BoxDecoration(
                  color: Colors.black.withOpacity(.45),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Text(
                  offline ? '摄像头不在线（点击播放重试）$stamp' : '画面 $stamp（暂停中）',
                  style: const TextStyle(color: Colors.white70, fontSize: 11),
                ),
              ),
            ),
          Positioned(
            top: 6,
            right: 6,
            child: GestureDetector(
              onTap: _start,
              child: Container(
                padding: const EdgeInsets.all(6),
                decoration: BoxDecoration(
                  color: Colors.black.withOpacity(.45),
                  borderRadius: BorderRadius.circular(8),
                ),
                child:
                    const Icon(Icons.play_arrow, color: Colors.white, size: 18),
              ),
            ),
          ),
        ]),
      );
    }
    // ───── 播放中：实时流 ─────
    return Container(
      margin: const EdgeInsets.only(bottom: 8),
      decoration: BoxDecoration(
        color: Colors.black,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: const Color(0xFFe2e8f0)),
      ),
      clipBehavior: Clip.antiAlias,
      child: Stack(alignment: Alignment.bottomCenter, children: [
        AspectRatio(
          aspectRatio: 4 / 3,
          child: _frameCache[widget.camBase] != null
              ? Image.memory(_frameCache[widget.camBase]!,
                  gaplessPlayback: true, fit: BoxFit.cover)
              : const Center(
                  child: Text('连接中…',
                      style: TextStyle(color: Colors.white70, fontSize: 12))),
        ),
        Positioned(
          top: 6,
          right: 6,
          child: GestureDetector(
            onTap: _stop,
            child: Container(
              padding: const EdgeInsets.all(6),
              decoration: BoxDecoration(
                color: Colors.black.withOpacity(.45),
                borderRadius: BorderRadius.circular(8),
              ),
              child: const Icon(Icons.pause, color: Colors.white, size: 18),
            ),
          ),
        ),
      ]),
    );
  }
}

class _CamPlaceholder extends StatelessWidget {
  const _CamPlaceholder({required this.hint});
  final String hint;

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.only(bottom: 8),
      height: 120,
      alignment: Alignment.center,
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: const Color(0xFFe2e8f0)),
      ),
      child: Text(hint,
          textAlign: TextAlign.center,
          style: const TextStyle(fontSize: 12, color: AppTheme.muted)),
    );
  }
}

class _CardData {
  const _CardData(this.label, this.value, this.unit);
  final String label;
  final double? value;
  final String unit;
}

class _StateBar extends StatelessWidget {
  const _StateBar({required this.state, this.onTap});
  final String state;
  final VoidCallback? onTap; // 点击状态条：立即刷新链路（重探直连/重订云端/拉快照）

  /// 状态样式（Dart 2.19 无 records/switch 表达式，返回 List 两元素）
  static List _stateStyle(String s) {
    if (s.startsWith('cloud-error')) {
      // cloud-error|<真实失败原因>：把 MQTT 报错直接亮在状态条上便于远程定位
      final detail = s.split('|').length > 1 ? s.split('|')[1] : '';
      final msg = detail.isEmpty
          ? '云端连接失败（检查设置页云查看配置），20 秒后自动重试'
          : '云端连接失败：$detail（20 秒后自动重试）';
      return [Colors.deepOrange, msg];
    }
    if (s.startsWith('cloud-nodata')) {
      // cloud-nodata|<提示>：Broker 已连上但订阅主题内无数据（多为云查看 ID 填错）
      final detail = s.split('|').length > 1 ? s.split('|')[1] : '';
      return [Colors.amber.shade800, detail.isEmpty ? '云端已连接但未收到设备数据' : detail];
    }
    switch (s) {
      case 'connected':
        return [AppTheme.tealDark, '设备已连接'];
      case 'cloud':
        return [Colors.indigo, '云端查看中（局域网外 · 只读）'];
      case 'cloud-connecting':
        return [Colors.indigo, '局域网不可达，正在切换云端查看…'];
      case 'connecting':
        return [Colors.orange, '设备连接中…'];
      case 'error':
        return [AppTheme.danger, '设备连接失败（检查鱼缸页的设备 IP 与同网 WiFi）'];
      case 'manual':
        return [Colors.blueGrey, '手动管理缸（无设备数据源，可人工记录）'];
      default:
        return [AppTheme.muted, '设备未连接'];
    }
  }

  @override
  Widget build(BuildContext context) {
    final style = _stateStyle(state);
    final color = style[0] as Color;
    final text = style[1] as String;
    return GestureDetector(
      onTap: onTap,
      child: Container(
        margin: const EdgeInsets.only(bottom: 8),
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
        decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.circular(10),
          border: Border.all(color: const Color(0xFFe2e8f0)),
        ),
        child: Row(children: [
          Icon(Icons.circle, size: 9, color: color),
          const SizedBox(width: 8),
          Expanded(
            // 长文案（云端失败含 OS 级原因）允许 4 行省略，避免溢出
            child: Text(text,
                maxLines: 4,
                overflow: TextOverflow.ellipsis,
                style: TextStyle(fontSize: 12, color: color)),
          ),
          const SizedBox(width: 8),
          // 刷新按钮：点击立即重探当前链路（不等周期重连/重订定时器）
          const Icon(Icons.refresh, size: 16, color: AppTheme.muted),
          // 构建号：核对手机实际运行版本（修复版应显示 b3 或更高）
          const Text(kAppVerLabel,
              style: TextStyle(fontSize: 9.5, color: AppTheme.muted)),
        ]),
      ),
    );
  }
}

class _MetricCard extends StatelessWidget {
  const _MetricCard({required this.data});
  final _CardData data;

  String get _value {
    final v = data.value;
    if (v == null) return '--';
    if (v >= 100) return v.toStringAsFixed(0);
    return v.toStringAsFixed(2);
  }

  @override
  Widget build(BuildContext context) {
    final offline = data.value == null;
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: const Color(0xFFe2e8f0)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(data.label,
              style: const TextStyle(fontSize: 12, color: AppTheme.muted)),
          const SizedBox(height: 6),
          Row(
            crossAxisAlignment: CrossAxisAlignment.end,
            children: [
              Text(_value,
                  style: TextStyle(
                    fontSize: 22,
                    fontWeight: FontWeight.w800,
                    color: offline ? Colors.grey.shade400 : AppTheme.tealDark,
                  )),
              if (data.unit.isNotEmpty)
                Padding(
                  padding: const EdgeInsets.only(left: 4, bottom: 2),
                  child: Text(data.unit,
                      style: TextStyle(
                          fontSize: 11,
                          color:
                              offline ? Colors.grey.shade400 : AppTheme.muted)),
                ),
            ],
          ),
        ],
      ),
    );
  }
}
