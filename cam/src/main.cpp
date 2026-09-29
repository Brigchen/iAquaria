// ============================================================
// iAqua 摄像头节点固件
// 板卡: ESP32 + OV3660/OV2640（引脚预置见 platformio.ini）
// 服务:
//   :80  /        状态 JSON
//   :80  /capture 单帧 JPEG（上位机 1fps 轮询用）
//   :81  /stream  MJPEG 流（浏览器/仪表盘 <img> 直接嵌入）
//   :80  /wifi    配网页（保存后重启）
//   :80  /cloud   云照片上传配置（EMQX MQTT over TLS，保存后重启）
//   :80  /cloudsnap  立即拍一张并上传云端（测试用）
// 云照片：每小时 1 张（可配）→ retained 发布 <topic>/img，
//         App 局域网外经 EMQX 订阅查看；多客户端并发已支持
// STA 连不上 15s → 自动开热点 iAqua-Cam（密码 12345678）
// ============================================================
#include <Arduino.h>
#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <PubSubClient.h>
#include <WebServer.h>
#include <ESPmDNS.h>
#include <Preferences.h>
#include <mbedtls/base64.h>
#include "esp_camera.h"
#include "FS.h"
#include "SD_MMC.h"
#include "CamCert.h"

// ---- 引脚预置 ----
#if defined(CAM_PRESET_ESP_EYE)
#define CAM_PIN_PWDN  -1
#define CAM_PIN_RESET -1
#define CAM_PIN_XCLK  4
#define CAM_PIN_SIOD  18
#define CAM_PIN_SIOC  23
#define CAM_PIN_Y9    36
#define CAM_PIN_Y8    37
#define CAM_PIN_Y7    38
#define CAM_PIN_Y6    39
#define CAM_PIN_Y5    35
#define CAM_PIN_Y4    14
#define CAM_PIN_Y3    13
#define CAM_PIN_Y2    5
#define CAM_PIN_VSYNC 25
#define CAM_PIN_HREF  27
#define CAM_PIN_PCLK  19
#else  // 默认: AI-Thinker 兼容排布（大多数国产 CAM 板）
#define CAM_PIN_PWDN  32
#define CAM_PIN_RESET -1
#define CAM_PIN_XCLK  0
#define CAM_PIN_SIOD  26
#define CAM_PIN_SIOC  27
#define CAM_PIN_Y9    35
#define CAM_PIN_Y8    34
#define CAM_PIN_Y7    39
#define CAM_PIN_Y6    36
#define CAM_PIN_Y5    21
#define CAM_PIN_Y4    19
#define CAM_PIN_Y3    18
#define CAM_PIN_Y2    5
#define CAM_PIN_VSYNC 25
#define CAM_PIN_HREF  23
#define CAM_PIN_PCLK  22
#endif

static const char* AP_SSID = "iAqua-Cam";
static const char* AP_PASS = "12345678";

static WebServer server(80);
static WiFiServer streamSrv(81);
static bool camOk = false;
static uint32_t bootMs = 0;

static String s_logBuf[50];
static int s_logIdx = 0;
static String s_logRing(int i) { return s_logBuf[(s_logIdx + i) % 50]; }

static void logLine(const char* tag, const String& msg) {
  String line = "[" + String(millis() / 1000) + "][" + tag + "] " + msg;
  Serial.println(line);
  s_logBuf[s_logIdx] = line;             // 环形日志缓冲（HTTP /log 诊断用）
  s_logIdx = (s_logIdx + 1) % 50;
}

// AI-Thinker ESP32-CAM 板载 TF：SD_MMC 1-bit（CLK=14 CMD=15 D0=2）
static void probeTfCard() {
  if (!SD_MMC.begin("/sdcard", true)) {
    logLine("SD", "TF 未识别（卡槽/插紧/FAT32；1-bit SD_MMC）");
    return;
  }
  uint8_t type = SD_MMC.cardType();
  if (type == CARD_NONE) {
    logLine("SD", "卡槽无卡");
    SD_MMC.end();
    return;
  }
  const char* kind = (type == CARD_MMC) ? "MMC" : (type == CARD_SD) ? "SDSC" : "SDHC";
  uint64_t mb = SD_MMC.cardSize() / (1024ULL * 1024ULL);
  uint64_t used = SD_MMC.usedBytes() / (1024ULL * 1024ULL);
  logLine("SD", String("TF 就绪 type=") + kind + " size=" + mb + "MB used=" + used + "MB");
  SD_MMC.end();  // 仅诊断，释放引脚给后续摄像头
}

// ---------------- 云照片上传（EMQX MQTT over TLS） ----------------
static WiFiClientSecure cloudTls;
static PubSubClient cloudMqtt(cloudTls);
static SemaphoreHandle_t cloudMux = nullptr;   // 保护 cloudMqtt（任务/HTTP 线程）
static volatile bool cloudSnapReq = false;     // /cloudsnap 立即上传
static uint32_t cloudNextTry = 0;              // 断线重连退避
static uint32_t cloudLastUp = 0;               // 上次成功上传 epoch 秒

struct CloudCfg {
  bool en;
  String host, user, pass, topic;
  int port;       // MQTT over TLS，默认 8883
  int hours;      // 上传间隔（小时），默认 1
} g_cloud;

static void cloudLoad() {
  Preferences p;
  p.begin("iacam", true);
  g_cloud.en    = p.getBool("cloud_en", false);
  g_cloud.host  = p.getString("cloud_host", "");
  g_cloud.user  = p.getString("cloud_user", "");
  g_cloud.pass  = p.getString("cloud_pass", "");
  g_cloud.topic = p.getString("cloud_topic", "");
  g_cloud.port  = p.getInt("cloud_port", 8883);
  g_cloud.hours = p.getInt("cloud_hours", 1);
  p.end();
}

static void cloudSaveAndReboot() {
  Preferences p;
  p.begin("iacam", false);
  p.putBool("cloud_en", g_cloud.en);
  p.putString("cloud_host", g_cloud.host);
  p.putString("cloud_user", g_cloud.user);
  p.putString("cloud_pass", g_cloud.pass);
  p.putString("cloud_topic", g_cloud.topic);
  p.putInt("cloud_port", g_cloud.port);
  p.putInt("cloud_hours", g_cloud.hours);
  p.end();
  server.send(200, "text/html",
              "<meta charset=utf-8>云配置已保存，3 秒后重启…<script>setTimeout(()=>location='/',3000)</script>");
  delay(500);
  ESP.restart();
}

static bool cloudConfigured() {
  return g_cloud.en && g_cloud.host.length() && g_cloud.topic.length();
}

// TLS 可靠写：mbedtls 单次 write 允许部分写（返回实际写入量，错误返回 -1），
// 必须循环写满并校验，否则 broker 收到残包会断链丢弃且不保留 retained
static bool tlsWriteAll(WiFiClientSecure& c, const uint8_t* p, size_t n) {
  size_t off = 0;
  int idle = 0;
  while (off < n) {
    int w = c.write(p + off, n - off);
    if (w < 0) return false;
    if (w == 0) {
      if (++idle > 1000) return false;  // 持续 0 写判定失败
      delay(2);
      continue;
    }
    idle = 0;
    off += (size_t)w;
  }
  return true;
}

// 拍一帧 → base64 → retained 发布 <topic>/img（在云任务内调用，允许阻塞）
static bool cloudUploadNow() {
  if (!camOk || !cloudMqtt.connected()) {
    logLine("CLD", "上传中止: camOk=" + String(camOk) + " mqtt=" + String(cloudMqtt.connected()));
    return false;
  }
  camera_fb_t* fb = esp_camera_fb_get();
  if (!fb) {
    logLine("CLD", "拍照失败（传感器占用/超时）");
    return false;
  }

  // JSON: {"ts":<epoch>,"fmt":"jpeg","b64":"..."} —— b64 编码进 PSRAM 大缓冲（DRAM 堆放不下）
  // 先定头长（随 ts 位数变化），b64 必须紧跟头部；此前 b64 固定放偏移 52，与
  // 实际头长（~37B）不等，中间夹 PSRAM 垃圾导致 JSON 恒坏、App 解析必败
  size_t b64Cap = ((fb->len + 2) / 3) * 4;
  char pre[56];
  int hdr = snprintf(pre, sizeof(pre), "{\"ts\":%lu,\"fmt\":\"jpeg\",\"b64\":\"",
                     time(nullptr) > 100000 ? (unsigned long)time(nullptr) : millis() / 1000);
  uint8_t* msg = (uint8_t*)heap_caps_malloc(hdr + b64Cap + 3, MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT);
  if (!msg) {
    esp_camera_fb_return(fb);
    logLine("CLD", "上传缓冲区分配失败 heap=" + String(ESP.getFreeHeap()) +
                        " psram=" + String(ESP.getFreePsram()));
    return false;
  }
  memcpy(msg, pre, hdr);
  size_t olen = 0;
  // dst 可用 = b64Cap+3（b64 占 b64Cap，mbedtls 要求 NUL 余量 +1）
  int rc = mbedtls_base64_encode(msg + hdr, b64Cap + 3, &olen, fb->buf, fb->len);
  esp_camera_fb_return(fb);
  if (rc != 0) {
    free(msg);
    logLine("CLD", "base64 编码失败 rc=" + String(rc));
    return false;
  }
  memcpy(msg + hdr + olen, "\"}", 3);
  size_t total = hdr + olen + 2;

  String topic = g_cloud.topic + "/img";
  // 自建 PUBLISH(QoS0, retained) 包并逐段写满：PubSubClient 的 beginPublish+
  // write 不校验 WiFiClientSecure 的部分写/错误返回（-1 转 size_t 后非 0 仍
  // 被当 true），导致"照片已上传"假成功——broker 收到残包断链丢弃，/img
  // 永远没有 retained。改为循环写满校验（tlsWriteAll）。
  size_t tlen = topic.length();
  uint32_t remLen = (uint32_t)(tlen + 2 + total);
  uint8_t ph[8];
  size_t plen = 0;
  ph[plen++] = 0x31;  // PUBLISH | QoS0 | retained
  do {
    uint8_t d = remLen & 0x7F;
    remLen >>= 7;
    if (remLen) d |= 0x80;
    ph[plen++] = d;
  } while (remLen);
  ph[plen++] = (uint8_t)(tlen >> 8);
  ph[plen++] = (uint8_t)(tlen & 0xFF);

  bool ok = tlsWriteAll(cloudTls, ph, plen) &&
            tlsWriteAll(cloudTls, (const uint8_t*)topic.c_str(), tlen) &&
            tlsWriteAll(cloudTls, msg, total);
  free(msg);
  if (!ok) logLine("CLD", "发布失败 total=" + String(total) + " heap=" + String(ESP.getFreeHeap()));
  if (ok) {
    cloudLastUp = millis() / 1000;
    logLine("CLD", "照片已上传 " + String(olen * 3 / 4) + "B → " + topic);
    // 传完即断：TLS 连接常驻占 ~40KB 堆（CAM 总堆仅 ~100KB，曾致握手
    // rc=-2 与 minHeap 79KB）；上传为小时级，下次上传前重连即可
    cloudMqtt.disconnect();
  } else {
    cloudTls.stop();  // 写失败：TLS 流已不可信（可能已发残包），强制断开由云任务重连
  }
  return ok;
}

static bool cloudConnect() {
  cloudTls.setCACert(EMQXSL_ROOT_CA);
  cloudTls.setHandshakeTimeout(8);
  cloudMqtt.setServer(g_cloud.host.c_str(), g_cloud.port);
  cloudMqtt.setSocketTimeout(6);
  cloudMqtt.setKeepAlive(30);
  cloudMqtt.setBufferSize(512);  // CONNECT 包很小；大 buffer 留到上传前动态分配（CAM 堆紧张）
  String cid = String("iaqua-cam-") + String((uint32_t)(esp_random() & 0xffffff), HEX);
  bool ok = g_cloud.user.length()
      ? cloudMqtt.connect(cid.c_str(), g_cloud.user.c_str(), g_cloud.pass.c_str())
      : cloudMqtt.connect(cid.c_str());
  logLine("CLD", ok ? ("已连接 " + g_cloud.host) : ("连接失败 rc=" + String(cloudMqtt.state())));
  return ok;
}

// 云任务：连接维护 + 定时上传（阻塞操作全部隔离，不影响 HTTP/流服务）
static void cloudTask(void*) {
  uint32_t nextUp = 0;
  for (;;) {
    vTaskDelay(pdMS_TO_TICKS(500));
    if (!cloudConfigured() || WiFi.status() != WL_CONNECTED) {
      cloudNextTry = 0;
      continue;
    }
    bool connected;
    if (xSemaphoreTake(cloudMux, pdMS_TO_TICKS(100)) != pdTRUE) continue;
    connected = cloudMqtt.connected();
    if (!connected && (int32_t)(millis() - cloudNextTry) >= 0) {
      connected = cloudConnect();
      cloudNextTry = millis() + 30000;  // 失败 30s 退避
    }
    if (connected) {
      cloudMqtt.loop();  // 保活
      bool due = cloudSnapReq || (int32_t)(millis() - nextUp) >= 0;
      if (due) {
        cloudSnapReq = false;
        if (cloudUploadNow()) {
          nextUp = millis() + (uint32_t)g_cloud.hours * 3600000UL;
        } else {
          nextUp = millis() + 60000;  // 失败 60s 退避，避免刷屏
        }
      }
    }
    xSemaphoreGive(cloudMux);
  }
}

// ---------------- HTTP 云配置页 ----------------
static void hCloudGet() {
  String html = "<!DOCTYPE html><meta charset=utf-8><title>iAqua-Cam 云上传</title>"
      "<body style='font-family:system-ui;max-width:460px;margin:40px auto'>"
      "<h2>云照片上传（EMQX MQTT over TLS）</h2>"
      "<form method=POST action=/cloud>"
      "启用<input type=checkbox name=en value=1 " + String(g_cloud.en ? "checked" : "") + "><br><br>"
      "Broker 地址<br><input name=host value='" + g_cloud.host + "' style='width:100%'><br><br>"
      "端口（TLS）<br><input name=port value='" + String(g_cloud.port) + "' style='width:100%'><br><br>"
      "用户名<br><input name=user value='" + g_cloud.user + "' style='width:100%'><br><br>"
      "密码<br><input name=pass type=password value='" + g_cloud.pass + "' style='width:100%'><br><br>"
      "主题前缀（与主板 dev_id 一致）<br><input name=topic value='" + g_cloud.topic + "' style='width:100%' placeholder='iaquaria/iaqua-xxxx'><br><br>"
      "上传间隔（小时，>=1）<br><input name=hours value='" + String(g_cloud.hours) + "' style='width:100%'><br><br>"
      "<button style='padding:8px 24px'>保存并重启</button></form>"
      "<p>照片发布到 &lt;主题&gt;/img（retained），App 局域网外可查看最新一张。</p></body>";
  server.send(200, "text/html", html);
}

static void hCloudPost() {
  g_cloud.en    = server.arg("en") == "1";
  g_cloud.host  = server.arg("host");
  g_cloud.user  = server.arg("user");
  g_cloud.pass  = server.arg("pass");
  g_cloud.topic = server.arg("topic");
  g_cloud.port  = server.arg("port").toInt() > 1 ? server.arg("port").toInt() : 8883;
  g_cloud.hours = server.arg("hours").toInt() > 1 ? server.arg("hours").toInt() : 1;
  cloudSaveAndReboot();
}

static void hCloudSnap() {
  if (!cloudConfigured()) {
    server.send(400, "text/plain", "cloud not configured");
    return;
  }
  cloudSnapReq = true;
  server.send(200, "application/json", "{\"ok\":true,\"msg\":\"上传任务已触发\"}");
}

// ---------------- 摄像头 ----------------
static bool camInit() {
  camera_config_t cfg = {};
  cfg.ledc_channel = LEDC_CHANNEL_0;
  cfg.ledc_timer   = LEDC_TIMER_0;
  cfg.pin_pwdn     = CAM_PIN_PWDN;
  cfg.pin_reset    = CAM_PIN_RESET;
  cfg.pin_xclk     = CAM_PIN_XCLK;
  cfg.pin_sccb_sda = CAM_PIN_SIOD;
  cfg.pin_sccb_scl = CAM_PIN_SIOC;
  cfg.pin_d7 = CAM_PIN_Y9;  cfg.pin_d6 = CAM_PIN_Y8;
  cfg.pin_d5 = CAM_PIN_Y7;  cfg.pin_d4 = CAM_PIN_Y6;
  cfg.pin_d3 = CAM_PIN_Y5;  cfg.pin_d2 = CAM_PIN_Y4;
  cfg.pin_d1 = CAM_PIN_Y3;  cfg.pin_d0 = CAM_PIN_Y2;
  cfg.pin_vsync = CAM_PIN_VSYNC;
  cfg.pin_href  = CAM_PIN_HREF;
  cfg.pin_pclk  = CAM_PIN_PCLK;
  cfg.xclk_freq_hz = 20000000;
  cfg.pixel_format = PIXFORMAT_JPEG;
  cfg.grab_mode    = CAMERA_GRAB_LATEST;

  // VGA JPEG 只有十几 KB。放 PSRAM 时和 Wi-Fi 抢缓存，整幅会出现绿/蓝/黑点。
  // 片内 DRAM 装得下，点会消失。PSRAM 仍留给云上传的 base64 缓冲。
  cfg.frame_size   = FRAMESIZE_VGA;
  cfg.jpeg_quality = 16;
  cfg.fb_count     = 1;
  cfg.fb_location  = CAMERA_FB_IN_DRAM;

  esp_err_t err = esp_camera_init(&cfg);
  if (err != ESP_OK) {
    logLine("CAM", "初始化失败 0x" + String(err, HEX));
    return false;
  }
  sensor_t* s = esp_camera_sensor_get();
  if (s) {
    // 官方 CameraWebServer：OV3660 默认过饱和、偏绿，需压饱和度
    if (s->id.PID == OV3660_PID) {
      s->set_vflip(s, 1);
      s->set_brightness(s, 1);
      s->set_saturation(s, -2);
    }
    if (s->set_bpc) s->set_bpc(s, 1);
    if (s->set_wpc) s->set_wpc(s, 1);
    logLine("CAM", String("PID=0x") + String(s->id.PID, HEX) + " VGA/DRAM");
  } else {
    logLine("CAM", "就绪 VGA/DRAM");
  }
  return true;
}

// ---------------- WiFi ----------------
static void wifiSaveAndReboot(const String& ssid, const String& pass) {
  Preferences p;
  p.begin("iacam", false);
  p.putString("ssid", ssid);
  p.putString("pass", pass);
  p.end();
  server.send(200, "text/html",
              "<meta charset=utf-8>已保存，3 秒后重启…<script>setTimeout(()=>location='/',3000)</script>");
  delay(500);
  ESP.restart();
}

static bool wifiConnect() {
  Preferences p;
  p.begin("iacam", true);
  String ssid = p.getString("ssid", "");
  String pass = p.getString("pass", "");
  p.end();
  if (!ssid.length()) {
    ssid = CAM_WIFI_SSID;
    pass = CAM_WIFI_PASS;
  }
  if (!ssid.length()) return false;

  logLine("NET", "连接 " + ssid + " …");
  WiFi.mode(WIFI_STA);
  WiFi.begin(ssid.c_str(), pass.c_str());
  uint32_t t0 = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - t0 < 15000) delay(250);
  if (WiFi.status() == WL_CONNECTED) {
    // 关闭 modem 省电：默认 DTIM 休眠使 ping 延迟抖到 100ms+、TCP 吞吐
    // 塌到 <1KB/s，App 抓一帧 15KB 需 15s+ 直接超时判"不在线"（视频应用必关）
    WiFi.setSleep(false);
  }
  return WiFi.status() == WL_CONNECTED;
}

// ---------------- HTTP 处理器 ----------------
static void hRoot() {
  String j = "{\"model\":\"iAqua-Cam\",\"ip\":\"" + WiFi.localIP().toString() +
             "\",\"ap\":" + (WiFi.getMode() & WIFI_AP ? "true" : "false") +
             ",\"rssi\":" + String(WiFi.RSSI()) +
             ",\"up\":" + String(millis() / 1000) +
             ",\"cam\":" + (camOk ? "true" : "false") +
             ",\"cloud\":{\"en\":" + (cloudConfigured() ? "true" : "false") +
             ",\"topic\":\"" + g_cloud.topic + "\"" +
             ",\"last_up\":" + String(cloudLastUp) + "}}";
  server.send(200, "application/json", j);
}

static void hCapture() {
  if (!camOk) { server.send(503, "text/plain", "camera not ready"); return; }
  camera_fb_t* fb = esp_camera_fb_get();
  if (!fb) { server.send(500, "text/plain", "capture failed"); return; }
  server.sendHeader("Access-Control-Allow-Origin", "*");
  server.send_P(200, "image/jpeg", (const char*)fb->buf, fb->len);
  esp_camera_fb_return(fb);
}

static void hWifiGet() {
  String html = "<!DOCTYPE html><meta charset=utf-8><title>iAqua-Cam</title>"
      "<body style='font-family:system-ui;max-width:420px;margin:40px auto'>"
      "<h2>iAqua-Cam WiFi 配置</h2><form method=POST action=/wifi>"
      "SSID<br><input name=s style='width:100%'><br><br>"
      "密码<br><input name=p type=password style='width:100%'><br><br>"
      "<button style='padding:8px 24px'>保存并重启</button></form></body>";
  server.send(200, "text/html", html);
}

static void hWifiPost() {
  String s = server.arg("s"), p = server.arg("p");
  if (!s.length()) { server.send(400, "text/plain", "ssid empty"); return; }
  wifiSaveAndReboot(s, p);
}

// ---------------- MJPEG 流 ----------------
// 多客户端并发（PC + 手机同看）：每轮循环接受新连接，一帧抓取后广播给所有客户端
#define CAM_STREAM_CLIENTS 3
static WiFiClient streamClients[CAM_STREAM_CLIENTS];

static void pumpStream() {
  for (;;) {                                   // 接入所有待处理的新连接
    WiFiClient cl = streamSrv.available();
    if (!cl) break;
    int slot = -1;
    for (int i = 0; i < CAM_STREAM_CLIENTS; i++) {
      if (!streamClients[i] || !streamClients[i].connected()) { slot = i; break; }
    }
    if (slot < 0) { cl.stop(); continue; }     // 满员：直接拒绝
    logLine("STR", "客户端接入 " + cl.remoteIP().toString() + " slot" + String(slot));
    cl.print("HTTP/1.1 200 OK\r\nContent-Type: multipart/x-mixed-replace;boundary=frame\r\n"
             "Cache-Control: no-cache\r\nConnection: close\r\n\r\n");
    streamClients[slot] = cl;
  }

  bool any = false;
  for (int i = 0; i < CAM_STREAM_CLIENTS; i++) {
    if (streamClients[i] && streamClients[i].connected()) { any = true; break; }
  }
  if (!any) return;

  camera_fb_t* fb = esp_camera_fb_get();       // 抓一帧，广播
  if (!fb) return;
  for (int i = 0; i < CAM_STREAM_CLIENTS; i++) {
    WiFiClient& c = streamClients[i];
    if (!c) continue;
    if (!c.connected()) { c.stop(); streamClients[i] = WiFiClient(); continue; }
    c.printf("--frame\r\nContent-Type: image/jpeg\r\nContent-Length: %u\r\n\r\n", fb->len);
    c.write(fb->buf, fb->len);
    c.print("\r\n");
  }
  esp_camera_fb_return(fb);
  delay(100);                                  // ~10fps，多客户端共享带宽
}

// ---------------- 主流程 ----------------
void setup() {
  bootMs = millis();
  Serial.begin(115200);
  delay(200);
  logLine("SYS", "iAqua-Cam 启动");

  probeTfCard();  // 板载 TF 诊断（须在摄像头 init 前）
  camOk = camInit();
  cloudLoad();          // 云照片上传配置（NVS）
  cloudMux = xSemaphoreCreateMutex();

  if (!wifiConnect()) {
    logLine("NET", "STA 失败，开配网热点 " + String(AP_SSID));
    WiFi.mode(WIFI_AP);
    WiFi.softAP(AP_SSID, AP_PASS);
  } else {
    logLine("NET", "已连接 ip=" + WiFi.localIP().toString() +
                   " rssi=" + String(WiFi.RSSI()) + "dBm");
  }

  if (MDNS.begin("iaqua-cam")) {
    MDNS.addService("http", "tcp", 80);
    MDNS.addService("http", "tcp", 81);
    logLine("NET", "mDNS: iaqua-cam.local");
  }

  server.on("/", hRoot);
  server.on("/capture", hCapture);
  server.on("/wifi", HTTP_GET, hWifiGet);
  server.on("/wifi", HTTP_POST, hWifiPost);
  server.on("/cloud", HTTP_GET, hCloudGet);
  server.on("/cloud", HTTP_POST, hCloudPost);
  server.on("/cloudsnap", hCloudSnap);
  server.on("/log", HTTP_GET, []() {
    // 最近日志 + 内存状态（云端连接诊断）
    String out;
    for (int i = 0; i < 50; i++) {
      String line = s_logRing(i);
      if (line.length()) out += line + "\n";
    }
    out += String("[mem] heap=") + ESP.getFreeHeap() + " psram=" + ESP.getFreePsram() +
           " minHeap=" + ESP.getMinFreeHeap() + "\n";
    server.send(200, "text/plain", out);
  });
  server.begin();
  streamSrv.begin();
  // 云照片上传任务（TLS 阻塞操作隔离，不影响 HTTP/流服务）
  xTaskCreatePinnedToCore(cloudTask, "cloud", 8192, nullptr, 1, nullptr, 1);
  logLine("SYS", "HTTP :80 与流 :81 已就绪");
}

void loop() {
  server.handleClient();
  pumpStream();
}
