/// App 版本信息（三端共用）。
///
/// kAppBuild 为发给测试的构建序号：每次修复后重新打包递增，
/// 测试人可在「概览」页状态条右侧与「设置-关于」处核对手机上实际运行的版本，
/// 避免覆盖安装后旧进程 / 旧包导致的误判。
library;

const String kAppVersion = '0.1.0';
const String kAppBuild = '21';

/// 页面展示用，如 v0.1.0-b3
const String kAppVerLabel = 'v$kAppVersion-b$kAppBuild';
