/// 阈值告警引擎：本地评估遥测流，生成告警事件。
///
/// 规则要素（全部可在 App 内自定义，见 AlertRule）：
/// - 触发：越限持续 N 个周期（tel 帧去抖）
/// - 恢复：回限内持续 5 周期自动消除
/// - 冷却：同规则两次告警间隔 ≥ cooldownMin 分钟
/// - 免打扰：silentFrom~silentTo 时段内不推送（跨天支持）
library;

import '../models/records.dart';
import '../models/telemetry.dart';

class AlertEvent {
  AlertEvent({
    required this.ruleId,
    required this.metric,
    required this.message,
    required this.ts,
  });

  final String ruleId;
  final String metric;
  final String message;
  final DateTime ts;
}

class AlertEngine {
  AlertEngine(this._rules);

  final List<AlertRule> _rules;

  // ruleId → 持续越限计数
  final Map<String, int> _overStreak = {};
  // ruleId → 持续正常计数（恢复用）
  final Map<String, int> _okStreak = {};
  // ruleId → 上次告警时间（冷却用）
  final Map<String, DateTime> _lastFire = {};

  /// 输入一帧遥测，返回本次触发的告警事件（可能为空）
  List<AlertEvent> evaluate(Telemetry tel) {
    final fired = <AlertEvent>[];
    final now = DateTime.now();

    for (final r in _rules) {
      if (!r.enabled) continue;
      final v = _value(tel, r.metric);
      if (v == null) continue;

      final over = _isOver(r, v);
      if (over) {
        _okStreak[r.id] = 0;
        _overStreak[r.id] = (_overStreak[r.id] ?? 0) + 1;
        // 持续 N 次才触发；冷却期内不重复告警；免打扰时段不告警
        if (_overStreak[r.id] == r.holdN && !_inCooldown(r, now) && !_inSilent(r, now)) {
          _lastFire[r.id] = now;
          fired.add(AlertEvent(
            ruleId: r.id,
            metric: r.metric,
            message: _message(r, v),
            ts: now,
          ));
        }
      } else {
        _overStreak[r.id] = 0;
        _okStreak[r.id] = (_okStreak[r.id] ?? 0) + 1;
        if (_okStreak[r.id] == 5) {
          // 恢复（页面可据此清除横幅，此处不产生事件）
          _okStreak[r.id] = 0;
        }
      }
    }
    return fired;
  }

  double? _value(Telemetry t, String metric) {
    switch (metric) {
      case 'temp':
        return t.temp;
      case 'ph':
        return t.ph;
      case 'temp_ph':
        return t.tempPh;
      case 'tds1':
        return t.tds1;
      case 'tds2':
        return t.tds2;
      case 'lux':
        return t.lux;
      case 'lvl':
        return t.level;
      default:
        return null;
    }
  }

  bool _isOver(AlertRule r, double v) {
    if (r.mode == AlertRule.modeBaseline) {
      final base = r.baseline;
      final pct = r.pct;
      if (base == null || pct == null) return false;
      final lo = base * (1 - pct / 100);
      final hi = base * (1 + pct / 100);
      return v < lo || v > hi;
    }
    final lo = r.minVal;
    final hi = r.maxVal;
    return (lo != null && v < lo) || (hi != null && v > hi);
  }

  bool _inCooldown(AlertRule r, DateTime now) {
    final last = _lastFire[r.id];
    if (last == null) return false;
    return now.difference(last).inMinutes < r.cooldownMin;
  }

  /// 免打扰时段判断（支持跨天，如 23:00~07:00）
  bool _inSilent(AlertRule r, DateTime now) {
    final from = r.silentFrom;
    final to = r.silentTo;
    if (from == null || to == null || from.isEmpty || to.isEmpty) return false;
    final minutes = now.hour * 60 + now.minute;
    final f = _parseHm(from);
    final t = _parseHm(to);
    if (f == null || t == null) return false;
    if (f <= t) {
      return minutes >= f && minutes < t;
    }
    return minutes >= f || minutes < t; // 跨天
  }

  int? _parseHm(String s) {
    final p = s.split(':');
    if (p.length != 2) return null;
    final h = int.tryParse(p[0]);
    final m = int.tryParse(p[1]);
    if (h == null || m == null) return null;
    return h * 60 + m;
  }

  String _message(AlertRule r, double v) {
    final desc = r.mode == AlertRule.modeBaseline
        ? '基线 ${r.baseline} ±${r.pct}%'
        : '${r.minVal ?? '-∞'} ~ ${r.maxVal ?? '+∞'}';
    return '指标 ${r.metric} 当前 $v 越限（$desc），已持续 ${r.holdN} 个周期，请检查。';
  }
}
