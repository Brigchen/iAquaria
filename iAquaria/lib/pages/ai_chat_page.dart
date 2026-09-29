/// AI 智能分析对话页：
/// - 调用兼容 OpenAI 协议的 LLM（通义千问 / GLM / DeepSeek 等），流式打字输出
/// - 摄像头后台探测：拍照按钮按状态即时决策（在线秒拍 / 离线立即提示，无需干等超时）
/// - 常用分析请求：识图类（自动抓拍）与数据类（自动注入监测遥测）
/// - 自动注入当前水质遥测读数作为上下文
/// - 分析记录按缸保存（时间倒序可回看）；生物识别/清点结果回写生物清单
library;

import 'dart:async';
import 'dart:convert';
import 'dart:typed_data';

import 'package:flutter/material.dart';

import '../app.dart';
import '../core/theme.dart';
import '../models/bio.dart';
import '../services/camera_service.dart';
import '../services/llm_service.dart';

/// 常用分析请求：needCam=true 时点击自动抓拍（识图）；否则直接发（监测数据自动注入）
/// bio=true 的请求要求 LLM 在回复末行输出「生物清单：名称×数量, …」以便回写生物数据
class _QuickAsk {
  const _QuickAsk(this.label, this.prompt,
      {this.needCam = false, this.bio = false});
  final String label;
  final String prompt;
  final bool needCam;
  final bool bio;
}

const _quickAsks = <_QuickAsk>[
  _QuickAsk(
      '生物识别',
      '识别照片中的生物品种，逐一列出名称与简要习性。'
          '生物按类群分类，类群限于：鱼/水草/珊瑚/软体/甲壳。'
          '回答控制在200字内。最后另起一行，严格按纯文本单行（不要 Markdown 表格、不要换行）'
          '输出汇总：生物清单：类群|种名|数量, 类群|种名|数量，'
          '数量用阿拉伯数字（不确定给估计值），如「生物清单：鱼|斑马鱼|5, 水草|莫斯|3」。',
      needCam: true,
      bio: true),
  _QuickAsk(
      '数量清点',
      '清点照片中的生物数量，按类群与种类汇总。'
          '生物按类群分类，类群限于：鱼/水草/珊瑚/软体/甲壳。'
          '回答控制在200字内。最后另起一行，严格按纯文本单行（不要 Markdown 表格、不要换行）'
          '输出：生物清单：类群|种名|数量, 类群|种名|数量，'
          '数量用阿拉伯数字，如「生物清单：鱼|孔雀鱼|8, 甲壳|黑壳虾|20」。',
      needCam: true,
      bio: true),
  _QuickAsk('健康观察', '观察照片中鱼虾的健康状态：是否有白点、烂鳍、蒙眼、浮头、蹭缸等异常迹象。回答控制在200字内。',
      needCam: true),
  _QuickAsk('藻类评估', '评估缸壁、造景、水草上的藻类情况（褐藻/绿藻/丝藻/黑毛），判断是否需要处理并给出方案。回答控制在200字内。',
      needCam: true),
  _QuickAsk('水草状态', '评估水草状态：是否有黄叶、溶叶、缩叶、缺肥缺光迹象，给出修剪与施肥建议。回答控制在200字内。',
      needCam: true),
  _QuickAsk('水质判断', '根据当前监测数据（水温/pH/TDS等）综合判断水质状况，指出异常项与风险。回答控制在200字内。'),
  _QuickAsk('换水建议', '根据当前监测数据给出换水量、换水频率与操作注意事项。回答控制在200字内。'),
  _QuickAsk('CO2与光照', '根据光照与 pH 数据评估 CO2 补给与光照时长是否匹配，给出参数调整建议。回答控制在200字内。'),
  _QuickAsk('温度评估', '根据水温数据评估加热棒目标温度与回差设置是否合理。回答控制在200字内。'),
  _QuickAsk('养护清单', '综合当前监测数据，生成一份本周养护清单（喂食/换水/擦缸/设备检查）。回答控制在200字内。'),
];

/// 照片来源（在线摄像头 / 手机相机）
enum _ImgSrc { online, phone }

class AiChatPage extends StatefulWidget {
  const AiChatPage({super.key});

  @override
  State<AiChatPage> createState() => _AiChatPageState();
}

class _AiChatPageState extends State<AiChatPage> {
  final List<ChatMsg> _msgs = [];
  final _input = TextEditingController();
  final _scroll = ScrollController();
  Uint8List? _pendingImage; // 待发送的抓拍帧
  bool _busy = false;

  // 摄像头后台探测：拍照前已知晓状态，点击即时决策
  static const _camUnknown = 0, _camOnline = 1, _camOffline = 2;
  int _camState = _camUnknown;
  Timer? _camProbe;
  bool _probing = false;

  String? get _camUrl {
    final c = AppStore.instance.activeTank?.camUrl.trim() ?? '';
    return c.isEmpty ? null : c;
  }

  @override
  void initState() {
    super.initState();
    _camProbe = Timer.periodic(const Duration(seconds: 3), (_) => _probeCam());
  }

  @override
  void dispose() {
    _input.dispose();
    _scroll.dispose();
    _camProbe?.cancel();
    super.dispose();
  }

  Future<void> _probeCam() async {
    final cam = _camUrl;
    if (cam == null || _probing || _busy) return;
    _probing = true;
    try {
      await CameraService.instance.capture(cam);
      if (mounted && _camState != _camOnline)
        setState(() => _camState = _camOnline);
    } catch (_) {
      if (mounted && _camState != _camOffline)
        setState(() => _camState = _camOffline);
    } finally {
      _probing = false;
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('AI 智能分析'),
        actions: [
          // 分析记录入口（按日期时间回看，随缸保存）
          IconButton(
            tooltip: '分析记录',
            icon: const Icon(Icons.history),
            onPressed: _showHistory,
          ),
        ],
      ),
      body: Column(
        children: [
          Expanded(
            child: _msgs.isEmpty ? _emptyHint() : _list(),
          ),
          _quickBar(),
          _inputBar(),
        ],
      ),
    );
  }

  /// 分析记录弹层：按日期时间倒序列出本缸全部历史分析
  void _showHistory() {
    final store = AppStore.instance;
    showModalBottomSheet<void>(
      context: context,
      backgroundColor: Colors.white,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(16)),
      ),
      builder: (ctx) => SafeArea(
        child: SizedBox(
          height: 480,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Padding(
                padding: const EdgeInsets.fromLTRB(16, 14, 16, 8),
                child: Row(
                  children: [
                    const Expanded(
                      child: Text('分析记录',
                          style: TextStyle(
                              fontSize: 14.5, fontWeight: FontWeight.w700)),
                    ),
                    Text('${store.analysis.length} 条',
                        style: const TextStyle(
                            fontSize: 11.5, color: AppTheme.muted)),
                  ],
                ),
              ),
              const Divider(height: 1),
              Expanded(
                child: store.analysis.isEmpty
                    ? const Center(
                        child: Text('暂无分析记录',
                            style: TextStyle(
                                fontSize: 12.5, color: AppTheme.muted)))
                    : ListView.separated(
                        padding: const EdgeInsets.symmetric(
                            horizontal: 16, vertical: 8),
                        itemCount: store.analysis.length,
                        separatorBuilder: (_, __) => const Divider(height: 1),
                        itemBuilder: (_, i) {
                          final r = store.analysis[i];
                          final t = DateTime.fromMillisecondsSinceEpoch(r.ts);
                          final time =
                              '${t.year}-${_two(t.month)}-${_two(t.day)} ${_two(t.hour)}:${_two(t.minute)}';
                          return Theme(
                            data: Theme.of(ctx)
                                .copyWith(dividerColor: Colors.transparent),
                            child: ExpansionTile(
                              tilePadding: EdgeInsets.zero,
                              title: Text(r.req,
                                  maxLines: 1,
                                  overflow: TextOverflow.ellipsis,
                                  style: const TextStyle(
                                      fontSize: 13,
                                      fontWeight: FontWeight.w600)),
                              subtitle: Row(children: [
                                if (r.hasImage) ...[
                                  const Icon(Icons.photo,
                                      size: 12, color: AppTheme.tealDark),
                                  const SizedBox(width: 3),
                                ],
                                Text(time,
                                    style: const TextStyle(
                                        fontSize: 11, color: AppTheme.muted)),
                              ]),
                              children: [
                                Align(
                                  alignment: Alignment.centerLeft,
                                  child: SelectableText(r.reply,
                                      style: const TextStyle(
                                          fontSize: 12.5,
                                          height: 1.5,
                                          color: Colors.black87)),
                                ),
                                const SizedBox(height: 8),
                              ],
                            ),
                          );
                        },
                      ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _emptyHint() {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(Icons.auto_awesome,
              size: 44, color: AppTheme.teal.withOpacity(.5)),
          const SizedBox(height: 12),
          const Text('问点什么，或点击相机抓拍让 AI 看看鱼缸',
              style: TextStyle(color: AppTheme.muted, fontSize: 13)),
          const SizedBox(height: 6),
          const Text('例如：帮我评估爆藻风险 / 这些鱼是什么品种',
              style: TextStyle(color: AppTheme.muted, fontSize: 11.5)),
        ],
      ),
    );
  }

  Widget _list() {
    return ListView.builder(
      controller: _scroll,
      padding: const EdgeInsets.all(14),
      itemCount: _msgs.length,
      itemBuilder: (_, i) => _bubble(_msgs[i]),
    );
  }

  Widget _bubble(ChatMsg m) {
    final isUser = m.role == 'user';
    return Align(
      alignment: isUser ? Alignment.centerRight : Alignment.centerLeft,
      child: Container(
        margin: const EdgeInsets.only(bottom: 10),
        padding: const EdgeInsets.all(12),
        constraints:
            BoxConstraints(maxWidth: MediaQuery.of(context).size.width * .82),
        decoration: BoxDecoration(
          color: m.error
              ? const Color(0xFFfef2f2)
              : isUser
                  ? AppTheme.tealLight
                  : Colors.white,
          borderRadius: BorderRadius.circular(14),
          border: Border.all(
              color: m.error
                  ? AppTheme.danger.withOpacity(.4)
                  : const Color(0xFFe2e8f0)),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // 用户消息附带抓拍图
            if (m.imageBase64 != null)
              Container(
                margin: const EdgeInsets.only(bottom: 8),
                child: ClipRRect(
                  borderRadius: BorderRadius.circular(8),
                  child: Image.memory(
                    const Base64Decoder().convert(m.imageBase64!),
                    width: 200,
                    fit: BoxFit.cover,
                  ),
                ),
              ),
            SelectableText(
              m.content,
              style: TextStyle(
                fontSize: 13.5,
                height: 1.45,
                color: m.error ? AppTheme.danger : Colors.black87,
              ),
            ),
          ],
        ),
      ),
    );
  }

  /// 常用分析请求条（横向滚动；识图类点击自动抓拍，数据类直接发问）
  Widget _quickBar() {
    return SizedBox(
      height: 42,
      child: ListView.separated(
        scrollDirection: Axis.horizontal,
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
        itemCount: _quickAsks.length,
        separatorBuilder: (_, __) => const SizedBox(width: 6),
        itemBuilder: (_, i) {
          final q = _quickAsks[i];
          return ActionChip(
            label: Row(mainAxisSize: MainAxisSize.min, children: [
              Icon(
                  q.needCam ? Icons.photo_camera : Icons.monitor_heart_outlined,
                  size: 13,
                  color: AppTheme.tealDark),
              const SizedBox(width: 3),
              Text(q.label, style: const TextStyle(fontSize: 11.5)),
            ]),
            backgroundColor: AppTheme.tealLight.withOpacity(.55),
            side: BorderSide(color: AppTheme.teal.withOpacity(.35)),
            onPressed: _busy ? null : () => _runQuick(q),
          );
        },
      ),
    );
  }

  /// 执行快捷分析：识图类先取图（在线摄像头优先抓拍，失败/无设备时选手机相机）
  Future<void> _runQuick(_QuickAsk q) async {
    if (_busy) return;
    if (q.needCam && _pendingImage == null) {
      final store = AppStore.instance;
      Uint8List? jpeg;
      // 云端模式：直接用 ESP32-CAM 定时上传的最新云照片
      if (store.linkState == 'cloud' && store.cloudPhoto != null) {
        jpeg = store.cloudPhoto;
      }
      // 优先在线摄像头：已配置且未判离线时直接抓拍（快捷操作不弹层）
      final cam = _camUrl;
      if (jpeg == null && cam != null && _camState != _camOffline) {
        try {
          jpeg = await CameraService.instance.capture(cam);
          if (mounted) setState(() => _camState = _camOnline);
        } catch (_) {
          if (mounted) setState(() => _camState = _camOffline);
          jpeg = null; // 抓拍失败 → 落到来源选择（可改手机相机）
        }
      }
      // 无在线摄像头 / 抓拍失败（人工缸）：弹来源选择
      if (jpeg == null) {
        jpeg = await _chooseImageSource();
      }
      if (jpeg == null) return;
      if (!mounted) return;
      setState(() => _pendingImage = jpeg);
    }
    _input.text = q.prompt;
    await _send(bioExpect: q.bio);
  }

  Widget _inputBar() {
    return SafeArea(
      child: Container(
        padding: const EdgeInsets.fromLTRB(12, 8, 12, 10),
        decoration: const BoxDecoration(
          color: Colors.white,
          border: Border(top: BorderSide(color: Color(0xFFe2e8f0))),
        ),
        child: Row(
          children: [
            // 摄像头抓拍按钮（按后台探测状态即时决策：离线不再干等超时）
            Stack(
              clipBehavior: Clip.none,
              children: [
                IconButton(
                  onPressed: _busy ? null : _capture,
                  icon: Icon(Icons.photo_camera_outlined,
                      color: _pendingImage != null
                          ? AppTheme.tealDark
                          : _camState == _camOffline
                              ? Colors.grey.shade400
                              : AppTheme.muted),
                  tooltip: '抓拍鱼缸画面（ESP32-CAM）',
                ),
                // 摄像头状态圆点：绿=在线 灰=离线（未探测无点）
                if (_camState != _camUnknown)
                  Positioned(
                    right: 8,
                    top: 8,
                    child: Container(
                      width: 7,
                      height: 7,
                      decoration: BoxDecoration(
                        shape: BoxShape.circle,
                        color: _camState == _camOnline
                            ? const Color(0xFF22c55e)
                            : Colors.grey.shade400,
                      ),
                    ),
                  ),
              ],
            ),
            Expanded(
              child: TextField(
                controller: _input,
                minLines: 1,
                maxLines: 4,
                textInputAction: TextInputAction.send,
                onSubmitted: (_) => _send(),
                decoration: const InputDecoration(
                  hintText: '询问养护建议 / 识图分析…',
                  isDense: true,
                  filled: true,
                  fillColor: Color(0xFFF4F7F7),
                  border: OutlineInputBorder(borderSide: BorderSide.none),
                ),
              ),
            ),
            const SizedBox(width: 8),
            // 发送按钮（Flutter 3.7 无 IconButton.filled，用 Material 按钮）
            SizedBox(
              width: 42,
              height: 42,
              child: ElevatedButton(
                style: ElevatedButton.styleFrom(
                  backgroundColor: AppTheme.tealDark,
                  padding: EdgeInsets.zero,
                  shape: const CircleBorder(),
                ),
                onPressed: _busy ? null : _send,
                child: _busy
                    ? const SizedBox(
                        width: 18,
                        height: 18,
                        child: CircularProgressIndicator(
                            strokeWidth: 2, color: Colors.white))
                    : const Icon(Icons.send, size: 18, color: Colors.white),
              ),
            ),
          ],
        ),
      ),
    );
  }

  /// 选择照片来源并取图（在线摄像头抓拍 / 手机相机拍摄）
  Future<void> _capture() async {
    if (_busy) return;
    // 云端模式：直接用 ESP32-CAM 定时上传的最新云照片
    final store = AppStore.instance;
    if (store.linkState == 'cloud' && store.cloudPhoto != null) {
      setState(() {
        _pendingImage = store.cloudPhoto;
        _camState = _camOnline;
      });
      _toast('已取用最新云端照片，发送时 AI 将识图分析');
      return;
    }
    final jpeg = await _chooseImageSource();
    if (!mounted || jpeg == null) return;
    setState(() => _pendingImage = jpeg);
    _toast('已选取照片，发送时 AI 将识图分析');
  }

  /// 照片来源选择弹层：在线摄像头（ESP32-CAM）/ 手机相机。
  /// 返回 JPEG 字节（用户取消或失败返回 null）。
  Future<Uint8List?> _chooseImageSource() async {
    final online = _camUrl;
    final src = await showModalBottomSheet<_ImgSrc>(
      context: context,
      backgroundColor: Colors.white,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(16)),
      ),
      builder: (ctx) => SafeArea(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Padding(
              padding: EdgeInsets.fromLTRB(18, 18, 16, 6),
              child: Text('选择照片来源',
                  style:
                      TextStyle(fontSize: 14.5, fontWeight: FontWeight.w700)),
            ),
            ListTile(
              leading: const Icon(Icons.videocam, color: AppTheme.tealDark),
              title: const Text('在线摄像头'),
              subtitle: Text(online ?? '未配置（可在「鱼缸」Tab 编辑缸时填写）'),
              enabled: online != null,
              onTap: () => Navigator.pop(ctx, _ImgSrc.online),
            ),
            ListTile(
              leading: const Icon(Icons.phone_iphone, color: AppTheme.tealDark),
              title: const Text('手机相机'),
              subtitle: const Text('调起手机相机拍摄鱼缸（人工缸推荐）'),
              onTap: () => Navigator.pop(ctx, _ImgSrc.phone),
            ),
            const SizedBox(height: 10),
          ],
        ),
      ),
    );
    if (src == null) return null;

    if (src == _ImgSrc.online) {
      if (online == null) return null;
      try {
        final jpeg = await CameraService.instance.capture(online);
        if (mounted) setState(() => _camState = _camOnline);
        return jpeg;
      } catch (_) {
        if (mounted) {
          setState(() => _camState = _camOffline);
          _toast('在线摄像头抓拍失败，可重试或改用手机相机');
        }
        return null;
      }
    }

    try {
      return await CameraService.instance.pickFromPhoneCamera();
    } on UnsupportedError catch (e) {
      if (mounted) _toast(e.message ?? '当前平台不支持手机相机');
      return null;
    }
  }

  Future<void> _send({bool bioExpect = false}) async {
    final prompt = _input.text.trim();
    if (prompt.isEmpty && _pendingImage == null) return;
    final store = AppStore.instance;

    final img = _pendingImage;
    final imgB64 = img != null ? base64Encode(img) : null;

    setState(() {
      _msgs.add(ChatMsg(
          role: 'user',
          content: prompt.isEmpty ? '（识图分析这张鱼缸照片）' : prompt,
          imageBase64: imgB64));
      _pendingImage = null;
      _input.clear();
      // 预插入空的 assistant 气泡，流式填充
      _msgs.add(ChatMsg(role: 'assistant', content: ''));
      _busy = true;
    });
    _scrollToBottom();

    final history = _msgs.sublist(0, _msgs.length - 1);
    final buf = StringBuffer();
    await for (final delta in LlmService.instance.send(
      history: history,
      prompt: prompt.isEmpty ? '请识别照片中的鱼虾并计数，评估藻类与爆藻风险，给出养护建议。' : prompt,
      imageBase64: imgB64,
      telemetry: store.telemetry,
    )) {
      buf.write(delta);
      setState(() => _msgs.last.content = buf.toString());
      _scrollToBottom();
    }
    setState(() => _busy = false);
    _scrollToBottom();

    // ── 回复完成：保存分析记录（错误回复不存） ──
    final reply = buf.toString();
    if (store.activeTank != null &&
        reply.isNotEmpty &&
        !reply.startsWith('[请求失败]')) {
      await store.addAnalysisRecord(AnalysisRecord(
        ts: DateTime.now().millisecondsSinceEpoch,
        req: prompt.isEmpty ? '识图分析' : prompt,
        reply: reply,
        hasImage: imgB64 != null,
      ));

      // 生物识别/清点：解析「生物清单」回写生物数据（AI 可能误判，可后续手动修正）
      if (bioExpect) {
        final found = parseBioList(reply);
        if (found.isNotEmpty) {
          await store.updateBio(mergeBio(store.bio, found));
          if (mounted) _toast('已更新生物清单（AI 识别可能有误，可在概览页生物面板修正）');
        } else if (mounted) {
          // 解析失败给出明确反馈，避免用户不知道数据为何没进生物概览
          _toast('未能从 AI 回复中解析生物清单，可再试一次或在生物面板手动添加');
        }
      }
    }
  }

  void _scrollToBottom() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (_scroll.hasClients) {
        _scroll.animateTo(
          _scroll.position.maxScrollExtent,
          duration: const Duration(milliseconds: 200),
          curve: Curves.easeOut,
        );
      }
    });
  }

  void _toast(String s) {
    ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(s), behavior: SnackBarBehavior.floating));
  }

  /// 两位数补零（时间格式化用）
  static String _two(int n) => n.toString().padLeft(2, '0');
}
