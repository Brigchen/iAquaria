/// 设备自动运行阈值设置页（每缸）：
/// 通过 WS 直连设备读写 ctrl.* 配置（cfg 帧 / cfg.setMany 命令），
/// 覆盖加温、CO2（草缸）、灯光、补水四类自动控制。
library;

import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../app.dart';
import '../core/theme.dart';
import '../models/tank.dart';
import '../services/device_service.dart';

class DeviceConfigPage extends StatefulWidget {
  const DeviceConfigPage({super.key, required this.tank});
  final Tank tank;

  @override
  State<DeviceConfigPage> createState() => _DeviceConfigPageState();
}

class _DeviceConfigPageState extends State<DeviceConfigPage> {
  final _dev = DeviceService.instance;
  final _numCtrl = <String, TextEditingController>{};
  final _timeCtrl = <String, TextEditingController>{};

  Map<String, dynamic>? _cfg;
  bool _saving = false;
  bool _filled = false;
  StreamSubscription<Map<String, dynamic>>? _cfgSub;
  StreamSubscription<Map<String, dynamic>>? _ackSub;

  // ── 配置路径 → 显示信息（label/hint/单位）──
  static const _numFields = <String, List<String>>{
    'ctrl.heater.sp_c': ['目标温度', '低于「目标-回差」开、达到「目标」关', '℃'],
    'ctrl.heater.hyst_c': ['回差温度', '防止频繁启停', '℃'],
    'ctrl.heater.max_on_min': ['最长连续运行', '超时强制断开保护', '分钟'],
    'ctrl.co2.ph_on': ['pH 开启上限', 'pH ≥ 此值时开 CO2', ''],
    'ctrl.co2.ph_off': ['pH 关闭下限', 'pH ≤ 此值时关 CO2', ''],
    'ctrl.co2.max_on_min': ['最长连续运行', '超时强制断开保护', '分钟'],
    'ctrl.light.lux_on': ['开灯光照', '光照 ≤ 此值时开灯（光感模式）', 'lx'],
    'ctrl.light.lux_off': ['关灯光照', '光照 ≥ 此值时关灯（光感模式）', 'lx'],
    'ctrl.pump.lvl_on': ['开泵水位', '水位 ≤ 此值时补水', '%'],
    'ctrl.pump.lvl_off': ['关泵水位', '水位 ≥ 此值时停止补水', '%'],
  };

  @override
  void initState() {
    super.initState();
    _prepare();
  }

  Future<void> _prepare() async {
    // 配置哪缸看哪缸：非活动缸先切换（触发对应设备连接）
    final store = AppStore.instance;
    if (store.activeTank?.id != widget.tank.id) {
      await store.switchTank(widget.tank);
    }
    _cfgSub = _dev.config.listen(_onCfg);
    _ackSub = _dev.ack.listen((a) {
      if (!mounted) return;
      final ok = a['ok'] == true;
      _toast(ok ? '已保存到设备' : '保存失败：${a['msg'] ?? '未知错误'}');
      if (ok) setState(() => _saving = false);
    });
    if (widget.tank.esp32Ip.trim().isNotEmpty) {
      _dev.requestCfg();
    }
  }

  void _onCfg(Map<String, dynamic> cfg) {
    if (!mounted || _filled) return; // 首帧填充，之后不打断用户编辑
    _cfg = cfg;
    _fillControllers();
    setState(() => _filled = true);
  }

  T? _get<T>(String path) {
    final c = _cfg;
    if (c == null) return null;
    dynamic cur = c;
    for (final seg in path.split('.')) {
      if (cur is! Map) return null;
      cur = cur[seg];
    }
    return cur is T ? cur : null;
  }

  void _fillControllers() {
    _numFields.forEach((path, meta) {
      final v = _get<num>(path);
      _ctrl(path).text = v == null ? '' : _trimNum(v.toDouble());
    });
    final on = _get<String>('ctrl.light.on');
    final off = _get<String>('ctrl.light.off');
    if (on != null) _ctrl('ctrl.light.on').text = on;
    if (off != null) _ctrl('ctrl.light.off').text = off;
  }

  TextEditingController _ctrl(String path) =>
      _numCtrl.putIfAbsent(path, () => TextEditingController());

  static String _trimNum(double v) =>
      v == v.roundToDouble() ? v.toStringAsFixed(0) : v.toStringAsFixed(1);

  @override
  void dispose() {
    _cfgSub?.cancel();
    _ackSub?.cancel();
    for (final c in _numCtrl.values) {
      c.dispose();
    }
    for (final c in _timeCtrl.values) {
      c.dispose();
    }
    super.dispose();
  }

  void _toast(String s) {
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(s)));
  }

  Future<void> _save() async {
    if (_cfg == null) {
      _toast('设备配置尚未加载');
      return;
    }
    if (widget.tank.esp32Ip.trim().isEmpty) {
      _toast('手动管理缸无设备，无法设置');
      return;
    }
    final sets = <Map<String, dynamic>>[];
    // 开关与模式项（Switch/Segment 值存在 _cfg 内）
    for (final p in ['ctrl.co2.follow_light', 'ctrl.pump.auto_en', 'ctrl.light.mode']) {
      final v = _get<bool>(p) ?? _get<String>(p);
      if (v != null) sets.add({'path': p, 'value': v});
    }
    // 数值项
    _numFields.forEach((path, meta) {
      final raw = _ctrl(path).text.trim();
      if (raw.isEmpty) return;
      final v = double.tryParse(raw);
      if (v == null) return;
      // 整数值按 int 下发（设备配置类型敏感：bool/int/float）
      sets.add({'path': path, 'value': v == v.roundToDouble() ? v.toInt() : v});
    });
    // 灯光定时（仅定时模式时下发）
    final mode = _get<String>('ctrl.light.mode') ?? 'lux';
    if (mode != 'lux') {
      for (final p in ['ctrl.light.on', 'ctrl.light.off']) {
        final raw = _ctrl(p).text.trim();
        if (RegExp(r'^\d{2}:\d{2}$').hasMatch(raw)) {
          sets.add({'path': p, 'value': raw});
        }
      }
    }
    if (sets.isEmpty) {
      _toast('没有需要保存的修改');
      return;
    }
    setState(() => _saving = true);
    _dev.setCfgMany(_dev.rev, sets);
  }

  @override
  Widget build(BuildContext context) {
    final noDevice = widget.tank.esp32Ip.trim().isEmpty;
    return Scaffold(
      appBar: AppBar(title: Text('自动运行设置 · ${widget.tank.name}')),
      body: noDevice
          ? const Center(
              child: Text('该缸为手动管理缸（无设备），无法设置自动运行。',
                  style: TextStyle(fontSize: 13, color: AppTheme.muted)))
          : _cfg == null
              ? const Center(child: CircularProgressIndicator())
              : ListView(
                  padding: const EdgeInsets.all(14),
                  children: [
                    _card('加温（加热棒）', [
                      _num('ctrl.heater.sp_c'),
                      _num('ctrl.heater.hyst_c'),
                      _num('ctrl.heater.max_on_min'),
                    ]),
                    _card('CO2（草缸电磁阀）', [
                      _switch('ctrl.co2.follow_light', '跟随灯光联动',
                          '灯光关闭时强制关闭 CO2'),
                      _num('ctrl.co2.ph_on'),
                      _num('ctrl.co2.ph_off'),
                      _num('ctrl.co2.max_on_min'),
                    ]),
                    _card('灯光（水族灯）', [
                      _lightMode(),
                      _num('ctrl.light.lux_on'),
                      _num('ctrl.light.lux_off'),
                      _time('ctrl.light.on', '定时开灯 HH:mm'),
                      _time('ctrl.light.off', '定时关灯 HH:mm'),
                    ]),
                    _card('补水（补水泵）', [
                      _switch('ctrl.pump.auto_en', '自动补水',
                          '按水位回差自动启停（需超声波水位传感器）'),
                      _num('ctrl.pump.lvl_on'),
                      _num('ctrl.pump.lvl_off'),
                    ]),
                    const SizedBox(height: 6),
                    FilledButton(
                      style: FilledButton.styleFrom(
                          backgroundColor: AppTheme.tealDark,
                          padding: const EdgeInsets.symmetric(vertical: 13)),
                      onPressed: _saving ? null : _save,
                      child: Text(_saving ? '保存中…' : '保存全部设置到设备'),
                    ),
                    const SizedBox(height: 20),
                  ],
                ),
    );
  }

  Widget _card(String title, List<Widget> children) {
    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: const Color(0xFFe2e8f0)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(title,
              style: const TextStyle(fontSize: 13.5, fontWeight: FontWeight.w700)),
          const SizedBox(height: 10),
          ...children,
        ],
      ),
    );
  }

  Widget _num(String path) {
    final meta = _numFields[path]!;
    return Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(children: [
            Text(meta[0], style: const TextStyle(fontSize: 12.5)),
            if (meta[2].isNotEmpty)
              Text('（${meta[2]}）',
                  style: const TextStyle(fontSize: 11, color: AppTheme.muted)),
          ]),
          const SizedBox(height: 4),
          TextField(
            controller: _ctrl(path),
            keyboardType:
                const TextInputType.numberWithOptions(decimal: true, signed: false),
            inputFormatters: [
              FilteringTextInputFormatter.allow(RegExp(r'^-?\d*\.?\d*$')),
            ],
            decoration: InputDecoration(
              isDense: true,
              hintText: meta[1],
              hintStyle: const TextStyle(fontSize: 11, color: AppTheme.muted),
              border: const OutlineInputBorder(),
            ),
          ),
        ],
      ),
    );
  }

  Widget _time(String path, String label) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('$label（定时模式生效）',
              style: const TextStyle(fontSize: 12.5)),
          const SizedBox(height: 4),
          TextField(
            controller: _ctrl(path),
            keyboardType: TextInputType.datetime,
            inputFormatters: [
              FilteringTextInputFormatter.allow(RegExp(r'[\d:]')),
            ],
            decoration: const InputDecoration(
              isDense: true,
              hintText: '如 08:00',
              border: OutlineInputBorder(),
            ),
          ),
        ],
      ),
    );
  }

  Widget _lightMode() {
    final mode = _get<String>('ctrl.light.mode') ?? 'lux';
    return Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text('控制模式', style: TextStyle(fontSize: 12.5)),
          const SizedBox(height: 4),
          Row(children: [
            _modeBtn('lux', mode, '光感自动', 'ctrl.light.mode'),
            const SizedBox(width: 8),
            _modeBtn('timer', mode, '定时开关', 'ctrl.light.mode'),
          ]),
        ],
      ),
    );
  }

  Widget _modeBtn(String val, String cur, String label, String path) {
    final sel = cur == val;
    return Expanded(
      child: GestureDetector(
        onTap: () => setState(() {
          final c = _cfg!;
          final segs = path.split('.');
          (c[segs[0]] as Map)[segs[1]][segs[2]] = val;
        }),
        child: Container(
          padding: const EdgeInsets.symmetric(vertical: 7),
          decoration: BoxDecoration(
            color: sel ? AppTheme.tealDark : const Color(0xFFf1f5f9),
            borderRadius: BorderRadius.circular(8),
          ),
          alignment: Alignment.center,
          child: Text(label,
              style: TextStyle(
                  fontSize: 12,
                  color: sel ? Colors.white : AppTheme.muted,
                  fontWeight: sel ? FontWeight.w700 : FontWeight.w400)),
        ),
      ),
    );
  }

  Widget _switch(String path, String label, String hint) {
    final v = _get<bool>(path) ?? false;
    return Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: Row(children: [
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(label, style: const TextStyle(fontSize: 12.5)),
              Text(hint,
                  style: const TextStyle(fontSize: 10.5, color: AppTheme.muted)),
            ],
          ),
        ),
        Switch(
          value: v,
          activeColor: AppTheme.tealDark,
          onChanged: (nv) => setState(() {
            final segs = path.split('.');
            (_cfg![segs[0]] as Map)[segs[1]][segs[2]] = nv;
          }),
        ),
      ]),
    );
  }
}
