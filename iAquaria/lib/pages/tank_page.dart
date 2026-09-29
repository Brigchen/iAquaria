/// 鱼缸页：缸档案卡（设备 IP / 摄像头 / 删除）+ 添加新缸表单。
library;

import 'package:flutter/material.dart';

import '../app.dart';
import '../core/metrics.dart';
import '../core/theme.dart';
import '../models/tank.dart';
import '../services/device_service.dart';
import 'device_config_page.dart';

class TankPage extends StatefulWidget {
  const TankPage({super.key});

  @override
  State<TankPage> createState() => _TankPageState();
}

class _TankPageState extends State<TankPage> {
  Tank? _editTarget; // 当前编辑中的缸（档案卡"编辑"按钮触发）

  @override
  Widget build(BuildContext context) {
    final store = AppStore.instance;
    return AnimatedBuilder(
      animation: store,
      builder: (context, _) {
        final t = store.activeTank;
        return ListView(
          padding: const EdgeInsets.all(14),
          children: [
            if (t != null) _facts(context, t),
            const SizedBox(height: 10),
            if (_editTarget != null) _editCard(context, _editTarget!),
            _addCard(context),
            const SizedBox(height: 80),
          ],
        );
      },
    );
  }

  Widget _editCard(BuildContext context, Tank t) {
    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppTheme.tealLight.withOpacity(.25),
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: AppTheme.teal.withOpacity(.4)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('编辑「${t.name}」',
              style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w800)),
          const SizedBox(height: 4),
          const Text('修改 IP / 摄像头 / 云查看主题等，保存后自动重连设备。',
              style: TextStyle(fontSize: 11.5, color: AppTheme.muted)),
          const SizedBox(height: 12),
          _AddTankForm(
            editing: t,
            onAdded: () => setState(() => _editTarget = null),
          ),
          const SizedBox(height: 4),
          Align(
            alignment: Alignment.centerRight,
            child: TextButton(
              onPressed: () => setState(() => _editTarget = null),
              child: const Text('取消编辑'),
            ),
          ),
        ],
      ),
    );
  }

  Widget _facts(BuildContext context, Tank t) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: const Color(0xFFe2e8f0)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Expanded(
                child: Text(t.name,
                    style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w800)),
              ),
              // 操作按钮：右上角（Wrap 窄屏自动换行，不溢出）
              Wrap(
                spacing: 4,
                runSpacing: 0,
                alignment: WrapAlignment.end,
                children: [
                  TextButton.icon(
                    style: TextButton.styleFrom(foregroundColor: AppTheme.tealDark),
                    icon: const Icon(Icons.tune, size: 18),
                    label: const Text('自动运行', style: TextStyle(fontSize: 12.5)),
                    onPressed: () {
                      Navigator.of(context).push(MaterialPageRoute(
                        builder: (_) => DeviceConfigPage(tank: t),
                      ));
                    },
                  ),
                  TextButton.icon(
                    style: TextButton.styleFrom(foregroundColor: AppTheme.tealDark),
                    icon: const Icon(Icons.edit_outlined, size: 18),
                    label: const Text('编辑', style: TextStyle(fontSize: 12.5)),
                    onPressed: () => setState(() => _editTarget = t),
                  ),
                  TextButton.icon(
                    style: TextButton.styleFrom(foregroundColor: AppTheme.danger),
                    icon: const Icon(Icons.delete_outline, size: 18),
                    label: const Text('删除', style: TextStyle(fontSize: 12.5)),
                    onPressed: () => _confirmDelete(context, t),
                  ),
                ],
              ),
            ],
          ),
          const SizedBox(height: 12),
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              _fact('容量', t.capacityL > 0 ? '${t.capacityL} 升' : '--'),
              _fact('水型', t.waterType),
              _fact('位置', t.location.isEmpty ? '--' : t.location),
            ],
          ),
          const SizedBox(height: 12),
          // 水型对应的传感器配置说明
          Text(Metrics.sensorHint(t.waterType),
              style: const TextStyle(fontSize: 11.5, color: AppTheme.muted)),
          const SizedBox(height: 4),
          Text('设备 IP：${t.esp32Ip.isEmpty ? "未配置（数据无法获取）" : t.esp32Ip} · 摄像头：${t.camUrl.isEmpty ? "未配置" : t.camUrl}',
              style: const TextStyle(fontSize: 11.5, color: AppTheme.muted)),
        ],
      ),
    );
  }

  Future<void> _confirmDelete(BuildContext context, Tank t) async {
    final ok = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('删除鱼缸'),
        content: Text('确定删除「${t.name}」吗？仅删除 App 内档案，设备本身不受影响。'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('取消')),
          FilledButton(
            style: FilledButton.styleFrom(backgroundColor: AppTheme.danger),
            onPressed: () => Navigator.pop(ctx, true),
            child: const Text('删除'),
          ),
        ],
      ),
    );
    if (ok == true) await AppStore.instance.deleteTank(t);
  }

  Widget _fact(String k, String v) => Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(k, style: const TextStyle(fontSize: 11, color: AppTheme.muted)),
          const SizedBox(height: 2),
          Text(v, style: const TextStyle(fontSize: 14, fontWeight: FontWeight.bold)),
        ],
      );

  Widget _addCard(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: const Color(0xFFe2e8f0)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text('添加新缸', style: TextStyle(fontSize: 15, fontWeight: FontWeight.w800)),
          const SizedBox(height: 4),
          const Text('每缸对应一台 ESP32 主板：填写 IP 则直连设备取数；留空则创建手动管理缸（人工记录 / 周期提醒）。',
              style: TextStyle(fontSize: 11.5, color: AppTheme.muted)),
          const SizedBox(height: 12),
          _AddTankForm(onAdded: () => setState(() {})),
        ],
      ),
    );
  }
}

/// 添加/编辑缸表单：名称/设备 IP（可选）/位置/容量/水型/摄像头/云查看主题。
/// editing 非空 = 编辑模式：预填档案，保存走 updateTank（校验排除自身）。
class _AddTankForm extends StatefulWidget {
  const _AddTankForm({required this.onAdded, this.editing});
  final VoidCallback onAdded;
  final Tank? editing;

  @override
  State<_AddTankForm> createState() => _AddTankFormState();
}

class _AddTankFormState extends State<_AddTankForm> {
  final _name = TextEditingController();
  final _ip = TextEditingController();
  final _location = TextEditingController();
  final _capacity = TextEditingController();
  final _cam = TextEditingController();
  final _cloudTopic = TextEditingController();
  String _waterType = Tank.waterFresh;
  String? _nameErr;
  String? _ipErr;

  Tank? get _editing => widget.editing;
  bool get _isEdit => _editing != null;

  static final _ipRe = RegExp(r'^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$');

  @override
  void initState() {
    super.initState();
    final e = _editing;
    if (e != null) {
      _name.text = e.name;
      _ip.text = e.esp32Ip;
      _location.text = e.location;
      _capacity.text = e.capacityL > 0 ? '${e.capacityL}' : '';
      _cam.text = e.camUrl;
      _cloudTopic.text = e.cloudTopic.replaceFirst(RegExp('^iaquaria/'), '');
      _waterType = e.waterType;
    } else if (_ip.text.isEmpty) {
      // 添加模式：设备在线时自动带出云 ID（表单打开晚于握手，cfg 已缓存）
      final devId =
          DeviceService.instance.lastCfg?['cloud']?['dev_id'] as String?;
      if (devId != null && devId.isNotEmpty) _cloudTopic.text = devId;
    }
  }

  @override
  void dispose() {
    _name.dispose();
    _ip.dispose();
    _location.dispose();
    _capacity.dispose();
    _cam.dispose();
    _cloudTopic.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    final store = AppStore.instance;
    final name = _name.text.trim();
    final ip = _ip.text.trim();
    var nameErr = _validateName(store, name);
    var ipErr = _validateIp(store, ip);
    setState(() {
      _nameErr = nameErr;
      _ipErr = ipErr;
    });
    if (nameErr != null || ipErr != null) return;

    if (_isEdit) {
      final e = _editing!;
      await store.updateTank(e.copyWith(
        name: name,
        esp32Ip: ip,
        location: _location.text.trim(),
        capacityL: int.tryParse(_capacity.text.trim()) ?? 0,
        waterType: _waterType,
        camUrl: _cam.text.trim(),
        cloudTopic: _fmtCloudTopic(_cloudTopic.text),
      ));
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(
          content: Text('「$name」已更新${ip.isEmpty ? "（手动管理）" : "，正在连接 $ip …"}'),
        ));
      }
      widget.onAdded();
      return;
    }

    final id = 'tank_${DateTime.now().millisecondsSinceEpoch}';
    await store.addTank(Tank(
      id: id,
      name: name,
      esp32Ip: ip, // 可为空：手动管理缸（人工记录/周期提醒，无设备数据源）
      location: _location.text.trim(),
      capacityL: int.tryParse(_capacity.text.trim()) ?? 0,
      waterType: _waterType,
      camUrl: _cam.text.trim(),
      cloudTopic: _fmtCloudTopic(_cloudTopic.text),
    ));
    _name.clear();
    _ip.clear();
    _location.clear();
    _capacity.clear();
    _cam.clear();
    _cloudTopic.clear();
    if (mounted) {
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(
        content: Text(ip.isEmpty ? '已创建「$name」（手动管理）' : '已创建「$name」，正在连接 $ip …'),
      ));
    }
    widget.onAdded();
  }

  String? _validateName(AppStore store, String name) {
    if (name.isEmpty) return '请填写缸名称';
    if (store.tanks.any((t) => t.name == name && t.id != _editing?.id)) {
      return '已存在同名鱼缸，请换一个名字';
    }
    return null;
  }

  /// 云查看设备 ID → MQTT 主题：用户只填 iaqua-83d4，App 拼接 iaquaria/ 前缀
  String _fmtCloudTopic(String raw) {
    final id = raw.trim();
    if (id.isEmpty) return '';
    return id.startsWith('iaquaria/') ? id : 'iaquaria/$id';
  }

  /// IP 可选：留空创建手动管理缸；填写时校验格式与重复绑定
  String? _validateIp(AppStore store, String ip) {
    if (ip.isEmpty) return null;
    final m = _ipRe.firstMatch(ip);
    if (m == null) return '格式应为 192.168.x.x，留空则创建手动管理缸';
    for (final g in m.groups([1, 2, 3, 4])) {
      if (int.parse(g!) > 255) return '格式应为 192.168.x.x';
    }
    if (store.tanks.any((t) => t.esp32Ip == ip && t.id != _editing?.id)) {
      return '该设备 IP 已被其他鱼缸使用';
    }
    return null;
  }

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(children: [
          Expanded(child: _field('缸名称', _name, hint: '如：客厅缸', error: _nameErr, required: true)),
          const SizedBox(width: 8),
          Expanded(child: _field('位置', _location, hint: '客厅 · 南侧')),
        ]),
        _field('ESP32 主板 IP', _ip, hint: '如 192.168.3.190，留空为手动管理缸', error: _ipErr,
            keyboardType: const TextInputType.numberWithOptions(decimal: true)),
        _field('容量（升）', _capacity,
            keyboardType: const TextInputType.numberWithOptions()),
        // ── 水型选择：海水缸 → 盐度探头；淡水/草缸 → TDS 双通道 ──
        const Text('水型', style: TextStyle(fontSize: 12, color: AppTheme.muted)),
        const SizedBox(height: 6),
        Row(
          children: [Tank.waterFresh, Tank.waterSalt, Tank.waterPlanted]
              .map((wt) => Expanded(
                    child: Padding(
                      padding: const EdgeInsets.only(right: 8),
                      child: ChoiceChip(
                        label: Center(child: Text(wt, style: const TextStyle(fontSize: 12.5))),
                        selected: _waterType == wt,
                        selectedColor: AppTheme.tealLight,
                        labelPadding: const EdgeInsets.symmetric(horizontal: 12),
                        onSelected: (_) => setState(() => _waterType = wt),
                      ),
                    ),
                  ))
              .toList(),
        ),
        const SizedBox(height: 6),
        Text(Metrics.sensorHint(_waterType),
            style: const TextStyle(fontSize: 11.5, color: AppTheme.muted)),
        _field('摄像头地址', _cam, hint: 'http://192.168.3.191（独立设备）'),
        _field('云查看设备 ID', _cloudTopic,
            hint: '如 iaqua-84d4（出门在外远程看数据；设备在线时已自动读取）'),
        const SizedBox(height: 12),
        FilledButton(
          style: FilledButton.styleFrom(backgroundColor: AppTheme.tealDark),
          onPressed: _submit,
          child: Text(_isEdit ? '保存修改' : '保存并创建'),
        ),
      ],
    );
  }

  Widget _field(String label, TextEditingController c,
      {String hint = '', String? error, TextInputType? keyboardType,
      bool required = false}) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: TextField(
        controller: c,
        keyboardType: keyboardType,
        decoration: InputDecoration(
          label: required
              ? Text.rich(TextSpan(text: label, children: const [
                  TextSpan(text: ' *', style: TextStyle(color: Colors.red)),
                ]))
              : Text(label),
          hintText: hint,
          isDense: true,
          errorText: error,
          border: const OutlineInputBorder(),
        ),
      ),
    );
  }
}
