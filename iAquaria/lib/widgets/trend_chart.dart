/// 趋势图（自绘 CustomPainter，无第三方图表依赖，OHOS/Android/桌面通用）：
/// - 各序列独立 min-max 归一化到 0..1（与设备 Web 面板一致）
/// - 缺测点（null）断开曲线
/// - 数据由设备端抽稀（≤400 点/序列），App 不再二次抽稀
library;

import 'package:flutter/material.dart';

import '../core/theme.dart';

class SeriesStyle {
  const SeriesStyle(this.key, this.label, this.color);
  final String key;
  final String label;
  final Color color;
}

/// 与固件 HistStore 输出的 7 序列一一对应
const kSeriesStyles = <SeriesStyle>[
  SeriesStyle('temp', '水温', Color(0xFFef4444)),
  SeriesStyle('ph', 'pH', Color(0xFF8b5cf6)),
  SeriesStyle('temp_ph', '水温(pH)', Color(0xFFb45309)),
  SeriesStyle('tds1', 'TDS1', Color(0xFF2563eb)),
  SeriesStyle('tds2', 'TDS2', Color(0xFF0d9488)),
  SeriesStyle('lux', '光照', Color(0xFFf59e0b)),
  SeriesStyle('lvl', '水位', Color(0xFF16a34a)),
];

class TrendChart extends StatefulWidget {
  const TrendChart({
    super.key,
    required this.ts,
    required this.series,
    required this.hours,
    this.height = 190,
  });

  final List<int> ts;

  /// key → 归一化前原始序列（与 ts 等长，可含 null）
  final Map<String, List<double?>> series;
  final int hours;
  final double height;

  @override
  State<TrendChart> createState() => _TrendChartState();
}

class _TrendChartState extends State<TrendChart> {
  /// 用户点击图例关闭的序列（默认全开）
  final Set<String> _hidden = {};

  @override
  Widget build(BuildContext context) {
    // 图例集合：有数据的序列（无论开关，供点击切换）
    final legend = <SeriesStyle>[];
    for (final s in kSeriesStyles) {
      final list = widget.series[s.key];
      if (list == null) continue;
      if (list.any((v) => v != null)) legend.add(s);
    }
    if (widget.ts.isEmpty || legend.isEmpty) {
      return const SizedBox(
        height: 190,
        child: Center(
          child: Text('暂无历史数据（设备存储每 30 分钟记录一次）',
              style: TextStyle(fontSize: 12, color: AppTheme.muted)),
        ),
      );
    }

    // 每序列 min-max 归一化（仅绘制未隐藏的序列）
    final normalized = <SeriesStyle, List<double?>>{};
    final ranges = <SeriesStyle, List<double>>{};
    for (final s in legend) {
      final list = widget.series[s.key]!;
      double? mn, mx;
      for (final v in list) {
        if (v == null) continue;
        if (mn == null || v < mn) mn = v;
        if (mx == null || v > mx) mx = v;
      }
      if (mn == null || mx == null) continue;
      final mnF = mn;
      final mxF = mx;
      final span = (mxF - mnF) < 1e-6 ? 1.0 : (mxF - mnF);
      if (!_hidden.contains(s.key)) {
        normalized[s] =
            list.map((v) => v == null ? null : (v - mnF) / span).toList();
      }
      ranges[s] = [mnF, mxF];
    }

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        SizedBox(
          height: widget.height,
          child: CustomPaint(
            painter: _TrendPainter(
              ts: widget.ts,
              series: normalized,
              hours: widget.hours,
            ),
            size: Size.infinite,
          ),
        ),
        const SizedBox(height: 6),
        // 彩色可点击图例：圆点 + 名称 + 数值区间；点击切换显示/隐藏
        Wrap(
          spacing: 6,
          runSpacing: 4,
          children: [
            for (final s in legend)
              _LegendChip(
                style: s,
                range: ranges[s]!,
                off: _hidden.contains(s.key),
                onTap: () => setState(() {
                  if (!_hidden.remove(s.key)) _hidden.add(s.key);
                }),
              ),
          ],
        ),
      ],
    );
  }
}

class _LegendChip extends StatelessWidget {
  const _LegendChip({
    required this.style,
    required this.range,
    required this.off,
    required this.onTap,
  });

  final SeriesStyle style;
  final List<double> range;
  final bool off;
  final VoidCallback onTap;

  String get _rangeText {
    String f(double v) =>
        v >= 100 ? v.toStringAsFixed(0) : v.toStringAsFixed(2);
    return '${f(range[0])}~${f(range[1])}';
  }

  @override
  Widget build(BuildContext context) {
    final active = !off;
    return GestureDetector(
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 3),
        decoration: BoxDecoration(
          color:
              active ? style.color.withOpacity(.12) : const Color(0xFFf1f5f9),
          borderRadius: BorderRadius.circular(20),
          border: Border.all(
              color: active
                  ? style.color.withOpacity(.5)
                  : const Color(0xFFe2e8f0)),
        ),
        child: Row(mainAxisSize: MainAxisSize.min, children: [
          Container(
            width: 8,
            height: 8,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              color: active ? style.color : Colors.grey.shade400,
            ),
          ),
          const SizedBox(width: 4),
          Text('${style.label} $_rangeText',
              style: TextStyle(
                fontSize: 10,
                color: active ? AppTheme.tealDark : AppTheme.muted,
                fontWeight: active ? FontWeight.w600 : FontWeight.w400,
              )),
        ]),
      ),
    );
  }
}

class _TrendPainter extends CustomPainter {
  _TrendPainter({required this.ts, required this.series, required this.hours});
  final List<int> ts;
  final Map<SeriesStyle, List<double?>> series;
  final int hours;

  @override
  void paint(Canvas canvas, Size size) {
    // 网格背景
    final grid = Paint()
      ..color = const Color(0xFFeef2f5)
      ..strokeWidth = 1;
    for (var i = 0; i <= 4; i++) {
      final y = size.height * i / 4;
      canvas.drawLine(Offset(0, y), Offset(size.width, y), grid);
    }
    if (ts.length < 2) return;

    final t0 = ts.first * 1000;
    final t1 = ts.last * 1000;
    final span = (t1 - t0) < 1 ? 1.0 : (t1 - t0).toDouble();

    // X 轴时间标注（首/中/尾）
    final tp = TextPainter()..textDirection = TextDirection.ltr;
    void label(String s, double x, TextAlign align) {
      tp.text = TextSpan(
          text: s, style: const TextStyle(fontSize: 9, color: AppTheme.muted));
      tp.layout();
      final dx = align == TextAlign.left
          ? x
          : align == TextAlign.right
              ? x - tp.width
              : x - tp.width / 2;
      tp.paint(canvas, Offset(dx, size.height - 2));
    }

    final chartH = size.height - 14; // 底部留时间轴
    final dt0 = DateTime.fromMillisecondsSinceEpoch(t0);
    final dt1 = DateTime.fromMillisecondsSinceEpoch(t1);
    final dtm = DateTime.fromMillisecondsSinceEpoch((t0 + t1) ~/ 2);
    String fmt(DateTime t) {
      final hh = t.hour.toString().padLeft(2, '0');
      final mi = t.minute.toString().padLeft(2, '0');
      if (hours <= 24) return '$hh:$mi';
      final mm = t.month.toString().padLeft(2, '0');
      final dd = t.day.toString().padLeft(2, '0');
      return '$mm-$dd';
    }

    label(fmt(dt0), 2, TextAlign.left);
    label(fmt(dtm), size.width / 2, TextAlign.center);
    label(fmt(dt1), size.width - 2, TextAlign.right);

    // 各序列平滑曲线（中点二次贝塞尔；null 断开）
    for (final s in series.keys) {
      final list = series[s]!;
      final paint = Paint()
        ..color = s.color
        ..strokeWidth = 1.6
        ..style = PaintingStyle.stroke
        ..strokeCap = StrokeCap.round
        ..strokeJoin = StrokeJoin.round;
      final pts = <Offset>[];
      for (var i = 0; i < list.length && i < ts.length; i++) {
        final v = list[i];
        if (v == null) {
          _drawSmooth(canvas, pts, paint);
          pts.clear();
          continue;
        }
        final x = (ts[i] * 1000 - t0) / span * size.width;
        final y = (1 - v) * chartH;
        pts.add(Offset(x, y));
      }
      _drawSmooth(canvas, pts, paint);
    }
  }

  /// 中点平滑：相邻点连线取中点作为曲线锚点，原数据点作为控制点，
  /// 视觉平滑且曲线始终经过中点（不超出数据包络）
  void _drawSmooth(Canvas canvas, List<Offset> pts, Paint paint) {
    if (pts.isEmpty) return;
    if (pts.length == 1) {
      canvas.drawCircle(pts[0], 1.6, paint..style = PaintingStyle.fill);
      paint.style = PaintingStyle.stroke;
      return;
    }
    final path = Path()..moveTo(pts[0].dx, pts[0].dy);
    for (var i = 1; i < pts.length; i++) {
      final mid = Offset(
        (pts[i - 1].dx + pts[i].dx) / 2,
        (pts[i - 1].dy + pts[i].dy) / 2,
      );
      path.quadraticBezierTo(pts[i - 1].dx, pts[i - 1].dy, mid.dx, mid.dy);
    }
    path.lineTo(pts.last.dx, pts.last.dy);
    canvas.drawPath(path, paint);
  }

  @override
  bool shouldRepaint(covariant _TrendPainter old) =>
      old.ts != ts || old.series != series || old.hours != hours;
}
