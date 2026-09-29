/// 主框架：顶部缸切换器（全局）+ 底部 4 Tab + AI 对话入口。
library;

import 'package:flutter/material.dart';

import '../app.dart';
import '../core/theme.dart';
import '../models/tank.dart';
import 'ai_chat_page.dart';
import 'journal_page.dart';
import 'overview_page.dart';
import 'plan_page.dart';
import 'settings_page.dart';
import 'tank_page.dart';

class HomePage extends StatefulWidget {
  const HomePage({super.key});

  @override
  State<HomePage> createState() => _HomePageState();
}

class _HomePageState extends State<HomePage> {
  int _tab = 0;

  @override
  Widget build(BuildContext context) {
    final store = AppStore.instance;
    return AnimatedBuilder(
      animation: store,
      builder: (context, _) {
        return Scaffold(
          appBar: AppBar(
            title: _TankSwitcher(store: store),
            actions: [
              // AI 智能分析入口
              IconButton(
                icon: const Icon(Icons.auto_awesome, color: AppTheme.tealDark),
                tooltip: 'AI 智能分析',
                onPressed: () => Navigator.of(context).push(
                  MaterialPageRoute(builder: (_) => const AiChatPage()),
                ),
              ),
              // 设置（AI 服务配置 / 设备连接说明）
              IconButton(
                icon: const Icon(Icons.settings_outlined, color: AppTheme.muted),
                tooltip: '设置',
                onPressed: () => Navigator.of(context).push(
                  MaterialPageRoute(builder: (_) => const SettingsPage()),
                ),
              ),
            ],
          ),
          body: IndexedStack(
            index: _tab,
            children: const [
              OverviewPage(),
              JournalPage(),
              PlanPage(),
              TankPage(),
            ],
          ),
          bottomNavigationBar: NavigationBar(
            selectedIndex: _tab,
            onDestinationSelected: (i) => setState(() => _tab = i),
            destinations: const [
              NavigationDestination(icon: Icon(Icons.dashboard_outlined), selectedIcon: Icon(Icons.dashboard), label: '概览'),
              NavigationDestination(icon: Icon(Icons.menu_book_outlined), selectedIcon: Icon(Icons.menu_book), label: '日志'),
              NavigationDestination(icon: Icon(Icons.event_note_outlined), selectedIcon: Icon(Icons.event_note), label: '计划'),
              NavigationDestination(icon: Icon(Icons.opacity_outlined), selectedIcon: Icon(Icons.opacity), label: '鱼缸'),
            ],
          ),
        );
      },
    );
  }
}

/// 顶部缸切换器：下拉选择当前缸，全部页面数据随缸切换
class _TankSwitcher extends StatelessWidget {
  const _TankSwitcher({required this.store});

  final AppStore store;

  @override
  Widget build(BuildContext context) {
    final tank = store.activeTank;
    return PopupMenuButton<Tank>(
      initialValue: tank,
      onSelected: (t) => store.switchTank(t),
      itemBuilder: (ctx) => [
        ...store.tanks.map(
          (t) => PopupMenuItem(
            value: t,
            child: Text('${t.name}（${t.waterType}）'),
          ),
        ),
        const PopupMenuDivider(),
        const PopupMenuItem(
          enabled: false,
          height: 32,
          child: Text('添加鱼缸请进入「鱼缸」Tab', style: TextStyle(fontSize: 12, color: AppTheme.muted)),
        ),
      ],
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Text(
            tank?.name ?? '未添加鱼缸',
            style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w700),
          ),
          const Icon(Icons.expand_more, size: 20),
        ],
      ),
    );
  }
}
