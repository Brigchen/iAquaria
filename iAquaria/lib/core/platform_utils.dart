/// 平台判断工具类。
///
/// OpenHarmony 版 Flutter 运行在鸿蒙 Next 时 `Platform.operatingSystem == 'ohos'`，
/// 官方 `Platform.isAndroid` / `Platform.isIOS` 之外没有 `isOhos`，这里统一封装，
/// 业务代码一律通过本类做平台分支，禁止散落各处直接调用 `dart:io` 的 Platform。
library;

import 'dart:io' show Platform;

class PlatformUtils {
  PlatformUtils._();

  /// 是否运行在 Android
  static bool get isAndroid => Platform.isAndroid;

  /// 是否运行在 HarmonyOS Next（OpenHarmony Flutter 运行时的标识为 'ohos'）
  static bool get isOhos => Platform.operatingSystem == 'ohos';

  /// 当前平台名（日志与设置页展示用）
  static String get name => isOhos ? 'HarmonyOS Next' : Platform.operatingSystem;

  /// 平台差异的统一入口：
  /// - Android：动态权限走 permission_handler 前往系统设置页
  /// - HarmonyOS：权限在 module.json5 声明 + 首次使用时由系统弹窗授权，
  ///   受限权限（如写图库）需通过 ACL 声明，见 README「权限配置」
  static String get permissionDocHint => isOhos
      ? '鸿蒙：权限在 entry/src/main/module.json5 的 requestPermissions 中声明'
      : '安卓：权限在 android/app/src/main/AndroidManifest.xml 中声明';
}
