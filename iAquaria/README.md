# iAquaria — 水族缸智能管理 App（Flutter 双平台版）

**单位**：集美大学（Coralab）
**平台**：Android + HarmonyOS Next（鸿蒙）
**技术栈**：Flutter（OpenHarmony SIG 版 `flutter_flutter` master = 3.7.12-ohos-1.0.4，Dart 2.19）· 纯 Dart 依赖（dio / mqtt_client / fl_chart / shared_preferences）

同一套 Dart 代码同时构建 Android APK 与鸿蒙 HAP。所有第三方包均为**纯 Dart 实现**（无原生 FFI 插件），鸿蒙侧无需额外原生适配。

**应用标识（华为 AppGallery Connect 已申请）**：
- App ID：`6917616455116550998`
- 包名（applicationId / bundleName）：`com.iaquaria.smartaquarium`
- 应用名：`iAquaria`

**LLM 客户端说明**：鸿蒙版 Flutter 基于 Dart 2.19，`openai_dart`（需 Dart 3+）无法使用；已在 `lib/services/llm_service.dart` 内自实现 OpenAI Chat Completions 协议客户端（SSE 流式解析 + 多模态 data URI 识图），调用协议与 `openai_dart` 完全一致，兼容 DeepSeek / 通义千问，可无缝切换。

---

## 1. 功能总览

| 模块 | 说明 |
|---|---|
| 多缸管理 | 顶部切换器一键换缸，缸档案含名称/位置/容量/**水型**/MQTT 主题/摄像头地址 |
| 水型驱动显示 | 淡水/草缸显示 TDS(滤前)/TDS(滤后)（ppm）；**海水缸只显示单个"盐度"**（协议键 tds1，单位 ‰） |
| 实时概览 | 7 项指标卡片（水温/pH/ORP/TDS或盐度/水位/光照），离线置灰 |
| 养护日志 | 时间线 + 类型筛选（水质/换水/喂食/维护/其他），告警事件自动写入（带"自动"徽标） |
| 周期计划 | 今天/即将到期/已逾期分组，一键完成 → 自动写日志 + 周期顺延 |
| 阈值告警 | 区间 / 基线±百分比 两种模式，持续 N 次去抖、冷却时间、免打扰时段（跨天支持），全部本地自定义 |
| **AI 智能分析** | 兼容 OpenAI 协议 LLM（DeepSeek/通义千问），**流式打字输出**；**ESP32-CAM 抓拍多模态识图**：鱼虾识别计数、藻/草状态、爆藻风险评估、养护建议；自动注入实时水质读数 |
| 摄像头 | 抓拍走 HTTP `GET /capture`（纯 Dart，不用 image_picker/相机权限） |

## 2. 项目结构

```
lib/
├── main.dart                  # 入口
├── app.dart                   # 全局状态 AppStore（缸列表/活动缸/遥测/告警）
├── core/
│   ├── constants…theme.dart   # 主题（青绿水系 #2dd4bf）
│   ├── metrics.dart           # 水型驱动的指标名称/单位映射（与 Kotlin 版对齐）
│   └── platform_utils.dart    # Platform.isAndroid / isOhos 统一封装
├── models/                    # tank.dart / telemetry.dart / records.dart(日志·任务·规则)
├── services/                  # ← 独立 service 层
│   ├── mqtt_service.dart      # MQTT 收发（订阅 {topic}/tel，发布 {topic}/cmd）
│   ├── llm_service.dart       # openai_dart 封装：流式 + 多模态 + 系统提示词
│   ├── camera_service.dart    # ESP32-CAM /capture 抓拍
│   ├── alert_engine.dart      # 阈值告警本地评估引擎
│   └── storage_service.dart   # 本地持久化（含 API Key 安全存储）
└── pages/                     # ← 页面层
    ├── home_page.dart         # 底部 4 Tab + 缸切换器
    ├── overview_page.dart / journal_page.dart / plan_page.dart / tank_page.dart
    ├── ai_chat_page.dart      # AI 对话（流式 + 抓拍识图）
    └── settings_page.dart     # LLM/MQTT 配置
```

## 3. 环境部署步骤

### 3.1 通用（Windows 实测路径）

1. **JDK 17**：`C:\Users\brigc\Tools\jdk-17.0.2`（已装）
2. **Android SDK**：`C:\Users\brigc\AppData\Local\Android\Sdk`（已装，platform 35 + build-tools 34.0.0 + platform-tools，许可已接受）
3. **Flutter（鸿蒙版）**：`C:\Users\brigc\Tools\flutter`（已装，分支 `3.22.1-ohos-0.1.0`）

```powershell
# 已固化的用户环境变量
FLUTTER_STORAGE_BASE_URL = https://storage.flutter-io.cn   # Flutter 产物镜像
PUB_HOSTED_URL           = https://pub.flutter-io.cn       # pub 包镜像
PATH += C:\Users\brigc\Tools\flutter\bin ; C:\Users\brigc\Tools\MinGit\cmd
```

```powershell
flutter doctor          # Android toolchain 应为 [√]
flutter devices         # 真机插 USB 打开 USB 调试后可见
```

### 3.2 拉依赖与运行

```powershell
cd iAquaria
flutter pub get
flutter run                     # 运行到已连接真机
flutter build apk --release     # 安卓正式包（output: build/app/outputs/flutter-apk/）
```

## 4. MQTT 配置（设置 → MQTT Broker）

在 App「设置」页填写（均保存在本机，**禁止硬编码**）：

| 项 | 说明 | 示例 |
|---|---|---|
| Broker 地址 | 内网 broker IP 或域名 | `192.168.3.10` |
| 端口 | TCP 端口 | `1883` |
| 用户名/密码 | broker 鉴权（可空） | — |

**主题约定**（与设备端约定一致）：

```
iaquaria/{tankId}/tel     设备 → App，JSON 遥测（字段同 WS tel 帧：temp/ph/orp/tds1/tds2/lux/lvl/…）
iaquaria/{tankId}/cmd     App → 设备，JSON 命令（如 {"cmd":"set","k":"lux_on","v":200}）
```

缸档案中的 MQTT 主题填前缀（如 `iaquaria/tank_livingroom`），留空则默认 `iaquaria/{tankId}`。
本地快速搭 broker 测试：Windows 可用 [mosquitto]（`mosquitto -v`），或 Docker：`docker run -p 1883:1883 eclipse-mosquitto`。

## 5. LLM 接口密钥配置（设置 → AI 服务）

| 项 | DeepSeek | 通义千问（多模态必选） |
|---|---|---|
| Base URL | `https://api.deepseek.com/v1` | `https://dashscope.aliyuncs.com/compatible-mode/v1` |
| 模型 | `deepseek-chat` | `qwen-vl-max`（视觉）/ `qwen-vl-plus` |
| API Key | [DeepSeek 开放平台](https://platform.deepseek.com/) 申请 | [阿里云百炼](https://bailian.console.aliyun.com/) 申请 |

> ⚠️ **密钥安全（重要）**
> 1. API Key **禁止硬编码**进源码、pubspec、README 或任何版本库；
> 2. Key 仅在 App「设置」页录入，经 `StorageService` 保存在本机（shared_preferences）；
> 3. **生产环境建议自建后端中转**（App → 后端 → LLM），App 只持短期 token，防止密钥随安装包泄露，并便于限流/审计。

**多模态注意**：识图功能要求所选模型支持视觉输入。DeepSeek 的 chat 模型**不支持**图片，请切到通义 `qwen-vl-max` 等视觉模型后再使用抓拍识图。

## 6. 权限配置对照表（自动区分平台）

业务代码不直接申请权限；平台差异由以下两处声明承担，均带注释：

### Android：`android/app/src/main/AndroidManifest.xml`

| 权限 | 用途 | 授予方式 |
|---|---|---|
| `INTERNET` | MQTT / LLM / 摄像头抓拍 | 安装即授予（普通权限） |
| `ACCESS_NETWORK_STATE` | 网络可达性提示 | 安装即授予 |
| `POST_NOTIFICATIONS` | 告警系统通知 | Android 13+ 运行时弹窗 |

> 抓拍走 HTTP 拉流，不用手机相机 → 无需 `CAMERA`；无相册扫描 → 无需存储权限。

### HarmonyOS Next：`ohos/entry/src/main/module.json5`（创建 ohos 平台后生效）

```jsonc
"requestPermissions": [
  // 网络访问（系统默认授予的 normal 权限）
  { "name": "ohos.permission.INTERNET" },
  // 网络状态（normal）
  { "name": "ohos.permission.GET_NETWORK_INFO" },
  // 通知（如需告警系统通知；system_basic，正常申请即可）
  { "name": "ohos.permission.NOTIFICATION_CONTROLLER" }
]
```

> 鸿蒙侧同样无需相机/存储权限（识图为 HTTP 拉帧）。
> 若后续加入"保存图片到相册"等能力，需申请 `ohos.permission.WRITE_IMAGEVIDEO`（受限开放权限，需在 `acls` 中声明并说明用途，上架审核严格）。

## 7. 双平台打包前置条件

### Android（本机已就绪）
- JDK 17 + Android SDK（platform 35 / build-tools 34.0.0）+ 接受全部 license
- `flutter build apk --release`

### HarmonyOS Next（本机已安装 DevEco Studio 26.0.0.821）
1. DevEco Studio 26 已静默安装于 `C:\Program Files\Huawei\DevEco Studio`（HarmonyOS NEXT SDK 合一打包在 `sdk` 子目录）；
2. 已固化的用户环境变量（flutter build hap 依赖）：

   ```powershell
   DEVECO_SDK_HOME = C:\Program Files\Huawei\DevEco Studio\sdk
   PATH 追加 = C:\Program Files\Huawei\DevEco Studio\tools\ohpm\bin
              ; C:\Program Files\Huawei\DevEco Studio\tools\hvigor\bin
              ; C:\Program Files\Huawei\DevEco Studio\tools\node
   ```
3. ohos/ 平台目录已生成（`flutter config --enable-ohos` 已开启，重建命令供参考）：

   ```powershell
   flutter create --platforms ohos --org com.iaquaria --project-name iaquaria .
   ```
4. 包名已在 `ohos/AppScope/app.json5` 中配置为 `com.iaquaria.smartaquarium`，权限见 `ohos/entry/src/main/module.json5`；
5. **先配置签名（debug/release 都必需，否则 build hap 在 Hvigor 编译通过后仍会失败）**：
   用 DevEco Studio 打开本项目的 `ohos/` 子目录 → File > Project Structure > Signing Configs →
   勾选 **Automatically generate signature** 并登录华为账号（AGC 对应 App ID `6917616455116550998` 的账号）。
   该步骤会生成本机调试证书/profile 并自动填入 `ohos/build-profile.json5` 的 signingConfigs（一次性操作）。
6. 构建（新开终端使环境变量生效后）：

   ```powershell
   flutter build hap --release    # 鸿蒙应用包（output: build/app/outputs/）
   ```

   注：若终端是旧会话（启动早于环境变量固化），需手动注入 `$env:DEVECO_SDK_HOME = "C:\Program Files\Huawei\DevEco Studio\sdk"`。
7. 上架时在 AGC 上传证书/profile 并关联 App ID `6917616455116550998`。

## 8. 测试说明（支持真机调试）

```powershell
flutter analyze                    # 静态检查（当前 0 issues）
flutter test                       # 冒烟测试（test/widget_test.dart）
flutter devices                    # 列出真机
flutter run -d <device-id>         # 真机热重载调试（USB 调试已开启）
```

**真机功能验证清单**：
1. 添加缸 → 选"海水"→ 确认提示为盐度探头、概览页只显示单个"盐度（‰）"卡片；
2. 设置页填 MQTT broker → 概览页状态条变"已连接"、指标随设备 tel 帧跳动；
3. 设置页填 LLM（先 deepseek-chat）→ AI 页发文字 → 流式打字回答；
4. 切 `qwen-vl-max` → AI 页点相机抓拍 → 发送 → 返回鱼虾计数/爆藻风险评估；
5. 阈值规则：把水温下限改到高于当前读数 → 数帧后概览页出现告警横幅 + 日志自动新增"自动告警"。

**无设备时的模拟**：任意 MQTT 客户端（如 `mosquitto_pub`）向 `iaquaria/{tankId}/tel` 发布 JSON：
`{"temp":26.5,"ph":7.0,"tds1":230,"tds2":180,"lux":120,"lvl":80}`
（海水缸场景该帧的 `tds1` 即显示为"盐度"）。

## 9. 已知约束

- OpenHarmony 版 Flutter master 基于 3.7.12（Dart 2.19.6）：`openai_dart`（需 Dart 3+）不可用，LLM 客户端已在 `llm_service.dart` 自实现（协议一致）；`dio` 锁 5.4.x、`fl_chart` 锁 0.55.x、`mqtt_client` 锁 10.3.x；后续 SIG 升级 SDK 分支后可放开；
- 鸿蒙侧 `shared_preferences` 需替换为 SIG 适配版（见下）；
- Web 端实时控制台与 PC 上位机仍走设备 WebSocket，不冲突。

**鸿蒙侧 shared_preferences 适配**（构建 HAP 前在 `pubspec.yaml` 追加）：

```yaml
dependency_overrides:
  shared_preferences_ohos:
    git:
      url: https://gitee.com/openharmony-sig/flutter_packages.git
      path: packages/shared_preferences/shared_preferences_ohos
```

---

iAquaria · 集美大学 · Coralab
