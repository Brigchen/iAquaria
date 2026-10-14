/// 养护日志页：时间线 + 类型筛选 + 手动/自动记录 + 人工水质检测 + 导出。
///
/// 页面顶部提供常驻操作按钮（水质检测 / 新增记录 / 导出），不依赖悬浮按钮；
/// 导出分「导出日志」（CSV）与「导出数据」（本机保存的遥测+人工测量 CSV）。
library;

import 'dart:convert';
import 'dart:io';

import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:path_provider/path_provider.dart';

import '../app.dart';
import '../core/metrics.dart';
import '../core/theme.dart';
import '../models/records.dart';
import '../services/local_data_service.dart';

class JournalPage extends StatefulWidget {
  const JournalPage({super.key});

  @override
  State<JournalPage> createState() => _JournalPageState();
}

class _JournalPageState extends State<JournalPage> {
  String _filter = '全部';
  bool _last48h = true; // true=最近48小时；false=全部历史

  static const _types = [
    '全部',
    JournalEntry.typeWater,
    JournalEntry.typeChange,
    JournalEntry.typeFeed,
    JournalEntry.typeMaintain,
    JournalEntry.typeDevice,
    JournalEntry.typeOther
  ];

  @override
  Widget build(BuildContext context) {
    final store = AppStore.instance;
    return AnimatedBuilder(
      animation: store,
      builder: (context, _) {
        // 注意：必须在 builder 内读取，IndexedStack 常驻页面首帧时缸列表尚未加载，
        // 若在 build 外捕获会导致按钮永远禁用（切页后 store 通知只重建 builder）
        final tank = store.activeTank;
        return FutureBuilder<List<JournalEntry>>(
          future: tank == null ? Future.value([]) : store.st.journals(tank.id),
          builder: (context, snap) {
            var all = snap.data ?? const <JournalEntry>[];
            // 时间范围：最近 48 小时 / 全部历史
            if (_last48h) {
              final cutoff = DateTime.now().subtract(const Duration(hours: 48));
              all = all.where((e) => e.ts.isAfter(cutoff)).toList();
            }
            final list = _filter == '全部'
                ? all
                : all.where((e) => e.type == _filter).toList();
            return Scaffold(
              // 顶部常驻按钮已覆盖新增/导出，不再放悬浮按钮避免重复
              body: Column(
                children: [
                  // 常驻操作按钮（不依赖悬浮按钮，始终可见可点）
                  Padding(
                    padding: const EdgeInsets.fromLTRB(14, 8, 14, 0),
                    child: Row(
                      children: [
                        Expanded(
                          child: OutlinedButton.icon(
                            style: OutlinedButton.styleFrom(
                              foregroundColor: AppTheme.tealDark,
                              side: const BorderSide(color: AppTheme.teal),
                              padding: const EdgeInsets.symmetric(vertical: 4),
                            ),
                            onPressed: tank == null
                                ? null
                                : () => _newWaterMeasure(context, tank.id),
                            icon: const Icon(Icons.science, size: 16),
                            label: const Text('水质检测',
                                style: TextStyle(fontSize: 12.5)),
                          ),
                        ),
                        const SizedBox(width: 8),
                        Expanded(
                          child: OutlinedButton.icon(
                            style: OutlinedButton.styleFrom(
                              foregroundColor: AppTheme.tealDark,
                              side: const BorderSide(color: AppTheme.teal),
                              padding: const EdgeInsets.symmetric(vertical: 4),
                            ),
                            onPressed: tank == null
                                ? null
                                : () => _newRecord(context, tank.id),
                            icon: const Icon(Icons.add, size: 16),
                            label: const Text('新增记录',
                                style: TextStyle(fontSize: 12.5)),
                          ),
                        ),
                        const SizedBox(width: 8),
                        Expanded(
                          child: OutlinedButton.icon(
                            style: OutlinedButton.styleFrom(
                              foregroundColor: AppTheme.tealDark,
                              side: const BorderSide(color: AppTheme.teal),
                              padding: const EdgeInsets.symmetric(vertical: 4),
                            ),
                            onPressed: tank == null
                                ? null
                                : () => _exportDialog(context),
                            icon: const Icon(Icons.ios_share, size: 15),
                            label: const Text('导出',
                                style: TextStyle(fontSize: 12.5)),
                          ),
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(height: 6),
                  // 时间范围 + 类型筛选条
                  SizedBox(
                    height: 40,
                    child: ListView(
                      scrollDirection: Axis.horizontal,
                      padding: const EdgeInsets.symmetric(horizontal: 14),
                      children: [
                        Padding(
                          padding: const EdgeInsets.only(right: 8),
                          child: ChoiceChip(
                            label: Text(_last48h ? '范围：48小时内' : '范围：全部历史',
                                style: const TextStyle(
                                    fontSize: 12, fontWeight: FontWeight.w600)),
                            selected: true,
                            selectedColor: AppTheme.tealLight,
                            onSelected: (_) =>
                                setState(() => _last48h = !_last48h),
                          ),
                        ),
                        ..._types
                            .map((t) => Padding(
                                  padding: const EdgeInsets.only(right: 8),
                                  child: ChoiceChip(
                                    label: Text(t,
                                        style: const TextStyle(fontSize: 12)),
                                    selected: _filter == t,
                                    selectedColor: AppTheme.tealLight,
                                    onSelected: (_) =>
                                        setState(() => _filter = t),
                                  ),
                                ))
                            .toList(),
                      ],
                    ),
                  ),
                  Expanded(
                    child: list.isEmpty
                        ? Center(
                            child: Text(
                            _last48h
                                ? '48小时内暂无记录，可切换到全部历史'
                                : '暂无记录，点上方「新增记录」添加',
                            style: const TextStyle(
                                color: AppTheme.muted, fontSize: 12.5),
                          ))
                        : ListView.separated(
                            padding: const EdgeInsets.all(14),
                            itemCount: list.length,
                            separatorBuilder: (_, __) =>
                                const SizedBox(height: 8),
                            itemBuilder: (_, i) =>
                                _item(context, tank?.id ?? '', list[i]),
                          ),
                  ),
                ],
              ),
            );
          },
        );
      },
    );
  }

  Widget _item(BuildContext context, String tankId, JournalEntry e) {
    final time =
        '${e.ts.month}/${e.ts.day} ${e.ts.hour.toString().padLeft(2, '0')}:${e.ts.minute.toString().padLeft(2, '0')}';
    // 长按删除：误输入/错误记录可清理（不影响设备自动记录的重新生成）
    return GestureDetector(
      onLongPress: () => _confirmDelete(context, tankId, e),
      child: Container(
        padding: const EdgeInsets.all(12),
        decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.circular(12),
          border: Border.all(color: const Color(0xFFe2e8f0)),
        ),
        child: Row(
          children: [
            Container(
              width: 38,
              height: 38,
              alignment: Alignment.center,
              decoration: BoxDecoration(
                  color: AppTheme.tealLight,
                  borderRadius: BorderRadius.circular(10)),
              child: Text(e.type.characters.first,
                  style: const TextStyle(
                      color: AppTheme.tealDark, fontWeight: FontWeight.bold)),
            ),
            const SizedBox(width: 10),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(children: [
                    Text(e.type,
                        style: const TextStyle(
                            fontWeight: FontWeight.w700, fontSize: 13.5)),
                    if (e.auto)
                      Container(
                        margin: const EdgeInsets.only(left: 6),
                        padding: const EdgeInsets.symmetric(
                            horizontal: 6, vertical: 1),
                        decoration: BoxDecoration(
                            color: AppTheme.tealLight,
                            borderRadius: BorderRadius.circular(6)),
                        child: const Text('自动',
                            style: TextStyle(
                                fontSize: 10, color: AppTheme.tealDark)),
                      ),
                  ]),
                  const SizedBox(height: 2),
                  Text(e.note,
                      style: const TextStyle(
                          fontSize: 12.5, color: AppTheme.muted)),
                ],
              ),
            ),
            Text(time,
                style: const TextStyle(fontSize: 11, color: AppTheme.muted)),
          ],
        ),
      ),
    );
  }

  // ───────────── 长按删除 ─────────────

  Future<void> _confirmDelete(
      BuildContext context, String tankId, JournalEntry e) async {
    final ok = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('删除这条记录？'),
        content: Text(
            '「${e.type}」${e.note.length > 40 ? '${e.note.substring(0, 40)}…' : e.note}\n\n删除后不可恢复。',
            style: const TextStyle(fontSize: 13)),
        actions: [
          TextButton(
              onPressed: () => Navigator.pop(ctx, false),
              child: const Text('取消')),
          FilledButton(
            style: FilledButton.styleFrom(backgroundColor: AppTheme.danger),
            onPressed: () => Navigator.pop(ctx, true),
            child: const Text('删除'),
          ),
        ],
      ),
    );
    if (ok == true) {
      await AppStore.instance.st.deleteJournal(tankId, e.id);
      if (mounted) setState(() {});
    }
  }

  // ───────────── 导出：日志 / 数据 两种 ─────────────

  void _exportDialog(BuildContext context) {
    showModalBottomSheet<void>(
      context: context,
      backgroundColor: Colors.white,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(16)),
      ),
      builder: (ctx) => SafeArea(
        child: Column(mainAxisSize: MainAxisSize.min, children: [
          const Padding(
            padding: EdgeInsets.all(14),
            child: Text('选择导出内容',
                style: TextStyle(fontSize: 14.5, fontWeight: FontWeight.w700)),
          ),
          ListTile(
            leading: const Icon(Icons.menu_book, color: AppTheme.tealDark),
            title: const Text('导出日志', style: TextStyle(fontSize: 13.5)),
            subtitle: const Text('养护记录时间线（人工 + 设备自动）',
                style: TextStyle(fontSize: 11.5)),
            onTap: () {
              Navigator.pop(ctx);
              final tank = AppStore.instance.activeTank;
              if (tank != null) _export(context, tank.id, tank.name);
            },
          ),
          ListTile(
            leading: const Icon(Icons.query_stats, color: AppTheme.tealDark),
            title: const Text('导出数据', style: TextStyle(fontSize: 13.5)),
            subtitle: const Text('本机保存的传感数据 + 人工水质测量（含自定义参数）',
                style: TextStyle(fontSize: 11.5)),
            onTap: () {
              Navigator.pop(ctx);
              final tank = AppStore.instance.activeTank;
              if (tank != null) _exportData(context, tank.id, tank.name);
            },
          ),
          const SizedBox(height: 8),
        ]),
      ),
    );
  }

  /// 通用 CSV 输出：三端统一弹系统「另存为」对话框，用户可自选保存目录与
  /// 文件名（Android/鸿蒙系统保存界面默认落在 Documents；Windows=另存为）。
  /// 默认文件名 = 类型_缸名_时间戳.csv。系统对话框异常时回退应用文档目录，
  /// 再失败兜底剪贴板。
  Future<void> _writeCsv(ScaffoldMessengerState messenger, String csv,
      String fileName, int rows) async {
    // 文件名安全清洗：缸名可能含路径非法字符；空缸名兜底，避免出现「日志_.csv」
    final safe = fileName
        .replaceAll(RegExp(r'[\\/:*?"<>|]'), '-')
        .replaceAll(RegExp(r'\s+'), '')
        .trim();
    final base = safe.isEmpty ? '未命名缸' : safe;
    final stamp = DateTime.now()
        .toIso8601String()
        .substring(0, 19)
        .replaceAll(RegExp('[:T]'), '-');
    final name = '${base}_$stamp';
    final bytes = Uint8List.fromList(utf8.encode(csv));
    try {
      final path = await FilePicker.platform.saveFile(
        dialogTitle: '导出 CSV',
        fileName: '$name.csv',
        type: FileType.custom,
        allowedExtensions: ['csv'],
        bytes: bytes, // Windows/Android：插件直接写入所选位置
      );
      if (path == null) return; // 用户取消另存为
      // 鸿蒙 saveFile 只返回所选路径不写内容：文件不存在或为空时补写
      final f = File(path);
      if (!f.existsSync() || f.lengthSync() == 0) {
        try {
          await f.writeAsBytes(bytes);
        } catch (_) {}
      }
      messenger.showSnackBar(SnackBar(
          content: Text('已导出 $rows 行：$path'),
          duration: const Duration(seconds: 5),
          behavior: SnackBarBehavior.floating));
      return;
    } catch (_) {
      // 系统对话框不可用（平台异常）：回退应用文档目录
    }
    try {
      final docs = await getApplicationDocumentsDirectory();
      final dir = Directory('${docs.path}${Platform.pathSeparator}iAquaria');
      if (!dir.existsSync()) dir.createSync(recursive: true);
      final f = File('${dir.path}${Platform.pathSeparator}$name.csv');
      await f.writeAsBytes(bytes);
      messenger.showSnackBar(SnackBar(
          content: Text('已导出 $rows 行：${f.path}'),
          duration: const Duration(seconds: 5),
          behavior: SnackBarBehavior.floating));
    } catch (_) {
      await Clipboard.setData(ClipboardData(text: csv));
      messenger.showSnackBar(const SnackBar(
          content: Text('写文件失败，已复制到剪贴板'), behavior: SnackBarBehavior.floating));
    }
  }

  /// 导出当前缸全部日志为 CSV（带 BOM，Excel 可直接打开）
  Future<void> _export(
      BuildContext context, String tankId, String tankName) async {
    final messenger = ScaffoldMessenger.of(context);
    final all = await AppStore.instance.st.journals(tankId);
    if (all.isEmpty) {
      messenger.showSnackBar(const SnackBar(
          content: Text('暂无日志可导出'), behavior: SnackBarBehavior.floating));
      return;
    }
    final sb = StringBuffer('\uFEFF时间,类型,来源,内容\r\n');
    for (final e in all) {
      final ts = e.ts.toIso8601String().substring(0, 19).replaceAll('T', ' ');
      final note = e.note.replaceAll(',', '，').replaceAll('\n', ' ');
      sb.writeln('$ts,${e.type},${e.auto ? "设备自动" : "人工"},$note');
    }
    await _writeCsv(messenger, sb.toString(), '日志_$tankName', all.length);
  }

  /// 导出当前缸本机数据（自动遥测 + 人工测量）为宽表 CSV：
  /// 列 = 时间/来源/固定参数（按协议键序）/自定义参数
  Future<void> _exportData(
      BuildContext context, String tankId, String tankName) async {
    final messenger = ScaffoldMessenger.of(context);
    final recs = await LocalDataService.instance.all(tankId);
    if (recs.isEmpty) {
      messenger.showSnackBar(const SnackBar(
          content: Text('本机暂无数据（联网同步或人工测量后积累）'),
          behavior: SnackBarBehavior.floating));
      return;
    }
    // 列集合：固定键在前，其余（自定义 c_* 等）按出现顺序追加
    const fixed = [
      'temp',
      'ph',
      'temp_ph',
      'tds1',
      'tds2',
      'lux',
      'lvl',
      'no3',
      'po4',
      'nh4',
      'kh',
      'ca'
    ];
    final extra = <String>[];
    for (final r in recs) {
      final v = Map<String, dynamic>.from(r['v'] as Map);
      for (final k in v.keys) {
        if (!fixed.contains(k) && !extra.contains(k)) extra.add(k);
      }
    }
    // 表头（含单位）
    final labelOf = <String, String>{
      'temp': '水温(℃)',
      'ph': 'pH',
      'temp_ph': '水温(pH)(℃)',
      'tds1': 'TDS1/盐度',
      'tds2': 'TDS2',
      'lux': '光照(lx)',
      'lvl': '水位(%)',
      'no3': '硝酸盐(mg/L)',
      'po4': '磷酸盐(mg/L)',
      'nh4': '铵盐(mg/L)',
      'kh': '碱度KH(dKH)',
      'ca': '钙(mg/L)',
    };
    final cols = [...fixed, ...extra];
    final srcName = {'lan': '局域网', 'cloud': '云端', 'manual': '人工'};
    final sb = StringBuffer(
        '\uFEFF时间,来源,${cols.map((k) => labelOf[k] ?? k).join(',')}\r\n');
    var n = 0;
    for (final r in recs) {
      final ts = DateTime.fromMillisecondsSinceEpoch((r['ts'] as int) * 1000)
          .toIso8601String()
          .substring(0, 19)
          .replaceAll('T', ' ');
      final v = Map<String, dynamic>.from(r['v'] as Map);
      final row = cols.map((k) => v[k] ?? '').join(',');
      sb.writeln('$ts,${srcName[r['src']] ?? r['src']},$row');
      n++;
    }
    // 写文件导出无行数限制
    await _writeCsv(messenger, sb.toString(), '数据_$tankName', n);
  }

  // ───────────── 新增：普通记录 ─────────────

  Future<void> _newRecord(BuildContext context, String tankId) async {
    final typeCtrl = TextEditingController(text: JournalEntry.typeChange);
    final noteCtrl = TextEditingController();
    final ok = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('新增记录'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            DropdownButtonFormField<String>(
              value: typeCtrl.text,
              // 水质检测走顶部独立按键（结构化表单），此处不再提供，避免重复入口
              items: const [
                DropdownMenuItem(
                    value: JournalEntry.typeChange,
                    child: Text(JournalEntry.typeChange)),
                DropdownMenuItem(
                    value: JournalEntry.typeFeed,
                    child: Text(JournalEntry.typeFeed)),
                DropdownMenuItem(
                    value: JournalEntry.typeMaintain,
                    child: Text(JournalEntry.typeMaintain)),
                DropdownMenuItem(
                    value: JournalEntry.typeOther,
                    child: Text(JournalEntry.typeOther)),
              ],
              onChanged: (v) => typeCtrl.text = v ?? JournalEntry.typeOther,
              decoration: const InputDecoration(labelText: '类型'),
            ),
            TextField(
                controller: noteCtrl,
                decoration:
                    const InputDecoration(labelText: '备注（如：换水 30%，GH6·KH8）')),
          ],
        ),
        actions: [
          TextButton(
              onPressed: () => Navigator.pop(ctx, false),
              child: const Text('取消')),
          FilledButton(
              onPressed: () => Navigator.pop(ctx, true),
              child: const Text('保存')),
        ],
      ),
    );
    if (ok == true) {
      await AppStore.instance.st.addJournal(JournalEntry(
        id: 'j_${DateTime.now().millisecondsSinceEpoch}',
        tankId: tankId,
        type: typeCtrl.text,
        note: noteCtrl.text.isEmpty ? '手动记录' : noteCtrl.text,
        ts: DateTime.now(),
      ));
      if (mounted) setState(() {});
    }
  }

  // ───────────── 新增：人工水质检测（含自定义参数，落本机数据 + 日志） ─────────────

  Future<void> _newWaterMeasure(BuildContext context, String tankId) async {
    final store = AppStore.instance;
    final wt = store.activeTank?.waterType;
    // 参数行定义：key / 显示名 / 单位（海水缸 tds1 为盐度，不显示 tds2）
    final params = <List<String>>[
      ['temp', '水温', '℃'],
      ['ph', 'pH', ''],
      ['temp_ph', '水温(pH)', '℃'],
      if (Metrics.isSalt(wt))
        ['tds1', '盐度', '‰']
      else ...[
        ['tds1', 'TDS(滤前)', 'ppm'],
        ['tds2', 'TDS(滤后)', 'ppm'],
      ],
      for (final p in kManualParams) [p['key']!, p['label']!, p['unit']!],
    ];
    // 自定义参数（本机记忆，跨次复用）
    final customs = await LocalDataService.instance.customMetrics();
    if (!context.mounted) return;
    for (final c in customs) {
      params.add(['c_${c['name']}', '${c['name']}', '${c['unit'] ?? ''}']);
    }
    final ctrls = <String, TextEditingController>{};

    final ok = await showDialog<bool>(
      context: context,
      builder: (ctx) => StatefulBuilder(
        builder: (ctx, setD) => AlertDialog(
          title: const Text('人工水质检测'),
          content: SizedBox(
            width: 320,
            child: ListView(
              shrinkWrap: true,
              children: [
                const Text('选填，留空的参数不会保存',
                    style: TextStyle(fontSize: 11.5, color: AppTheme.muted)),
                const SizedBox(height: 6),
                for (final p in params)
                  Padding(
                    padding: const EdgeInsets.only(bottom: 8),
                    child: TextField(
                      controller: ctrls.putIfAbsent(
                          p[0], () => TextEditingController()),
                      keyboardType:
                          const TextInputType.numberWithOptions(decimal: true),
                      decoration: InputDecoration(
                        labelText: '${p[1]}${p[2].isEmpty ? '' : '（${p[2]}）'}',
                        isDense: true,
                        border: const OutlineInputBorder(),
                      ),
                    ),
                  ),
                // 新增自定义参数：命名后立即加入表单并记忆
                TextButton.icon(
                  onPressed: () async {
                    final nameCtrl = TextEditingController();
                    final unitCtrl = TextEditingController();
                    final okC = await showDialog<bool>(
                      context: ctx,
                      builder: (ctx2) => AlertDialog(
                        title: const Text('自定义参数'),
                        content:
                            Column(mainAxisSize: MainAxisSize.min, children: [
                          TextField(
                              controller: nameCtrl,
                              decoration: const InputDecoration(
                                  labelText: '参数名（如：镁 Mg）')),
                          TextField(
                              controller: unitCtrl,
                              decoration: const InputDecoration(
                                  labelText: '单位（选填，如 mg/L）')),
                        ]),
                        actions: [
                          TextButton(
                              onPressed: () => Navigator.pop(ctx2, false),
                              child: const Text('取消')),
                          FilledButton(
                              onPressed: () => Navigator.pop(ctx2, true),
                              child: const Text('添加')),
                        ],
                      ),
                    );
                    if (okC == true && nameCtrl.text.trim().isNotEmpty) {
                      final name = nameCtrl.text.trim();
                      final unit = unitCtrl.text.trim();
                      // 记忆自定义参数（下次表单自动出现）
                      final list =
                          await LocalDataService.instance.customMetrics();
                      if (!list.any((e) => e['name'] == name)) {
                        list.add({'name': name, 'unit': unit});
                        await LocalDataService.instance.saveCustomMetrics(list);
                      }
                      setD(() => params.add(['c_$name', name, unit]));
                    }
                  },
                  icon: const Icon(Icons.add, size: 16),
                  label:
                      const Text('新增自定义参数', style: TextStyle(fontSize: 12.5)),
                ),
              ],
            ),
          ),
          actions: [
            TextButton(
                onPressed: () => Navigator.pop(ctx, false),
                child: const Text('取消')),
            FilledButton(
                onPressed: () => Navigator.pop(ctx, true),
                child: const Text('保存')),
          ],
        ),
      ),
    );
    if (ok != true) return;
    if (!context.mounted) return;
    // 收集有值的参数
    final vals = <String, double>{};
    final noteParts = <String>[];
    for (final p in params) {
      final c = ctrls[p[0]];
      final v = double.tryParse(c?.text.trim() ?? '');
      if (v == null) continue;
      vals[p[0]] = v;
      noteParts.add('${p[1]} $v${p[2]}');
    }
    if (vals.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(
          content: Text('未填写任何数值'), behavior: SnackBarBehavior.floating));
      return;
    }
    await AppStore.instance
        .addManualMeasurement(tankId, vals, '人工水质检测：${noteParts.join('、')}');
    if (mounted) setState(() {});
  }
}
