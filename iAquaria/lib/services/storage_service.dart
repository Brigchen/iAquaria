/// 本地存储服务：缸档案 / 日志 / 任务 / 告警规则 / **LLM API 密钥** 全部保存在本地。
///
/// 安全约束（重要）：
/// - API Key 禁止硬编码在任何源码、配置文件或版本库中；
/// - 密钥仅保存在本机（shared_preferences），不上传、不写日志；
/// - 生产环境建议由后端中转 LLM 请求，App 端只持有短期 token，避免密钥泄露。
library;

import 'dart:convert';

import 'package:shared_preferences/shared_preferences.dart';

import '../models/bio.dart';
import '../models/records.dart';
import '../models/tank.dart';

class StorageService {
  StorageService._();
  static final StorageService instance = StorageService._();

  SharedPreferences? _prefs;

  Future<SharedPreferences> get prefs async => _prefs ??= await SharedPreferences.getInstance();

  // ───────────── 通用 KV ─────────────
  Future<String?> getString(String key) async => (await prefs).getString(key);

  Future<void> setString(String key, String value) async => (await prefs).setString(key, value);

  Future<void> remove(String key) async => (await prefs).remove(key);

  // ───────────── LLM 配置（密钥安全：仅本地） ─────────────
  static const _kLlmBaseUrl = 'llm_base_url';
  static const _kLlmApiKey = 'llm_api_key';
  static const _kLlmModel = 'llm_model';

  /// LLM 接口地址，如：
  /// - 通义千问(OpenAI兼容, 阿里云百炼): https://llm-xxx.cn-beijing.maas.aliyuncs.com/compatible-mode/v1
  /// - DeepSeek: https://api.deepseek.com/v1
  Future<String> llmBaseUrl() async =>
      await getString(_kLlmBaseUrl) ?? 'https://llm-54er3r3q5452ofct.cn-beijing.maas.aliyuncs.com/compatible-mode/v1';

  Future<void> setLlmBaseUrl(String v) => setString(_kLlmBaseUrl, v);

  /// API Key：仅存本地，禁止硬编码 / 打日志
  Future<String> llmApiKey() async => await getString(_kLlmApiKey) ?? '';

  Future<void> setLlmApiKey(String v) => setString(_kLlmApiKey, v);

  /// 模型名，如 qwen3.8-flash（阿里云百炼多模态）/ deepseek-flash（支持视觉）
  Future<String> llmModel() async => await getString(_kLlmModel) ?? 'qwen3.8-flash';

  Future<void> setLlmModel(String v) => setString(_kLlmModel, v);

  // ───────────── 云查看配置（EMQX Serverless 等 MQTT over TLS Broker） ─────────────
  // App 连接云 Broker（WebSocket over TLS，默认 8084）订阅设备上行主题，
  // 用于局域网之外的远程查看。凭据仅存本机。
  static const _kCloudHost = 'cloud_host';
  static const _kCloudPort = 'cloud_port';
  static const _kCloudUser = 'cloud_user';
  static const _kCloudPass = 'cloud_pass';

  /// 云 Broker 地址（域名），如 xxxx.ala.cn-hangzhou.emqxsl.cn
  Future<String> cloudHost() async => await getString(_kCloudHost) ?? '';

  Future<void> setCloudHost(String v) => setString(_kCloudHost, v);

  /// WebSocket over TLS 端口（EMQX Serverless 为 8084）
  Future<int> cloudPort() async {
    final raw = await getString(_kCloudPort);
    return int.tryParse(raw ?? '') ?? 8084;
  }

  Future<void> setCloudPort(int v) => setString(_kCloudPort, '$v');

  Future<String> cloudUser() async => await getString(_kCloudUser) ?? '';

  Future<void> setCloudUser(String v) => setString(_kCloudUser, v);

  /// 密码（仅存本机，不上传日志）
  Future<String> cloudPass() async => await getString(_kCloudPass) ?? '';

  Future<void> setCloudPass(String v) => setString(_kCloudPass, v);

  // ───────────── 缸档案 ─────────────
  // 说明：设备直连架构下无需 MQTT Broker，每缸的 ESP32 IP 保存在 Tank 档案里。
  static const _kTanks = 'tanks_json';
  static const _kActiveTank = 'active_tank_id';

  Future<List<Tank>> tanks() async {
    final raw = await getString(_kTanks);
    if (raw == null || raw.isEmpty) return [];
    try {
      final list = (jsonDecode(raw) as List).cast<Map<String, dynamic>>();
      return list.map(Tank.fromJson).where((t) => !t.archived).toList();
    } catch (_) {
      return [];
    }
  }

  Future<void> saveTanks(List<Tank> tanks) =>
      setString(_kTanks, jsonEncode(tanks.map((t) => t.toJson()).toList()));

  Future<String?> activeTankId() async => await getString(_kActiveTank);

  Future<void> setActiveTankId(String id) => setString(_kActiveTank, id);

  Future<void> clearActiveTankId() => remove(_kActiveTank);

  // ───────────── 日志 ─────────────
  static const _kJournals = 'journals_json';

  Future<List<JournalEntry>> journals(String tankId) async {
    final raw = await getString(_kJournals);
    if (raw == null || raw.isEmpty) return [];
    try {
      final list = (jsonDecode(raw) as List).cast<Map<String, dynamic>>();
      return list
          .map(JournalEntry.fromJson)
          .where((e) => e.tankId == tankId)
          .toList()
        ..sort((a, b) => b.ts.compareTo(a.ts));
    } catch (_) {
      return [];
    }
  }

  Future<void> addJournal(JournalEntry e) async {
    final raw = await getString(_kJournals);
    final list = (raw == null || raw.isEmpty)
        ? <Map<String, dynamic>>[]
        : (jsonDecode(raw) as List).cast<Map<String, dynamic>>();
    list.add(e.toJson());
    await setString(_kJournals, jsonEncode(list));
  }

  /// 删除单条日志（长按删除误输入/错误记录），按 id+缸 id 双重匹配
  Future<void> deleteJournal(String tankId, String id) async {
    final raw = await getString(_kJournals);
    if (raw == null || raw.isEmpty) return;
    try {
      final list = (jsonDecode(raw) as List).cast<Map<String, dynamic>>();
      list.removeWhere((m) => m['id'] == id && m['tankId'] == tankId);
      await setString(_kJournals, jsonEncode(list));
    } catch (_) {}
  }

  // ───────────── 任务 ─────────────
  static const _kTasks = 'tasks_json';

  Future<List<TaskEntity>> tasks(String tankId) async {
    final raw = await getString(_kTasks);
    if (raw == null || raw.isEmpty) return [];
    try {
      final list = (jsonDecode(raw) as List).cast<Map<String, dynamic>>();
      final all = list.map(TaskEntity.fromJson).where((t) => t.tankId == tankId && !t.paused).toList()
        ..sort((a, b) => a.nextDue.compareTo(b.nextDue));
      return all;
    } catch (_) {
      return [];
    }
  }

  Future<void> saveTasks(List<TaskEntity> tasks) =>
      setString(_kTasks, jsonEncode(tasks.map((t) => t.toJson()).toList()));

  // ───────────── 告警规则 ─────────────
  static const _kRules = 'alert_rules_json';

  Future<List<AlertRule>> alertRules(String tankId) async {
    final raw = await getString(_kRules);
    if (raw == null || raw.isEmpty) return [];
    try {
      final list = (jsonDecode(raw) as List).cast<Map<String, dynamic>>();
      return list.map(AlertRule.fromJson).where((r) => r.tankId == tankId).toList();
    } catch (_) {
      return [];
    }
  }

  Future<void> saveAlertRules(List<AlertRule> rules) =>
      setString(_kRules, jsonEncode(rules.map((r) => r.toJson()).toList()));

  // ───────────── 生物监测数据（按缸） ─────────────
  // 结构：{ tankId: [ {name, count}, ... ] }（AI 识别回写 + 手动修正）
  static const _kBio = 'bio_json';

  Future<List<BioSpecies>> bioOf(String tankId) async {
    final raw = await getString(_kBio);
    if (raw == null || raw.isEmpty) return [];
    try {
      final map = (jsonDecode(raw) as Map).cast<String, dynamic>();
      final arr = map[tankId];
      return arr is List ? BioSpecies.listFromJson(arr) : [];
    } catch (_) {
      return [];
    }
  }

  Future<void> saveBio(String tankId, List<BioSpecies> list) async {
    final raw = await getString(_kBio);
    final map = <String, dynamic>{};
    if (raw != null && raw.isNotEmpty) {
      try {
        map.addAll((jsonDecode(raw) as Map).cast<String, dynamic>());
      } catch (_) {}
    }
    map[tankId] = BioSpecies.listToJson(list);
    await setString(_kBio, jsonEncode(map));
  }

  /// 生物清单历史版本（按时间点）：{ tankId: [ {ts, items:[...]}, ... ] }
  /// 每次修改前把旧清单快照入档（最新在前，上限 50 版）
  static const _kBioHistory = 'bio_history_json';

  Future<List<Map<String, dynamic>>> bioHistoryOf(String tankId) async {
    final raw = await getString(_kBioHistory);
    if (raw == null || raw.isEmpty) return [];
    try {
      final map = (jsonDecode(raw) as Map).cast<String, dynamic>();
      final arr = map[tankId];
      if (arr is! List) return [];
      return arr
          .map((e) => Map<String, dynamic>.from(e as Map))
          .toList();
    } catch (_) {
      return [];
    }
  }

  Future<void> pushBioHistory(String tankId, List<BioSpecies> oldList) async {
    final raw = await getString(_kBioHistory);
    final map = <String, dynamic>{};
    if (raw != null && raw.isNotEmpty) {
      try {
        map.addAll((jsonDecode(raw) as Map).cast<String, dynamic>());
      } catch (_) {}
    }
    final arr = (map[tankId] is List)
        ? (map[tankId] as List)
            .map((e) => Map<String, dynamic>.from(e as Map))
            .toList()
        : <Map<String, dynamic>>[];
    arr.insert(0, {
      'ts': DateTime.now().toIso8601String(),
      'items': BioSpecies.listToJson(oldList),
    });
    if (arr.length > 50) arr.removeRange(50, arr.length);
    map[tankId] = arr;
    await setString(_kBioHistory, jsonEncode(map));
  }

  // ───────────── AI 分析记录（按缸，最新在前，上限 200 条） ─────────────
  static const _kAnalysis = 'analysis_json';

  Future<List<AnalysisRecord>> analysisOf(String tankId) async {
    final raw = await getString(_kAnalysis);
    if (raw == null || raw.isEmpty) return [];
    try {
      final map = (jsonDecode(raw) as Map).cast<String, dynamic>();
      final arr = map[tankId];
      return arr is List
          ? arr.map((e) => AnalysisRecord.fromJson(Map<String, dynamic>.from(e as Map))).toList()
          : [];
    } catch (_) {
      return [];
    }
  }

  Future<void> addAnalysis(String tankId, AnalysisRecord rec) async {
    final list = await analysisOf(tankId);
    list.insert(0, rec);
    if (list.length > 200) list.removeRange(200, list.length);
    final raw = await getString(_kAnalysis);
    final map = <String, dynamic>{};
    if (raw != null && raw.isNotEmpty) {
      try {
        map.addAll((jsonDecode(raw) as Map).cast<String, dynamic>());
      } catch (_) {}
    }
    map[tankId] = list.map((e) => e.toJson()).toList();
    await setString(_kAnalysis, jsonEncode(map));
  }
}
