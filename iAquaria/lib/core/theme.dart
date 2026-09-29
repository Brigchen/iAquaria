/// 主题：延续 Web 端水系青绿主色（#2dd4bf），白底圆角卡片风格。
library;

import 'package:flutter/material.dart';

class AppTheme {
  AppTheme._();

  static const Color teal = Color(0xFF2dd4bf);
  static const Color tealDark = Color(0xFF0f766e);
  static const Color tealLight = Color(0xFFccfbf1);
  static const Color bg = Color(0xFFF4F7F7);
  static const Color muted = Color(0xFF64748b);
  static const Color danger = Color(0xFFef4444);

  static ThemeData light() {
    final base = ThemeData.light(useMaterial3: true);
    return base.copyWith(
      scaffoldBackgroundColor: bg,
      colorScheme: base.colorScheme.copyWith(
        primary: teal,
        secondary: tealDark,
        surface: Colors.white,
        error: danger,
        outline: const Color(0xFFe2e8f0),
      ),
      appBarTheme: const AppBarTheme(
        backgroundColor: bg,
        surfaceTintColor: Colors.transparent,
        elevation: 0,
        centerTitle: false,
        titleTextStyle: TextStyle(
          color: Colors.black87,
          fontSize: 18,
          fontWeight: FontWeight.w700,
        ),
      ),
      cardTheme: CardTheme(
        color: Colors.white,
        elevation: 0,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
      ),
      navigationBarTheme: NavigationBarThemeData(
        backgroundColor: Colors.white,
        indicatorColor: tealLight,
        labelTextStyle: WidgetStateProperty.all(
          const TextStyle(fontSize: 11.5, color: Colors.black87),
        ),
      ),
    );
  }
}
