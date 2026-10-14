/// 本地数据服务：遥测快照 + 人工水质测量的本地持久化（按缸分库）。
///
/// 设计要点：
/// - 局域网直连与云端 MQTT 收到的遥测统一落本地（来源标记 lan/cloud），
///   自动抽稀：同缸自动数据 ≥5 分钟才记一条，避免刷爆本地存储；
/// - 人工水质检测（含硝酸盐/磷酸盐/铵盐/碱度/钙与自定义参数）按时间点
///   立即保存（src=manual），与自动数据同库；
/// - 历史趋势直接读本服务（≤400 点二次抽稀），云端模式不再向设备下载；
/// - 无实时链路（人工缸 / 断连 / 云端未连）时，指标卡回退显示本机最近值；
/// - 超量自动压缩：3 天内保留 5 分钟粒度，更早保留 1 小时粒度，400 天截断。
library;

import 'dart:convert';

import 'package:shared_preferences/shared_preferences.dart';

import '../models/telemetry.dart';
import 'device_service.dart';

/// 人工测量的固定参数项（与设备自动参数互补的常规手测项）
const List<Map<String, String>> kManualParams = [
  {'key': 'no3', 'label': '硝酸盐 NO₃', 'unit': 'mg/L'},
  {'key': 'po4', 'label': '磷酸盐 PO₄', 'unit': 'mg/L'},
  {'key': 'nh4', 'label': '铵盐 NH₃/NH₄', 'unit': 'mg/L'},
  {'key': 'kh', 'label': '碱度 KH', 'unit': 'dKH'},
  {'key': 'ca', 'label': '钙 Ca', 'unit': 'mg/L'},
];

/// 自动参数（协议键 → 显示名/单位），人工表单与导出共用
const List<Map<String, String>> kAutoParams = [
  {'key': 'temp', 'label': '水温', 'unit': '℃'},
  {'key': 'ph', 'label': 'pH', 'unit': ''},
  {'key': 'temp_ph', 'label': '水温(pH)', 'unit': '℃'},
  {'key': 'tds1', 'label': 'TDS(滤前)/盐度', 'unit': 'ppm'},
  {'key': 'tds2', 'label': 'TDS(滤后)', 'unit': 'ppm'},
];

class LocalDataService {
  LocalDataService._();
  static final LocalDataService instance = LocalDataService._();

  static const _kPrefix = 'tel_hist_';
  static const _kCustom = 'custom_metrics_json';

  /// 每缸记录条数上限（超过触发压缩）
  static const int _cap = 6000;

  /// 自动数据最小记录间隔（秒）
  static const int _minAutoGap = 300;

  Future<SharedPreferences> get _prefs => SharedPreferences.getInstance();

  // ───────────── 原始读写 ─────────────

  /// 读取某缸全部记录（按时间升序）：{ts, src, v:{key: value}}
  Future<List<Map<String, dynamic>>> all(String tankId) async {
    final raw = (await _prefs).getString('$_kPrefix$tankId');
    if (raw == null || raw.isEmpty) return [];
    try {
      final list = (jsonDecode(raw) as List)
          .map((e) => Map<String, dynamic>.from(e as Map))
          .toList();
      list.sort((a, b) => (a['ts'] as int).compareTo(b['ts'] as int));
      return list;
    } catch (_) {
      return [];
    }
  }

  Future<void> _write(String tankId, List<Map<String, dynamic>> list) async {
    list.sort((a, b) => (a['ts'] as int).compareTo(b['ts'] as int));
    await (await _prefs).setString('$_kPrefix$tankId', jsonEncode(list));
  }

  // ───────────── 写入：自动遥测 / 人工测量 ─────────────

  /// 自动遥测落库（局域网/云端共用；≤5 分钟一条，空快照跳过）
  Future<void> addAuto(String tankId, Telemetry tel, String src) async {
    if (tel.isEmpty) return;
    final v = <String, dynamic>{
      'temp': tel.temp,
      'ph': tel.ph,
      'temp_ph': tel.tempPh,
      'tds1': tel.tds1,
      'tds2': tel.tds2,
      'lux': tel.lux,
      'lvl': tel.level,
    };
    final list = await all(tankId);
    final now = DateTime.now().millisecondsSinceEpoch ~/ 1000;
    // 节流：最后一条（含人工）距今不足 5 分钟则跳过
    // （云端 30s 一帧、WS 数秒一帧；人工测量不受此限制，addManual 直接落库）
    if (list.isNotEmpty && now - (list.last['ts'] as int) < _minAutoGap) {
      return;
    }
    v.removeWhere((_, val) => val == null);
    list.add({'ts': now, 'src': src, 'v': v});
    await _compact(tankId, list);
  }

  /// 人工测量落库（立即保存，允许自定义参数键）
  Future<void> addManual(String tankId, Map<String, double> vals) async {
    if (vals.isEmpty) return;
    final list = await all(tankId);
    final now = DateTime.now().millisecondsSinceEpoch ~/ 1000;
    list.add({'ts': now, 'src': 'manual', 'v': vals});
    await _compact(tankId, list);
  }

  /// 设备历史帧回填（局域网查询 hist 后种子本地，近重复 4 分钟内去重）
  Future<void> seedHist(String tankId, HistResult h) async {
    if (h.ts.isEmpty) return;
    final list = await all(tankId);
    final tsList = list.map((e) => e['ts'] as int).toList();
    const keys = ['temp', 'ph', 'temp_ph', 'tds1', 'tds2', 'lux', 'lvl'];
    var added = 0;
    for (var i = 0; i < h.ts.length; i++) {
      final ts = h.ts[i];
      if (tsList.any((t) => (t - ts).abs() < 240)) continue;
      final v = <String, dynamic>{};
      for (final k in keys) {
        final s = h.series[k];
        if (s != null && i < s.length && s[i] != null) v[k] = s[i];
      }
      if (v.isEmpty) continue;
      list.add({'ts': ts, 'src': 'lan', 'v': v});
      added++;
    }
    if (added > 0) await _compact(tankId, list);
  }

  /// 压缩：>6000 条时，3 天内全保，更早按 1 小时取 1 条，400 天截断
  Future<void> _compact(String tankId, List<Map<String, dynamic>> list) async {
    if (list.length <= _cap) {
      await _write(tankId, list);
      return;
    }
    final now = DateTime.now().millisecondsSinceEpoch ~/ 1000;
    final keep = <Map<String, dynamic>>[];
    final hourSeen = <int>{};
    for (final r in list) {
      final ts = r['ts'] as int;
      final age = now - ts;
      if (age > 400 * 86400) continue; // 超 400 天丢弃
      if (r['src'] == 'manual' || age <= 3 * 86400) {
        keep.add(r); // 人工数据与近 3 天全保
        continue;
      }
      if (hourSeen.add(ts ~/ 3600)) keep.add(r); // 更早：每小时 1 条
    }
    await _write(tankId, keep);
  }

  // ───────────── 读取：趋势 / 最近值 ─────────────

  /// 读取趋势数据：指定小时范围内 ≤400 点抽稀（各序列与 ts 对齐，缺测为 null）
  Future<HistResult> readSeries(String tankId, int hours) async {
    final recs = await all(tankId);
    const keys = ['temp', 'ph', 'temp_ph', 'tds1', 'tds2', 'lux', 'lvl'];
    final series = <String, List<double?>>{
      for (final k in keys) k: <double?>[]
    };
    if (recs.isEmpty)
      return HistResult(hours: hours, ts: const [], series: series);

    final now = DateTime.now().millisecondsSinceEpoch ~/ 1000;
    final cutoff = now - hours * 3600;
    final span = (hours * 3600) / 400;
    // 分桶：每桶保留最新一条（时间升序遍历，后写覆盖）
    final buckets = List<Map<String, dynamic>?>.filled(400, null);
    for (final r in recs) {
      final ts = r['ts'] as int;
      if (ts < cutoff) continue;
      final idx = ((ts - cutoff) / span).floor().clamp(0, 399);
      buckets[idx] = r;
    }
    final tsOut = <int>[];
    for (final b in buckets) {
      if (b == null) continue;
      tsOut.add(b['ts'] as int);
      final v = Map<String, dynamic>.from(b['v'] as Map);
      for (final k in keys) {
        series[k]!.add((v[k] as num?)?.toDouble());
      }
    }
    return HistResult(hours: hours, ts: tsOut, series: series);
  }

  /// 本机最近一次各参数值（从新到旧逐条合并，人工+自动同源）
  Future<Map<String, double>> latest(String tankId) async {
    final recs = await all(tankId);
    final out = <String, double>{};
    for (final r in recs.reversed) {
      final v = Map<String, dynamic>.from(r['v'] as Map);
      v.forEach((k, val) {
        if (!out.containsKey(k) && val is num) out[k] = val.toDouble();
      });
    }
    return out;
  }

  // ───────────── 自定义测量参数 ─────────────

  /// 自定义参数清单：[{name, unit}]
  Future<List<Map<String, dynamic>>> customMetrics() async {
    final raw = (await _prefs).getString(_kCustom);
    if (raw == null || raw.isEmpty) return [];
    try {
      return (jsonDecode(raw) as List)
          .map((e) => Map<String, dynamic>.from(e as Map))
          .toList();
    } catch (_) {
      return [];
    }
  }

  Future<void> saveCustomMetrics(List<Map<String, dynamic>> v) async {
    await (await _prefs).setString(_kCustom, jsonEncode(v));
  }
}
