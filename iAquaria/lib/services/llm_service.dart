/// LLM 服务（独立 service）：自实现 OpenAI 协议客户端（SSE 流式 + 多模态识图）。
///
/// ── 实现说明 ────────────────────────────────────────────────
/// 鸿蒙版 Flutter 基于 Dart 2.19，openai_dart 包（需 Dart 3+）无法使用，
/// 故按 OpenAI Chat Completions 协议手写轻量客户端：
/// - POST {baseUrl}/chat/completions，stream=true，逐行解析 `data: {...}` SSE 帧
/// - 与 openai_dart 调用协议完全一致，可无缝切换 DeepSeek / 通义千问
/// ── 安全提醒（务必遵守）─────────────────────────────────────
/// 1. API Key 禁止硬编码到源码 / 配置 / 版本库；
/// 2. Key 仅通过设置页录入，保存在本机（StorageService，shared_preferences）；
/// 3. 生产环境建议自建后端中转 LLM 请求（App → 后端 → LLM），
///    避免密钥随 App 分发泄露，也可做限流与审计。
/// ────────────────────────────────────────────────────────────
///
/// 兼容 OpenAI 协议的服务商（设置页配置 baseUrl + 模型名 + Key 即可切换）：
/// - 通义千问：    https://llm-xxx.cn-beijing.maas.aliyuncs.com/compatible-mode/v1（阿里云百炼）
///   模型 qwen3.8-flash（多模态视觉识别）
/// - 智谱 GLM：    https://open.bigmodel.cn/api/paas/v4
///   模型 glm-5.3-flash（多模态）
/// - 豆包(火山方舟)：https://ark.cn-beijing.volces.com/api/v3
///   模型 doubao-seed-2-1-pro-260628（多模态）
/// - DeepSeek：    https://api.deepseek.com
///   模型 deepseek-flash（V4.1-Flash，支持视觉）；deepseek-v4-pro 为旗舰纯文本
/// - Kimi：        https://api.moonshot.cn/v1
///   模型 kimi-k3（1M 上下文 + 视觉理解）
/// - 其他 OpenAI 兼容端点（SiliconFlow / Ollama 等）同理。
library;

import 'dart:async';
import 'dart:convert';

import 'package:dio/dio.dart';

import '../models/telemetry.dart';
import 'storage_service.dart';

/// 一条聊天消息（App 侧展示模型）
class ChatMsg {
  ChatMsg({
    required this.role,
    required this.content,
    this.imageBase64,
    this.error = false,
  });

  final String role; // user / assistant
  String content;

  /// 用户附带图片（JPEG base64，无 data: 前缀）
  final String? imageBase64;

  final bool error;
}

class LlmService {
  LlmService._();
  static final LlmService instance = LlmService._();

  final Dio _dio = Dio();

  /// 当前是否正在流式回答（页面据此禁用发送按钮）
  bool streaming = false;

  /// 发送一条消息并流式回调（打字机效果）。
  ///
  /// [history] 为本会话历史（user/assistant 轮次）；
  /// [imageBase64] 非空时走多模态（需模型支持视觉，如 qwen3.8-flash）；
  /// [telemetry] 非空时自动把当前水质读数注入上下文。
  Stream<String> send({
    required List<ChatMsg> history,
    required String prompt,
    String? imageBase64,
    Telemetry? telemetry,
  }) async* {
    final st = StorageService.instance;
    final apiKey = await st.llmApiKey();
    final baseUrl = await st.llmBaseUrl();
    final model = await st.llmModel();

    if (apiKey.isEmpty) {
      yield '尚未配置 LLM API Key：请到「设置 → AI 服务」填入密钥（仅保存在本机，禁止硬编码分发）。';
      return;
    }

    // ── 组装 messages（OpenAI Chat Completions 格式）──
    final messages = <Map<String, dynamic>>[
      // 系统提示：水族养护专家人设 + 输出约束
      {'role': 'system', 'content': _systemPrompt()},
      // 历史轮次
      for (final m in history)
        m.role == 'user'
            ? _userMessage(m.content, m.imageBase64)
            : {'role': 'assistant', 'content': m.content},
      // 本轮输入（可带图）
      _userMessage(_composePrompt(prompt, telemetry), imageBase64),
    ];

    final body = {
      'model': model,
      'messages': messages,
      'stream': true, // 流式输出（打字机）
    };

    streaming = true;
    try {
      // dio 流式响应：逐字节接收，按行拆 SSE 帧
      final res = await _dio.post<ResponseBody>(
        '${baseUrl.replaceAll(RegExp(r'/+$'), '')}/chat/completions',
        options: Options(
          headers: {
            'Authorization': 'Bearer $apiKey',
            'Content-Type': 'application/json',
            'Accept': 'text/event-stream',
          },
          responseType: ResponseType.stream, // 关键：流式接收
          validateStatus: (s) => s != null && s < 500,
        ),
        data: body,
      );

      if (res.statusCode != 200) {
        // 读取错误体给用户明确提示（如 401 密钥无效 / 400 模型不支持图片）
        String errText = 'HTTP ${res.statusCode}';
        try {
          errText = await utf8.decodeStream(res.data!.stream);
        } catch (_) {}
        yield '\n[请求失败] $errText\n请检查：接口地址 / API Key / 模型名（图片需视觉模型如 qwen3.8-flash）。';
        return;
      }

      // 逐行解析 SSE：以 "data: " 开头的 JSON 帧，data: [DONE] 结束
      final lines = res.data!.stream
          .cast<List<int>>()
          .transform(const Utf8Decoder(allowMalformed: true))
          .transform(const LineSplitter());
      await for (final line in lines) {
        final t = line.trim();
        if (!t.startsWith('data:')) continue;
        final payload = t.substring(5).trim();
        if (payload == '[DONE]') break;
        try {
          final j = jsonDecode(payload) as Map<String, dynamic>;
          final choices = (j['choices'] as List?) ?? const [];
          if (choices.isEmpty) continue;
          final delta = (choices.first as Map)['delta'] as Map<String, dynamic>?;
          final content = delta?['content'] as String?;
          if (content != null && content.isNotEmpty) {
            yield content;
          }
        } catch (_) {
          // 非 JSON 行（心跳注释等）忽略
        }
      }
    } catch (e) {
      yield '\n[请求失败] $e\n请检查：接口地址 / API Key / 网络。';
    } finally {
      streaming = false;
    }
  }

  // ───────────── 内部工具 ─────────────

  /// 文本消息 或 多模态消息（text + image_url，data URI 内嵌 JPEG base64）
  Map<String, dynamic> _userMessage(String text, String? imageBase64) {
    if (imageBase64 == null || imageBase64.isEmpty) {
      return {'role': 'user', 'content': text};
    }
    return {
      'role': 'user',
      'content': [
        {'type': 'text', 'text': text},
        {
          'type': 'image_url',
          'image_url': {'url': 'data:image/jpeg;base64,$imageBase64'},
        },
      ],
    };
  }

  String _systemPrompt() =>
      '你是"iAquaria 水族 AI 助理"，由集美大学 Coralab 团队开发，擅长淡水缸/海水缸/草缸的'
      '水质管理与养护建议。回答规则：1) 用简体中文，简洁分点，给出可执行的养护动作；'
      '2) 涉及数值判断时引用给定的实时读数与合理阈值（水温 24-28℃，pH 6.4-7.6，水位 20%-95%）；'
      '3) 收到鱼缸照片时：识别并计数可见的鱼/虾/螺，描述水草与藻类状态，评估爆藻风险'
      '（低/中/高），给出喂食量、换水与灯光调整建议；4) 不确定的结论要说明依据不足，不建议用药；'
      '5) 回答全文控制在 200 字以内（数据/清单行不计）。';

  String _composePrompt(String prompt, Telemetry? tel) {
    if (tel == null || tel.isEmpty) return prompt;
    final s = StringBuffer('【当前水质读数】');
    if (tel.temp != null) s.write('水温 ${tel.temp}℃；');
    if (tel.ph != null) s.write('pH ${tel.ph}；');
    if (tel.orp != null) s.write('ORP ${tel.orp}mV；');
    if (tel.tds1 != null) s.write('TDS/盐度通道1 ${tel.tds1}；');
    if (tel.tds2 != null) s.write('TDS通道2 ${tel.tds2}；');
    if (tel.lux != null) s.write('光照 ${tel.lux}lx；');
    if (tel.level != null) s.write('水位 ${tel.level}%');
    s.write('\n\n');
    s.write(prompt);
    return s.toString();
  }
}
