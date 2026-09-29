import 'package:flutter/material.dart';

import 'app.dart';
import 'core/theme.dart';
import 'pages/home_page.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  // 全局状态初始化（缸档案 + 设备 WebSocket 直连）
  AppStore.instance.init();
  runApp(const IaquaApp());
}

class IaquaApp extends StatelessWidget {
  const IaquaApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'iAquaria',
      debugShowCheckedModeBanner: false,
      theme: AppTheme.light(),
      home: const HomePage(),
    );
  }
}
