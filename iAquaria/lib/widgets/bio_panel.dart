/// 生物概览面板（概览页·水质参数上方）。
///
/// 左右两个数据板：生物种类（N 种）/ 鱼只数量（M 只，只统计「鱼」类群）；
/// 点击分别打开弹层：种类清单（类群/种名可改、可删、可新增）、
/// 鱼类数量调整（每种 −/+/输入 与总数）。
/// 数据源：AI 生物识别/清点回写（类群|种名|数量）+ 用户手动修正。
library;

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../app.dart';
import '../core/theme.dart';
import '../models/bio.dart';

class BioPanel extends StatelessWidget {
  const BioPanel({super.key});

  @override
  Widget build(BuildContext context) {
    final store = AppStore.instance;
    final bio = store.bio;
    final species = bio.length;
    // 鱼只数量只统计「鱼」类群（水草/珊瑚等不计数）
    final fish = bio.where((e) => e.group == '鱼').fold<int>(0, (s, e) => s + e.count);

    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: const Color(0xFFe2e8f0)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Row(
            children: [
              Text('生物概览',
                  style: TextStyle(fontSize: 13.5, fontWeight: FontWeight.w700)),
              SizedBox(width: 6),
              Expanded(
                child: Text('（AI 识别结果可点开修正）',
                    style: TextStyle(fontSize: 11, color: AppTheme.muted)),
              ),
            ],
          ),
          const SizedBox(height: 8),
          Row(
            children: [
              Expanded(
                child: _statCard(
                  icon: Icons.pets,
                  value: '$species',
                  unit: '种',
                  label: '生物种类',
                  onTap: () => _editSpecies(context),
                ),
              ),
              const SizedBox(width: 8),
              Expanded(
                child: _statCard(
                  icon: Icons.set_meal,
                  value: '$fish',
                  unit: '只',
                  label: '鱼只数量',
                  onTap: () => _editCounts(context),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  /// 单个数据板（左：种类 右：数量）
  Widget _statCard({
    required IconData icon,
    required String value,
    required String unit,
    required String label,
    required VoidCallback onTap,
  }) {
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(10),
      child: Container(
        padding: const EdgeInsets.symmetric(vertical: 10, horizontal: 12),
        decoration: BoxDecoration(
          color: AppTheme.tealLight.withOpacity(.45),
          borderRadius: BorderRadius.circular(10),
          border: Border.all(color: AppTheme.teal.withOpacity(.3)),
        ),
        child: Row(
          children: [
            Icon(icon, size: 22, color: AppTheme.tealDark),
            const SizedBox(width: 8),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    crossAxisAlignment: CrossAxisAlignment.baseline,
                    textBaseline: TextBaseline.alphabetic,
                    children: [
                      Text(value,
                          style: const TextStyle(
                              fontSize: 20, fontWeight: FontWeight.w800, color: AppTheme.tealDark)),
                      const SizedBox(width: 3),
                      Text(unit, style: const TextStyle(fontSize: 11.5, color: AppTheme.muted)),
                    ],
                  ),
                  Text(label, style: const TextStyle(fontSize: 11, color: AppTheme.muted)),
                ],
              ),
            ),
            const Icon(Icons.chevron_right, size: 18, color: AppTheme.muted),
          ],
        ),
      ),
    );
  }

  // ───────────── 弹层 A：种类清单（类群/种名可改、删除、新增） ─────────────

  void _editSpecies(BuildContext context) {
    final store = AppStore.instance;
    // 弹层内工作副本，确认时一次性保存
    final list = store.bio
        .map((e) => BioSpecies(name: e.name, count: e.count, group: e.group))
        .toList();
    showModalBottomSheet<void>(
      context: context,
      backgroundColor: Colors.white,
      isScrollControlled: true,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(16)),
      ),
      builder: (ctx) => StatefulBuilder(
        builder: (ctx, setSheet) => SafeArea(
          child: SizedBox(
            height: 480,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Padding(
                  padding: const EdgeInsets.fromLTRB(16, 14, 8, 8),
                  child: Row(
                    children: [
                      const Expanded(
                        child: Text('生物种类清单',
                            style: TextStyle(fontSize: 14.5, fontWeight: FontWeight.w700)),
                      ),
                      // 历史版本：修改时自动按时间点存档，可回看/恢复
                      IconButton(
                        tooltip: '历史版本',
                        icon: const Icon(Icons.history, size: 20),
                        color: AppTheme.tealDark,
                        onPressed: () => _showHistory(ctx),
                      ),
                      TextButton.icon(
                        onPressed: () =>
                            setSheet(() => list.add(BioSpecies(name: '', count: 0, group: '鱼'))),
                        icon: const Icon(Icons.add, size: 16),
                        label: const Text('新增', style: TextStyle(fontSize: 12.5)),
                      ),
                    ],
                  ),
                ),
                const Divider(height: 1),
                Expanded(
                  child: list.isEmpty
                      ? const Center(
                          child: Text('暂无记录，可新增或在 AI 分析中识别',
                              style: TextStyle(fontSize: 12.5, color: AppTheme.muted)))
                      : ListView.separated(
                          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                          itemCount: list.length,
                          separatorBuilder: (_, __) => const SizedBox(height: 6),
                          itemBuilder: (_, i) => Row(
                            children: [
                              // 二级分类下拉（预定类群）
                              _groupPicker(
                                value: list[i].group,
                                onChanged: (v) => setSheet(() => list[i].group = v),
                              ),
                              const SizedBox(width: 6),
                              Expanded(
                                child: TextField(
                                  controller:
                                      TextEditingController(text: list[i].name)..selection =
                                          TextSelection.collapsed(offset: list[i].name.length),
                                  style: const TextStyle(fontSize: 13),
                                  decoration: const InputDecoration(
                                    isDense: true,
                                    hintText: '种名（如：斑马鱼 / 莫斯）',
                                    filled: true,
                                    fillColor: Color(0xFFF4F7F7),
                                    contentPadding: EdgeInsets.symmetric(horizontal: 10, vertical: 9),
                                    border: OutlineInputBorder(borderSide: BorderSide.none),
                                  ),
                                  onChanged: (v) => list[i].name = v,
                                ),
                              ),
                              IconButton(
                                visualDensity: VisualDensity.compact,
                                icon: Icon(Icons.remove_circle_outline,
                                    size: 20, color: Colors.red.shade300),
                                onPressed: () => setSheet(() => list.removeAt(i)),
                              ),
                            ],
                          ),
                        ),
                ),
                // 确认保存
                Padding(
                  padding: const EdgeInsets.fromLTRB(16, 4, 16, 12),
                  child: SizedBox(
                    width: double.infinity,
                    child: FilledButton(
                      style: FilledButton.styleFrom(backgroundColor: AppTheme.tealDark),
                      onPressed: () {
                        // 过滤掉名称为空的行
                        final clean = list.where((e) => e.name.trim().isNotEmpty).toList();
                        for (final e in clean) {
                          e.name = e.name.trim();
                          e.normalizeGroup();
                        }
                        store.updateBio(clean);
                        Navigator.pop(ctx);
                      },
                      child: const Text('保存清单'),
                    ),
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  /// 历史版本：每次修改前的清单快照（最新在前），可一键恢复
  Future<void> _showHistory(BuildContext context) async {
    final store = AppStore.instance;
    final tank = store.activeTank;
    if (tank == null) return;
    final hist = await store.st.bioHistoryOf(tank.id);
    if (!context.mounted) return;
    showModalBottomSheet<void>(
      context: context,
      backgroundColor: Colors.white,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(16)),
      ),
      builder: (ctx) => SafeArea(
        child: SizedBox(
          height: 420,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Padding(
                padding: EdgeInsets.all(14),
                child: Text('生物清单历史版本',
                    style: TextStyle(fontSize: 14.5, fontWeight: FontWeight.w700)),
              ),
              const Divider(height: 1),
              Expanded(
                child: hist.isEmpty
                    ? const Center(
                        child: Text('暂无历史版本（修改清单后自动按时间点存档）',
                            style: TextStyle(fontSize: 12.5, color: AppTheme.muted)))
                    : ListView.separated(
                        padding: const EdgeInsets.symmetric(vertical: 6),
                        itemCount: hist.length,
                        separatorBuilder: (_, __) => const Divider(height: 1),
                        itemBuilder: (_, i) {
                          final snap = hist[i];
                          final items = (snap['items'] as List? ?? const [])
                              .map((e) => BioSpecies.fromJson(Map<String, dynamic>.from(e as Map)))
                              .toList();
                          final ts = DateTime.tryParse('${snap['ts'] ?? ''}');
                          final time = ts == null
                              ? ''
                              : '${ts.month}/${ts.day} ${ts.hour.toString().padLeft(2, '0')}:${ts.minute.toString().padLeft(2, '0')}';
                          // 摘要：前 3 项「种名×数」
                          final brief = items
                              .take(3)
                              .map((e) => '${e.name}×${e.count}')
                              .join('、');
                          return ListTile(
                            dense: true,
                            title: Text(time,
                                style: const TextStyle(
                                    fontSize: 13, fontWeight: FontWeight.w600)),
                            subtitle: Text(
                                '${items.length} 项${brief.isEmpty ? '' : '：$brief${items.length > 3 ? " …" : ""}'}',
                                style: const TextStyle(
                                    fontSize: 11.5, color: AppTheme.muted)),
                            trailing: TextButton(
                              onPressed: () {
                                store.updateBio(items);
                                Navigator.pop(ctx);
                                Navigator.pop(context); // 同时关闭清单弹层，回到面板
                              },
                              child: const Text('恢复',
                                  style: TextStyle(
                                      color: AppTheme.tealDark,
                                      fontWeight: FontWeight.w700)),
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

  /// 类群选择器（紧凑下拉）
  Widget _groupPicker({required String value, required ValueChanged<String> onChanged}) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8),
      decoration: BoxDecoration(
        color: AppTheme.tealLight.withOpacity(.6),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: AppTheme.teal.withOpacity(.4)),
      ),
      child: DropdownButtonHideUnderline(
        child: DropdownButton<String>(
          value: kBioGroups.contains(value) ? value : '鱼',
          items: [for (final g in kBioGroups) DropdownMenuItem(value: g, child: Text(g, style: const TextStyle(fontSize: 12.5)))],
          onChanged: (v) => v == null ? null : onChanged(v),
          style: const TextStyle(fontSize: 12.5, color: AppTheme.tealDark, fontWeight: FontWeight.w600),
          icon: const Icon(Icons.expand_more, size: 15, color: AppTheme.tealDark),
          borderRadius: BorderRadius.circular(10),
        ),
      ),
    );
  }

  // ───────────── 弹层 B：鱼只数量（只统计「鱼」类群） ─────────────

  void _editCounts(BuildContext context) {
    final store = AppStore.instance;
    // 仅鱼类条目参与计数（水草/珊瑚/软体/甲壳不在数量板调整，走种类清单）
    final list = store.bio
        .where((e) => e.group == '鱼')
        .map((e) => BioSpecies(name: e.name, count: e.count, group: e.group))
        .toList();
    showModalBottomSheet<void>(
      context: context,
      backgroundColor: Colors.white,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(16)),
      ),
      builder: (ctx) => StatefulBuilder(
        builder: (ctx, setSheet) {
          final total = list.fold<int>(0, (s, e) => s + e.count);
          return SafeArea(
            child: SizedBox(
              height: 460,
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Padding(
                    padding: const EdgeInsets.fromLTRB(16, 14, 16, 8),
                    child: Row(
                      children: [
                        const Expanded(
                          child: Text('鱼只数量',
                              style: TextStyle(fontSize: 14.5, fontWeight: FontWeight.w700)),
                        ),
                        Text('总数 $total 只',
                            style: const TextStyle(
                                fontSize: 12.5,
                                fontWeight: FontWeight.w700,
                                color: AppTheme.tealDark)),
                      ],
                    ),
                  ),
                  const Divider(height: 1),
                  Expanded(
                    child: list.isEmpty
                        ? const Center(
                            child: Text('暂无鱼类记录，可在 AI 分析（数量清点）后自动生成，或在种类清单中新增',
                                style: TextStyle(fontSize: 12.5, color: AppTheme.muted)))
                        : ListView.separated(
                            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                            itemCount: list.length,
                            separatorBuilder: (_, __) => const SizedBox(height: 6),
                            itemBuilder: (_, i) => Row(
                              children: [
                                Expanded(
                                  child: Text(list[i].name,
                                      style: const TextStyle(fontSize: 13)),
                                ),
                                // 数量步进：- n +
                                IconButton(
                                  visualDensity: VisualDensity.compact,
                                  icon: const Icon(Icons.remove_circle_outline, size: 20),
                                  color: AppTheme.tealDark,
                                  onPressed: list[i].count <= 0
                                      ? null
                                      : () => setSheet(() => list[i].count--),
                                ),
                                SizedBox(
                                  width: 46,
                                  child: TextField(
                                    textAlign: TextAlign.center,
                                    keyboardType: TextInputType.number,
                                    inputFormatters: [FilteringTextInputFormatter.digitsOnly],
                                    controller:
                                        TextEditingController(text: '${list[i].count}')..selection =
                                            TextSelection.collapsed(offset: '${list[i].count}'.length),
                                    style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w700),
                                    decoration: const InputDecoration(
                                      isDense: true,
                                      filled: true,
                                      fillColor: Color(0xFFF4F7F7),
                                      contentPadding: EdgeInsets.symmetric(vertical: 8),
                                      border: OutlineInputBorder(borderSide: BorderSide.none),
                                    ),
                                    onChanged: (v) =>
                                        list[i].count = int.tryParse(v) ?? list[i].count,
                                  ),
                                ),
                                IconButton(
                                  visualDensity: VisualDensity.compact,
                                  icon: const Icon(Icons.add_circle_outline, size: 20),
                                  color: AppTheme.tealDark,
                                  onPressed: () => setSheet(() => list[i].count++),
                                ),
                              ],
                            ),
                          ),
                  ),
                  Padding(
                    padding: const EdgeInsets.fromLTRB(16, 4, 16, 12),
                    child: SizedBox(
                      width: double.infinity,
                      child: FilledButton(
                        style: FilledButton.styleFrom(backgroundColor: AppTheme.tealDark),
                        onPressed: () {
                          // 数量弹层只改鱼类数量：按名称把工作副本数量写回全量清单
                          final byName = {for (final x in list) x.name: x.count};
                          final merged = [
                            for (final e in store.bio)
                              if (e.group == '鱼' && byName.containsKey(e.name))
                                e..count = byName[e.name]!
                              else
                                e,
                          ];
                          store.updateBio(merged);
                          Navigator.pop(ctx);
                        },
                        child: const Text('保存数量'),
                      ),
                    ),
                  ),
                ],
              ),
            ),
          );
        },
      ),
    );
  }
}
