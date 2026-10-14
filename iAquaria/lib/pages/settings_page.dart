/// 设置页：LLM 服务配置（密钥仅存本机）+ 设备连接说明 + 平台信息。
library;

import 'package:flutter/material.dart';

import '../core/platform_utils.dart';
import '../core/theme.dart';
import '../core/version.dart';
import '../app.dart';
import '../services/demo_data_service.dart';
import '../services/storage_service.dart';
import '../services/sync_service.dart';

class SettingsPage extends StatefulWidget {
  const SettingsPage({super.key});

  @override
  State<SettingsPage> createState() => _SettingsPageState();
}

/// 快捷预设：服务商 → [接口地址, 默认模型名]（2026-09 核对，多模态优先）
const _llmPresets = <String, List<String>>{
  '通义千问': [
    'https://llm-54er3r3q5452ofct.cn-beijing.maas.aliyuncs.com/compatible-mode/v1',
    'qwen3.8-flash'
  ],
  '智谱GLM': ['https://open.bigmodel.cn/api/paas/v4', 'glm-5.3-flash'],
  '豆包': [
    'https://ark.cn-beijing.volces.com/api/v3',
    'doubao-seed-2-1-pro-260628'
  ],
  'DeepSeek': ['https://api.deepseek.com', 'deepseek-flash'],
  'Kimi': ['https://api.moonshot.cn/v1', 'kimi-k3'],
};

class _SettingsPageState extends State<SettingsPage> {
  final _keyCtrl = TextEditingController();
  final _baseUrlCtrl = TextEditingController();
  final _modelCtrl = TextEditingController();
  bool _syncEnabled = true; // 日志与计划云同步开关（默认开）
  bool _demoOn = false; // 演示模式（示例数据 + 模拟遥测）
  final _cloudHostCtrl = TextEditingController();
  final _cloudPortCtrl = TextEditingController();
  final _cloudUserCtrl = TextEditingController();
  final _cloudPassCtrl = TextEditingController();

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    final st = StorageService.instance;
    _keyCtrl.text = await st.llmApiKey();
    _baseUrlCtrl.text = await st.llmBaseUrl();
    _modelCtrl.text = await st.llmModel();
    _cloudHostCtrl.text = await st.cloudHost();
    final port = await st.cloudPort();
    _cloudPortCtrl.text = port > 0 ? '$port' : '';
    _cloudUserCtrl.text = await st.cloudUser();
    _cloudPassCtrl.text = await st.cloudPass();
    _syncEnabled = await SyncService.instance.enabled();
    _demoOn = await DemoDataService.instance.enabled();
    if (mounted) setState(() {});
  }

  /// 演示模式开关：确认后播种示例数据 + 模拟遥测
  Future<void> _toggleDemo(bool v) async {
    if (v && AppStore.instance.activeTank == null) {
      _toast('请先在「鱼缸」Tab 添加并选择鱼缸');
      return;
    }
    if (v) {
      final ok = await showDialog<bool>(
        context: context,
        builder: (ctx) => AlertDialog(
          title: const Text('开启演示模式？'),
          content: const Text('将向当前缸写入示例养护日志、周期计划与生物清单'
              '（仅在对应内容为空时写入，不覆盖已有记录），并每 10 秒模拟一帧'
              '遥测让概览数据动起来。\n\n关闭后停止模拟遥测；已写入的记录保留，'
              '日志可长按删除。'),
          actions: [
            TextButton(
                onPressed: () => Navigator.pop(ctx, false),
                child: const Text('取消')),
            FilledButton(
                style:
                    FilledButton.styleFrom(backgroundColor: AppTheme.tealDark),
                onPressed: () => Navigator.pop(ctx, true),
                child: const Text('开启')),
          ],
        ),
      );
      if (ok != true) return;
    }
    setState(() => _demoOn = v);
    await DemoDataService.instance.setEnabled(v);
    _toast(v ? '演示数据已写入当前缸，模拟遥测已开启' : '已关闭演示模式（已写入的记录保留，日志长按可删）');
  }

  /// 日志与计划云同步开关
  Future<void> _toggleSync(bool v) async {
    setState(() => _syncEnabled = v);
    await SyncService.instance.setEnabled(v);
    _toast(v ? '云同步已开启：云端在线时自动双向合并' : '云同步已关闭：数据仅存本机');
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('设置')),
      body: ListView(
        padding: const EdgeInsets.all(14),
        children: [
          // ── AI 服务（LLM）─────────────────────
          const _SectionTitle('AI 服务（兼容 OpenAI 协议）'),
          _card([
            // 快捷预设：点选自动填接口地址与模型名，只需再填 Key
            const Text('快捷预设（点选自动填充）',
                style: TextStyle(fontSize: 12, color: AppTheme.muted)),
            const SizedBox(height: 6),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: [
                for (final name in _llmPresets.keys)
                  ActionChip(
                    label: Text(name, style: const TextStyle(fontSize: 12.5)),
                    backgroundColor: AppTheme.tealLight,
                    onPressed: () => _applyPreset(name),
                  ),
              ],
            ),
            const SizedBox(height: 10),
            _field('接口地址 Base URL', _baseUrlCtrl,
                hint:
                    'https://llm-xxx.cn-beijing.maas.aliyuncs.com/compatible-mode/v1'),
            _field('模型名', _modelCtrl, hint: 'qwen3.8-flash / glm-5.3-flash'),
            _field('API Key（仅保存在本机）', _keyCtrl,
                obscure: true, required: true, hint: '禁止硬编码；生产建议后端中转'),
            const _SecurityNote(),
            FilledButton(
              style: FilledButton.styleFrom(backgroundColor: AppTheme.tealDark),
              onPressed: _saveLlm,
              child: const Text('保存 AI 配置'),
            ),
          ]),
          const SizedBox(height: 14),

          // ── 设备连接说明（局域网直连 + 可选云查看）──
          const _SectionTitle('设备连接'),
          _card([
            const Text('本 App 与每台 ESP32 主板局域网直连，日常使用不需要任何服务器。',
                style: TextStyle(fontSize: 13, fontWeight: FontWeight.w600)),
            const SizedBox(height: 6),
            const Text('· 在「鱼缸」Tab 添加鱼缸时填写主板 IP（如 192.168.3.190）',
                style: TextStyle(fontSize: 12, color: AppTheme.muted)),
            const Text('· 手机与设备必须连接同一路由器的 2.4G WiFi',
                style: TextStyle(fontSize: 12, color: AppTheme.muted)),
            const Text('· 摄像头（ESP32-CAM）为独立设备，添加鱼缸时可填写其地址',
                style: TextStyle(fontSize: 12, color: AppTheme.muted)),
            const Text('· 在家直连取实时数据；出门在外经下方云查看订阅最新数据',
                style: TextStyle(fontSize: 12, color: AppTheme.muted)),
          ]),
          const SizedBox(height: 14),

          // ── 云查看（EMQX 云 Broker：局域网外远程查看数据）──
          const _SectionTitle('云查看（局域网外）'),
          _card([
            const Text(
                '设备把遥测/事件上行到云 Broker；手机不在家时 App 自动'
                '经云端订阅查看（只读，无需路由器端口映射）。',
                style: TextStyle(fontSize: 12, color: AppTheme.muted)),
            const SizedBox(height: 6),
            const Text('· 设备端：在主板 Web「云链路」页填同一 Broker 并启用',
                style: TextStyle(fontSize: 12, color: AppTheme.muted)),
            const Text('· 鱼缸：添加缸时填云查看设备 ID（如 iaqua-xxxx）',
                style: TextStyle(fontSize: 12, color: AppTheme.muted)),
            const SizedBox(height: 8),
            _field('Broker 地址', _cloudHostCtrl,
                required: true, hint: '如 xxxx.ala.cn-hangzhou.emqxsl.cn'),
            Row(children: [
              Expanded(child: _field('端口（WSS）', _cloudPortCtrl, hint: '8084')),
              const SizedBox(width: 8),
              Expanded(child: _field('用户名', _cloudUserCtrl)),
            ]),
            _field('密码（仅存本机）', _cloudPassCtrl, obscure: true),
            SwitchListTile(
              contentPadding: EdgeInsets.zero,
              activeColor: AppTheme.tealDark,
              value: _syncEnabled,
              onChanged: _toggleSync,
              title: const Text('日志与计划云同步',
                  style: TextStyle(fontSize: 14, fontWeight: FontWeight.w600)),
              subtitle: const Text(
                  '多台手机经云 Broker 自动双向合并养护日志与周期计划'
                  '（含删除）；仅云端在线时产生流量，局域网直连不消耗',
                  style: TextStyle(fontSize: 11.5, color: AppTheme.muted)),
            ),
            FilledButton(
              style: FilledButton.styleFrom(backgroundColor: AppTheme.tealDark),
              onPressed: _saveCloud,
              child: const Text('保存云查看配置'),
            ),
          ]),
          const SizedBox(height: 14),

          // ── 演示数据（示意/截图用）──
          const _SectionTitle('演示数据'),
          _card([
            const Text(
                '一键写入示例养护日志、周期计划与生物清单，并模拟遥测'
                '（10 秒一帧）让概览数据卡、计划提醒、告警都有完整示意效果，'
                '适合演示与文档截图。',
                style: TextStyle(fontSize: 12, color: AppTheme.muted)),
            const SizedBox(height: 6),
            const Text('· 仅在对应内容为空时写入，不覆盖已有记录',
                style: TextStyle(fontSize: 12, color: AppTheme.muted)),
            const Text('· 关闭后停止模拟遥测；已写入的日志长按可删',
                style: TextStyle(fontSize: 12, color: AppTheme.muted)),
            SwitchListTile(
              contentPadding: EdgeInsets.zero,
              activeColor: AppTheme.tealDark,
              value: _demoOn,
              onChanged: _toggleDemo,
              title: const Text('演示模式',
                  style: TextStyle(fontSize: 14, fontWeight: FontWeight.w600)),
              subtitle: const Text('示例日志 / 周期计划 / 生物清单 + 模拟遥测',
                  style: TextStyle(fontSize: 11.5, color: AppTheme.muted)),
            ),
          ]),
          const SizedBox(height: 14),

          // ── 平台信息 ────────────────────────
          const _SectionTitle('关于'),
          _card([
            const Text('App：iAquaria $kAppVerLabel · 集美大学',
                style: TextStyle(fontSize: 13, fontWeight: FontWeight.w600)),
            const SizedBox(height: 4),
            Text('运行平台：${PlatformUtils.name}',
                style: const TextStyle(fontSize: 12, color: AppTheme.muted)),
            const SizedBox(height: 4),
            Text('权限声明：${PlatformUtils.permissionDocHint}',
                style: const TextStyle(fontSize: 11.5, color: AppTheme.muted)),
          ]),
          const SizedBox(height: 40),
        ],
      ),
    );
  }

  /// 点选预设：填充接口地址与模型名（Key 仍需用户填写）
  void _applyPreset(String name) {
    final p = _llmPresets[name];
    if (p == null || p.length < 2) return;
    setState(() {
      _baseUrlCtrl.text = p[0];
      _modelCtrl.text = p[1];
    });
    final tip = name == '豆包'
        ? '已填充豆包配置：模型名可改为你的推理接入点 ep-xxx'
        : '已填充$name配置，请填入 API Key 并保存';
    _toast(tip);
  }

  Future<void> _saveLlm() async {
    final st = StorageService.instance;
    await st.setLlmBaseUrl(_baseUrlCtrl.text.trim());
    await st.setLlmModel(_modelCtrl.text.trim());
    await st.setLlmApiKey(_keyCtrl.text.trim());
    _toast('AI 配置已保存（密钥仅存本机）');
    if (mounted) setState(() {}); // 保存后立即回显（含规范化值）
  }

  Future<void> _saveCloud() async {
    final st = StorageService.instance;
    await st.setCloudHost(_cloudHostCtrl.text.trim());
    await st.setCloudPort(int.tryParse(_cloudPortCtrl.text.trim()) ?? 8084);
    await st.setCloudUser(_cloudUserCtrl.text.trim());
    await st.setCloudPass(_cloudPassCtrl.text.trim());
    _toast('云查看配置已保存；鱼缸填了云主题后，断网 8 秒自动切云端');
    if (mounted) setState(() {}); // 保存后立即回显
  }

  Widget _card(List<Widget> children) => Container(
        padding: const EdgeInsets.all(14),
        decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.circular(14),
          border: Border.all(color: const Color(0xFFe2e8f0)),
        ),
        child: Column(
            crossAxisAlignment: CrossAxisAlignment.start, children: children),
      );

  Widget _field(String label, TextEditingController c,
      {bool obscure = false, String hint = '', bool required = false}) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: TextField(
        controller: c,
        obscureText: obscure,
        decoration: InputDecoration(
          label: required
              ? Text.rich(TextSpan(text: label, children: const [
                  TextSpan(text: ' *', style: TextStyle(color: Colors.red)),
                ]))
              : Text(label),
          hintText: hint,
          isDense: true,
          border: const OutlineInputBorder(),
        ),
      ),
    );
  }

  void _toast(String s) => ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text(s), behavior: SnackBarBehavior.floating));
}

class _SectionTitle extends StatelessWidget {
  const _SectionTitle(this.title);
  final String title;

  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.only(bottom: 8),
        child: Text(title,
            style: const TextStyle(
                fontSize: 13,
                fontWeight: FontWeight.w800,
                color: AppTheme.muted)),
      );
}

class _SecurityNote extends StatelessWidget {
  const _SecurityNote();

  @override
  Widget build(BuildContext context) => Container(
        margin: const EdgeInsets.only(bottom: 10),
        padding: const EdgeInsets.all(10),
        decoration: BoxDecoration(
          color: const Color(0xFFfffbeb),
          borderRadius: BorderRadius.circular(8),
          border: Border.all(color: const Color(0xFFfde68a)),
        ),
        child: const Text(
          '安全提示：API Key 禁止硬编码/进版本库；生产环境建议由后端中转 LLM 请求，防止密钥泄露。',
          style: TextStyle(fontSize: 11, color: Color(0xFF92400e)),
        ),
      );
}
