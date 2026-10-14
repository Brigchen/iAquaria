/// 计划页：周期养护任务管理。
/// - 分组：已逾期 / 今天 / 即将到期（3 天内）/ 稍后（4 天起全量显示——
///   修复此前"新建任务 nextDue 超出 3 天不属任何分组导致整页空白"的 bug）
/// - 任务支持指定每日时刻（"HH:mm"，可选）；到点 App 内横幅提醒（每任务
///   每天至多一次）。三端一致的 App 内提醒，鸿蒙暂无系统通知插件支持
/// - 与日志联动：一键完成自动写入养护日志（维护类型，id 前缀 task_），
///   行内显示完成次数与最近完成时间，点行查看该任务的完成历史
/// - 长按任务：编辑 / 删除
library;

import 'dart:async';
import 'dart:convert';

import 'package:flutter/material.dart';

import '../app.dart';
import '../core/theme.dart';
import '../models/records.dart';

class PlanPage extends StatefulWidget {
  const PlanPage({super.key});
  @override
  State<PlanPage> createState() => _PlanPageState();
}

class _PlanPageState extends State<PlanPage> {
  Timer? _remindTimer;
  final Set<String> _reminded = {}; // 会话内已提醒标记 <taskId>_<yyyyMMdd>
  String _loadedTank = ''; // 完成统计已加载的缸 id（切缸时重载）
  int _loadedVer = 0; // 完成统计加载时的数据版本（云同步改写后重载）
  Map<String, List<JournalEntry>> _doneBy = {}; // 任务 id → 完成日志（最新在前）

  @override
  void initState() {
    super.initState();
    // IndexedStack 常驻页面：App 运行期间每分钟检查一次到期任务
    _remindTimer =
        Timer.periodic(const Duration(minutes: 1), (_) => _checkRemind());
    WidgetsBinding.instance.addPostFrameCallback((_) => _checkRemind());
  }

  @override
  void dispose() {
    _remindTimer?.cancel();
    super.dispose();
  }

  // ───────────── 到点提醒（App 内横幅，会话内每任务每天一次） ─────────────

  Future<void> _checkRemind() async {
    if (!mounted) return;
    final store = AppStore.instance;
    final tank = store.activeTank;
    if (tank == null) return;
    final tasks = await store.st.tasks(tank.id);
    if (!mounted) return;
    final now = DateTime.now();
    final ymd = '${now.year}${_p2(now.month)}${_p2(now.day)}';
    for (final t in tasks) {
      final key = '${t.id}_$ymd';
      if (_reminded.contains(key)) continue;
      final d = _daysTo(t);
      String? msg;
      if (d == 0) {
        if (t.time == null) {
          msg = '「${t.title}」今天到期，记得完成';
        } else if (now.isAfter(_at(t.time!))) {
          msg = '「${t.title}」已到计划时间 ${t.time}';
        }
      } else if (d < 0) {
        msg = '「${t.title}」已逾期 ${-d} 天，请尽快处理';
      }
      if (msg == null) continue;
      _reminded.add(key);
      final taskId = t.id;
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(
        behavior: SnackBarBehavior.floating,
        duration: const Duration(seconds: 6),
        content: Row(
          children: [
            const Icon(Icons.alarm, color: Colors.white, size: 18),
            const SizedBox(width: 8),
            Expanded(child: Text(msg, style: const TextStyle(fontSize: 13))),
          ],
        ),
        // 点击「去处理」：跳到计划页并弹出该任务的处理面板
        action: SnackBarAction(
          label: '去处理',
          textColor: Colors.white,
          onPressed: () => AppStore.instance.requestTask(taskId),
        ),
      ));
    }
  }

  /// 计划页 build 检测到待处理任务（提醒横幅跳转而来）→ 弹出处理面板。
  /// 每次只处理一次（取走 pendingTaskId，不回通知避免重入）。
  Future<void> _openPendingTask() async {
    final store = AppStore.instance;
    final taskId = store.pendingTaskId;
    if (taskId == null) return;
    store.pendingTaskId = null;
    final tank = store.activeTank;
    if (tank == null || !mounted) return;
    final tasks = await store.st.tasks(tank.id);
    if (!mounted) return;
    final hit = tasks.where((x) => x.id == taskId).toList();
    if (hit.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(
          content: Text('任务不存在或已删除'), behavior: SnackBarBehavior.floating));
      return;
    }
    final t = hit.first;
    final d = _daysTo(t);
    final dueText = d < 0
        ? '已逾期 ${-d} 天'
        : d == 0
            ? '今天到期${t.time == null ? '' : ' ${t.time}'}'
            : '$d 天后到期';
    showModalBottomSheet<void>(
      context: context,
      backgroundColor: Colors.white,
      shape: const RoundedRectangleBorder(
          borderRadius: BorderRadius.vertical(top: Radius.circular(16))),
      builder: (ctx) => SafeArea(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 16, 16, 4),
              child: Row(
                children: [
                  Expanded(
                    child: Text('「${t.title}」$dueText',
                        style: const TextStyle(
                            fontSize: 14.5, fontWeight: FontWeight.w700)),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 4),
            ListTile(
              leading: const Icon(Icons.check_circle_outline,
                  color: AppTheme.tealDark),
              title: const Text('完成打卡'),
              subtitle: Text('完成后顺延 ${t.cycleDays} 天并写入养护日志'),
              onTap: () {
                Navigator.pop(ctx);
                _complete(t);
              },
            ),
            ListTile(
              leading: const Icon(Icons.history),
              title: const Text('查看完成历史'),
              onTap: () {
                Navigator.pop(ctx);
                _showHistory(t);
              },
            ),
            ListTile(
              leading: const Icon(Icons.edit_outlined),
              title: const Text('编辑 / 删除任务'),
              onTap: () {
                Navigator.pop(ctx);
                _taskMenu(t);
              },
            ),
            const SizedBox(height: 8),
          ],
        ),
      ),
    );
  }

  static String _p2(int v) => v.toString().padLeft(2, '0');

  /// "HH:mm" → 今天该时刻
  DateTime _at(String hhmm) {
    final p = hhmm.split(':');
    final now = DateTime.now();
    return DateTime(now.year, now.month, now.day, int.tryParse(p[0]) ?? 0,
        int.tryParse(p.length > 1 ? p[1] : '') ?? 0);
  }

  int _daysTo(TaskEntity t) {
    final now = DateTime.now();
    final due = DateTime(t.nextDue.year, t.nextDue.month, t.nextDue.day);
    final today = DateTime(now.year, now.month, now.day);
    return due.difference(today).inDays;
  }

  // ───────────── 完成统计（与日志联动） ─────────────

  Future<void> _loadDone(String tankId) async {
    final list = await AppStore.instance.st.journals(tankId);
    final map = <String, List<JournalEntry>>{};
    for (final e in list) {
      // 完成打卡的日志 id 形如 task_<taskId>_<时间戳>
      final m = RegExp(r'^task_([^_]+)_').firstMatch(e.id);
      if (m == null) continue;
      (map[m.group(1)!] ??= []).add(e);
    }
    if (!mounted) return;
    setState(() {
      _loadedTank = tankId;
      _doneBy = map;
    });
  }

  // ───────────── 页面 ─────────────

  @override
  Widget build(BuildContext context) {
    final store = AppStore.instance;
    return AnimatedBuilder(
      animation: store,
      builder: (context, _) {
        // 必须在 builder 内读取：IndexedStack 常驻页面首帧时缸列表尚未加载，
        // 若在 build 外捕获 null 会导致按钮永远禁用（此前"按键无响应"根因）
        final tank = store.activeTank;
        if (tank != null && tank.id != _loadedTank) {
          WidgetsBinding.instance
              .addPostFrameCallback((_) => _loadDone(tank.id));
        }
        // 云同步合并改写本地数据后：重载完成统计（列表 FutureBuilder 随通知自动重取）
        if (store.dataVer != _loadedVer) {
          _loadedVer = store.dataVer;
          if (tank != null) {
            WidgetsBinding.instance
                .addPostFrameCallback((_) => _loadDone(tank.id));
          }
        }
        // 提醒横幅「去处理」跳转而来：弹出对应任务的处理面板
        if (store.pendingTaskId != null) {
          WidgetsBinding.instance
              .addPostFrameCallback((_) => _openPendingTask());
        }
        return Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            // 顶部栏：标题 + 右上角"新增任务"（IndexedStack 常驻页面必须自带）
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 12, 8, 4),
              child: Row(
                children: [
                  const Text('养护计划',
                      style: TextStyle(
                          fontSize: 16.5,
                          fontWeight: FontWeight.w800,
                          color: Colors.black87)),
                  const Spacer(),
                  TextButton.icon(
                    onPressed: tank == null
                        ? null
                        : () => _taskDialog(context, tank.id),
                    icon: const Icon(Icons.add, size: 18),
                    label: const Text('新增任务'),
                    style: TextButton.styleFrom(
                        foregroundColor: AppTheme.tealDark),
                  ),
                ],
              ),
            ),
            Expanded(
              child: tank == null
                  ? const Center(
                      child: Text('暂无鱼缸，请先在设置页添加',
                          style:
                              TextStyle(fontSize: 13, color: AppTheme.muted)))
                  : FutureBuilder<List<TaskEntity>>(
                      future: store.st.tasks(tank.id),
                      builder: (context, snap) {
                        final tasks = snap.data ?? const <TaskEntity>[];
                        if (tasks.isEmpty) {
                          return Center(
                              child: Column(
                            mainAxisSize: MainAxisSize.min,
                            children: [
                              Icon(Icons.event_note_outlined,
                                  size: 44,
                                  color: AppTheme.muted.withOpacity(.6)),
                              const SizedBox(height: 10),
                              const Text('暂无周期任务',
                                  style: TextStyle(
                                      fontSize: 13.5, color: AppTheme.muted)),
                              const SizedBox(height: 4),
                              const Text('点右上角「新增任务」创建换水/喂食/保养计划',
                                  style: TextStyle(
                                      fontSize: 11.5, color: AppTheme.muted)),
                            ],
                          ));
                        }
                        // 分组：逾期 / 今天 / 3 天内 / 稍后（4 天起全部显示）
                        final overdue = <TaskEntity>[];
                        final today = <TaskEntity>[];
                        final soon = <TaskEntity>[];
                        final later = <TaskEntity>[];
                        for (final t in tasks) {
                          final d = _daysTo(t);
                          if (d < 0) {
                            overdue.add(t);
                          } else if (d == 0) {
                            today.add(t);
                          } else if (d <= 3) {
                            soon.add(t);
                          } else {
                            later.add(t);
                          }
                        }
                        return ListView(
                          padding: const EdgeInsets.fromLTRB(16, 4, 16, 24),
                          children: [
                            _group('已逾期', Icons.warning_amber_rounded,
                                AppTheme.danger, overdue),
                            _group('今天', Icons.today_outlined, AppTheme.teal,
                                today),
                            _group('即将到期（3 天内）', Icons.schedule,
                                AppTheme.tealDark, soon),
                            _group('稍后', Icons.event_outlined, AppTheme.muted,
                                later),
                          ],
                        );
                      },
                    ),
            ),
          ],
        );
      },
    );
  }

  Widget _group(
      String title, IconData icon, Color color, List<TaskEntity> list) {
    if (list.isEmpty) return const SizedBox.shrink();
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(2, 12, 0, 6),
          child: Row(
            children: [
              Icon(icon, size: 15, color: color),
              const SizedBox(width: 5),
              Text('$title（${list.length}）',
                  style: TextStyle(
                      fontSize: 12.5,
                      fontWeight: FontWeight.w700,
                      color: color)),
            ],
          ),
        ),
        ...list.map((t) => _row(t, color)),
      ],
    );
  }

  Widget _row(TaskEntity t, Color color) {
    final done = _doneBy[t.id] ?? const <JournalEntry>[];
    final due = t.nextDue;
    final dueText =
        '${due.month}/${due.day}${t.time == null ? '' : ' ${t.time}'}';
    return GestureDetector(
      onTap: () => _showHistory(t),
      onLongPress: () => _taskMenu(t),
      child: Container(
        margin: const EdgeInsets.only(bottom: 8),
        padding: const EdgeInsets.fromLTRB(12, 10, 8, 10),
        decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.circular(12),
          border: Border.all(color: const Color(0xFFe2e8f0)),
          boxShadow: [
            BoxShadow(
                color: Colors.black.withOpacity(.04),
                blurRadius: 4,
                offset: const Offset(0, 1)),
          ],
        ),
        child: Row(
          children: [
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(t.title,
                      style: const TextStyle(
                          fontSize: 14, fontWeight: FontWeight.w700)),
                  const SizedBox(height: 3),
                  Text('每 ${t.cycleDays} 天 · 下次 $dueText',
                      style: const TextStyle(
                          fontSize: 11.5, color: AppTheme.muted)),
                  if (done.isNotEmpty) ...[
                    const SizedBox(height: 3),
                    Text(
                      '已完成 ${done.length} 次 · 最近 ${done.first.ts.month}/${done.first.ts.day}',
                      style: const TextStyle(
                          fontSize: 11, color: AppTheme.tealDark),
                    ),
                  ],
                ],
              ),
            ),
            TextButton(
              onPressed: () => _complete(t),
              style: TextButton.styleFrom(
                  foregroundColor: AppTheme.tealDark,
                  padding: const EdgeInsets.symmetric(horizontal: 10)),
              child: const Text('完成 ✓',
                  style:
                      TextStyle(fontSize: 12.5, fontWeight: FontWeight.w700)),
            ),
          ],
        ),
      ),
    );
  }

  /// 点击行：查看该任务的完成历史（与日志页数据同源）
  void _showHistory(TaskEntity t) {
    final list = _doneBy[t.id] ?? const <JournalEntry>[];
    showModalBottomSheet<void>(
      context: context,
      backgroundColor: Colors.white,
      shape: const RoundedRectangleBorder(
          borderRadius: BorderRadius.vertical(top: Radius.circular(16))),
      builder: (ctx) => SafeArea(
        child: SizedBox(
          height: 380,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Padding(
                padding: const EdgeInsets.fromLTRB(16, 14, 16, 8),
                child: Text('「${t.title}」完成历史（${list.length} 次）',
                    style: const TextStyle(
                        fontSize: 14.5, fontWeight: FontWeight.w700)),
              ),
              const Divider(height: 1),
              Expanded(
                child: list.isEmpty
                    ? const Center(
                        child: Text('暂无完成记录，点任务行的「完成 ✓」打卡后自动写入日志',
                            style: TextStyle(
                                fontSize: 12.5, color: AppTheme.muted)))
                    : ListView.builder(
                        padding: const EdgeInsets.symmetric(
                            horizontal: 16, vertical: 8),
                        itemCount: list.length,
                        itemBuilder: (_, i) {
                          final e = list[i];
                          return Padding(
                            padding: const EdgeInsets.symmetric(vertical: 5),
                            child: Row(
                              children: [
                                const Icon(Icons.check_circle_outline,
                                    size: 15, color: AppTheme.teal),
                                const SizedBox(width: 8),
                                Text(
                                    '${e.ts.year}/${e.ts.month}/${e.ts.day} ${_p2(e.ts.hour)}:${_p2(e.ts.minute)}',
                                    style: const TextStyle(
                                        fontSize: 12.5,
                                        fontWeight: FontWeight.w600)),
                                const SizedBox(width: 10),
                                Expanded(
                                  child: Text(
                                    e.note.isEmpty ? '已完成' : e.note,
                                    style: const TextStyle(
                                        fontSize: 11.5, color: AppTheme.muted),
                                    overflow: TextOverflow.ellipsis,
                                  ),
                                ),
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

  /// 长按行：编辑 / 删除
  void _taskMenu(TaskEntity t) {
    final tankId = AppStore.instance.activeTank?.id;
    if (tankId == null) return;
    showModalBottomSheet<void>(
      context: context,
      backgroundColor: Colors.white,
      shape: const RoundedRectangleBorder(
          borderRadius: BorderRadius.vertical(top: Radius.circular(16))),
      builder: (ctx) => SafeArea(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            ListTile(
              leading: const Icon(Icons.edit_outlined),
              title: const Text('编辑任务'),
              onTap: () {
                Navigator.pop(ctx);
                _taskDialog(context, tankId, existing: t);
              },
            ),
            ListTile(
              leading: const Icon(Icons.delete_outline, color: Colors.red),
              title: const Text('删除任务', style: TextStyle(color: Colors.red)),
              onTap: () async {
                Navigator.pop(ctx);
                final ok = await showDialog<bool>(
                  context: context,
                  builder: (c) => AlertDialog(
                    title: const Text('删除任务'),
                    content: Text('确定删除「${t.title}」？已完成的历史记录仍保留在日志中。'),
                    actions: [
                      TextButton(
                          onPressed: () => Navigator.pop(c, false),
                          child: const Text('取消')),
                      FilledButton(
                          style: FilledButton.styleFrom(
                              backgroundColor: Colors.red),
                          onPressed: () => Navigator.pop(c, true),
                          child: const Text('删除')),
                    ],
                  ),
                );
                if (ok != true) return;
                await _removeTask(tankId, t.id);
                if (mounted) setState(() {});
              },
            ),
          ],
        ),
      ),
    );
  }

  Future<void> _removeTask(String tankId, String id) async {
    // tasks(tankId) 只返回本缸未暂停任务；删除需在全量数据上操作，
    // 这里按"读全量 → 过滤 → 写回"实现（storage 层为覆盖式保存）
    final store = AppStore.instance;
    final raw = await store.st.getString('tasks_json');
    if (raw == null || raw.isEmpty) return;
    try {
      final list = (jsonDecode(raw) as List).cast<Map<String, dynamic>>();
      list.removeWhere((m) => m['id'] == id);
      final remains = list.map(TaskEntity.fromJson).toList();
      await store.st.saveTasks(remains);
    } catch (_) {}
  }

  /// 一键完成：写入养护日志（维护类型，id 前缀 task_ 供历史统计）并顺延周期
  Future<void> _complete(TaskEntity t) async {
    final store = AppStore.instance;
    final now = DateTime.now();
    await store.st.addJournal(JournalEntry(
      id: 'task_${t.id}_${now.millisecondsSinceEpoch}',
      tankId: t.tankId,
      type: JournalEntry.typeMaintain,
      note: '完成任务「${t.title}」',
      ts: now,
    ));
    final next = t.nextDue.add(Duration(days: t.cycleDays));
    await _saveWithCopy(t, next);
    final tankId = t.tankId;
    await _loadDone(tankId);
    if (mounted) {
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(
        behavior: SnackBarBehavior.floating,
        duration: const Duration(seconds: 2),
        content: Text('已完成「${t.title}」，下次 ${next.month}/${next.day}'
            '${t.time == null ? '' : ' ${t.time}'}'),
      ));
    }
  }

  Future<void> _saveWithCopy(TaskEntity t, DateTime nextDue) async {
    final store = AppStore.instance;
    final all = await store.st.tasks(t.tankId);
    final idx = all.indexWhere((x) => x.id == t.id);
    if (idx < 0) return;
    final updated = TaskEntity(
      id: t.id,
      tankId: t.tankId,
      title: t.title,
      cycleDays: t.cycleDays,
      nextDue: nextDue,
      time: t.time,
      paused: t.paused,
      upd: DateTime.now().millisecondsSinceEpoch, // 云同步冲突合并用
    );
    all[idx] = updated;
    await store.st.saveTasks(all);
  }

  // ───────────── 新建 / 编辑对话框 ─────────────

  Future<void> _taskDialog(BuildContext context, String tankId,
      {TaskEntity? existing}) async {
    final titleCtrl = TextEditingController(text: existing?.title ?? '');
    int cycle = existing?.cycleDays ?? 7;
    TimeOfDay? time;
    if (existing?.time != null) {
      final p = existing!.time!.split(':');
      time = TimeOfDay(
          hour: int.tryParse(p[0]) ?? 9, minute: int.tryParse(p[1]) ?? 0);
    }
    final messenger = ScaffoldMessenger.of(context);
    final ok = await showDialog<bool>(
      context: context,
      builder: (ctx) => StatefulBuilder(
        builder: (ctx, setD) => AlertDialog(
          title: Text(existing == null ? '新增任务' : '编辑任务'),
          content: SizedBox(
            width: 320,
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                TextField(
                  controller: titleCtrl,
                  autofocus: existing == null,
                  decoration: const InputDecoration(
                    labelText: '任务名称 *',
                    hintText: '如：换水 / 滤材清洗 / 玻璃清洁',
                    border: OutlineInputBorder(),
                    isDense: true,
                  ),
                ),
                const SizedBox(height: 14),
                // 周期（天）：1~30 天
                Row(
                  children: [
                    const Text('周期', style: TextStyle(fontSize: 13)),
                    Expanded(
                      child: Slider(
                        value: cycle.toDouble(),
                        min: 1,
                        max: 30,
                        divisions: 29,
                        label: '$cycle 天',
                        onChanged: (v) => setD(() => cycle = v.round()),
                      ),
                    ),
                    Text('$cycle 天',
                        style: const TextStyle(
                            fontSize: 13, fontWeight: FontWeight.w700)),
                  ],
                ),
                const SizedBox(height: 4),
                // 每日时刻（可选）：指定后到点横幅提醒
                Row(
                  children: [
                    const Text('提醒时刻', style: TextStyle(fontSize: 13)),
                    const Spacer(),
                    Switch(
                      value: time != null,
                      onChanged: (v) => setD(() => time =
                          v ? const TimeOfDay(hour: 9, minute: 0) : null),
                    ),
                    InkWell(
                      onTap: time == null
                          ? null
                          : () async {
                              final t = await showTimePicker(
                                  context: ctx, initialTime: time!);
                              if (t != null) setD(() => time = t);
                            },
                      child: Container(
                        padding: const EdgeInsets.symmetric(
                            horizontal: 10, vertical: 6),
                        decoration: BoxDecoration(
                          color: time == null
                              ? Colors.grey.withOpacity(.12)
                              : AppTheme.teal.withOpacity(.12),
                          borderRadius: BorderRadius.circular(8),
                        ),
                        child: Text(
                          time == null
                              ? '全天（不限时刻）'
                              : '${_p2(time!.hour)}:${_p2(time!.minute)}',
                          style: TextStyle(
                              fontSize: 12.5,
                              fontWeight: FontWeight.w700,
                              color: time == null
                                  ? AppTheme.muted
                                  : AppTheme.tealDark),
                        ),
                      ),
                    ),
                  ],
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
                child: Text(existing == null ? '添加' : '保存')),
          ],
        ),
      ),
    );
    if (ok != true) return;
    final title = titleCtrl.text.trim();
    if (title.isEmpty) {
      messenger.showSnackBar(const SnackBar(
          content: Text('任务名称不能为空'), behavior: SnackBarBehavior.floating));
      return;
    }
    final store = AppStore.instance;
    final all = await store.st.tasks(tankId);
    final ex = existing; // 闭包内使用的局部引用（避免非空断言链）
    if (ex == null) {
      // 新建：首个到期日 = 指定时刻且今天未过 → 今天；否则从下一周期起算
      final now = DateTime.now();
      DateTime next;
      if (time != null) {
        final todayAt =
            DateTime(now.year, now.month, now.day, time!.hour, time!.minute);
        next = now.isBefore(todayAt)
            ? todayAt
            : todayAt.add(Duration(days: cycle));
      } else {
        next = now.add(Duration(days: cycle));
      }
      all.add(TaskEntity(
        id: 'task_${now.millisecondsSinceEpoch}',
        tankId: tankId,
        title: title,
        cycleDays: cycle,
        nextDue: next,
        time: time == null ? null : '${_p2(time!.hour)}:${_p2(time!.minute)}',
        upd: now.millisecondsSinceEpoch, // 云同步冲突合并用
      ));
      all.sort((a, b) => a.nextDue.compareTo(b.nextDue));
    } else {
      final idx = all.indexWhere((x) => x.id == ex.id);
      if (idx >= 0) {
        all[idx] = TaskEntity(
          id: ex.id,
          tankId: ex.tankId,
          title: title,
          cycleDays: cycle,
          nextDue: ex.nextDue,
          time: time == null ? null : '${_p2(time!.hour)}:${_p2(time!.minute)}',
          paused: ex.paused,
          upd: DateTime.now().millisecondsSinceEpoch, // 云同步冲突合并用
        );
      }
    }
    await store.st.saveTasks(all);
    final tank = store.activeTank;
    if (tank != null && tank.id == tankId) await _loadDone(tankId);
    if (mounted) setState(() {});
    if (existing == null) {
      messenger.showSnackBar(const SnackBar(
          content: Text('任务已添加'),
          behavior: SnackBarBehavior.floating,
          duration: Duration(seconds: 2)));
    }
  }
}
