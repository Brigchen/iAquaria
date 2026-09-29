#include "CloudLink.h"
#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>
#include "CloudCert.h"
#include "ConfigStore.h"
#include "SensorStore.h"
#include "Actuators.h"
#include "ControlEngine.h"
#include "Log.h"

namespace iaq {

CloudLink cloud;

static SemaphoreHandle_t s_mux = nullptr;
static WiFiClientSecure s_wc;
static PubSubClient s_mqtt(s_wc);
static String s_base;            // 主题前缀 iaquaria/<dev_id>
static uint32_t s_nextConnect = 0;
static uint32_t s_nextTel = 0;
static bool s_connected = false;
static uint32_t s_feedPendMs = 0;  // 云端喂食请求（taskFn 锁外延迟执行，避免回调内驱动）

static const char* kChName[CH_COUNT] = {"co2", "feed", "light", "heater", "pump"};

static float r2f(float v) { return roundf(v * 100.0f) / 100.0f; }

static void setConnected(bool up) {
  if (up != s_connected) {
    s_connected = up;
    LOGI("云端 MQTT %s", up ? "已连接" : "已断开");
  }
}

// 通道名 → 序号（255=无效）。与 WebService 的 chFromName 语义一致
static uint8_t chFromName(const char* n) {
  if (!n || !n[0]) return 255;
  for (uint8_t ch = 0; ch < CH_COUNT; ch++) {
    if (!strcmp(n, kChName[ch])) return ch;
  }
  return 255;
}

// 命令执行回执（发到 /evt，ev=cmd_ack；App 端未知事件类型自动忽略）
static void publishAck(bool ok, const char* msg) {
  JsonDocument d;
  d["ev"] = "cmd_ack";
  d["ok"] = ok;
  d["msg"] = msg;
  String s;
  serializeJson(d, s);
  s_mqtt.publish((s_base + "/evt").c_str(), s.c_str());
}

// 云端下行命令（白名单：ctrl 4 通道手动控制 / feed 喂食脉冲）。
// 注意：回调在 s_mqtt.loop() 内同步执行，此时本任务已持有 s_mux，
// 故回调内不得再取 s_mux（非递归互斥量会死锁）；publish 同任务直接调用安全。
static void onMqttMsg(char* topic, byte* payload, unsigned int len) {
  if (s_base.length() < 4 || String(topic) != s_base + "/cmd") return;
  JsonDocument doc;
  if (deserializeJson(doc, payload, len)) {
    publishAck(false, "JSON 解析失败");
    return;
  }
  const char* cmd = doc["cmd"] | "";
  if (!strcmp(cmd, "ctrl")) {
    uint8_t ch = chFromName(doc["ch"] | "");
    if (ch == 255 || ch == CH_FEEDER) {  // 喂食通道只走脉冲，防云端误控
      publishAck(false, "通道无效");
      return;
    }
    if (!strcmp(doc["mode"] | "", "auto")) {
      control.clearManual(ch);
      LOGI("云端命令：恢复自动 ch=%s", kChName[ch]);
    } else if (!doc["on"].isNull()) {
      bool on = doc["on"].as<bool>();
      control.setManual(ch, on);
      LOGI("云端命令：手动 ch=%s %s", kChName[ch], on ? "开" : "关");
    } else {
      publishAck(false, "缺 on/mode");
      return;
    }
    publishAck(true, "已下发");
  } else if (!strcmp(cmd, "feed")) {
    uint16_t defMs = (uint16_t)config.getL<float>("ctrl.feeder.pulse_ms", 800.0f);
    uint32_t ms = doc["ms"] | (uint32_t)defMs;
    s_feedPendMs = constrain((uint32_t)ms, 100u, 5000u);
    LOGI("云端命令：喂食 %ums", (unsigned)ms);
    publishAck(true, "喂食中");
  }
  // 其余命令（cfg.set/wifi/reboot/log 等）云端一律不放行，避免误触危险操作
}

void CloudLink::begin() {
  s_mux = xSemaphoreCreateMutex();
  // dev_id 为空时按 MAC 后 4 位生成（iaqua-a1b2），写回 NVS 供 Web/App 对齐主题
  String id = config.getStrL("cloud.dev_id", "");
  if (id.isEmpty()) {
    uint8_t mac[6];
    WiFi.macAddress(mac);
    char buf[24];
    snprintf(buf, sizeof(buf), "iaqua-%02x%02x", mac[4], mac[5]);
    id = buf;
    config.lock();
    config.doc["cloud"]["dev_id"] = id;
    config.save();
    config.unlock();
  }
  id.toCharArray(_devId, sizeof(_devId));
  s_base = "iaquaria/" + id;

  // 独立任务：TLS 连接/重连/保活/上行（阻塞操作全部隔离在此）
  xTaskCreatePinnedToCore(taskFn, "cloud", 8192, nullptr, 1, nullptr, 1);
  LOGI("云链路模块就绪 dev_id=%s 主题=%s/tel,evt", _devId, s_base.c_str());
}

// 连接云 Broker（在 cloud 任务内调用，允许阻塞）
static bool connectNow() {
  String host = config.getStrL("cloud.host", "");
  if (host.isEmpty()) {
    LOGW("云端未配置 Broker 地址（cloud.host）");
    return false;
  }
  int port = config.getL<int>("cloud.port", 8883);
  String user = config.getStrL("cloud.user", "");
  String pass = config.getStrL("cloud.pass", "");

  s_wc.setCACert(EMQXSL_ROOT_CA);  // DigiCert 根 CA 服务器验证（替代 setInsecure）
  s_wc.setHandshakeTimeout(8);
  s_mqtt.setServer(host.c_str(), port);
  s_mqtt.setSocketTimeout(6);
  s_mqtt.setKeepAlive(30);
  s_mqtt.setBufferSize(640);   // 遥测 JSON 超过默认 256B
  s_mqtt.setCallback(onMqttMsg);  // 云端下行命令（ctrl/feed 白名单）

  char cid[40];
  snprintf(cid, sizeof(cid), "iaqua-%06lu", (unsigned long)(esp_random() % 1000000));
  bool ok = user.isEmpty()
      ? s_mqtt.connect(cid)
      : s_mqtt.connect(cid, user.c_str(), pass.c_str());
  setConnected(ok);
  if (ok) {
    // 订阅云端下行命令主题（QoS1，断线重连后自动重订阅）
    bool sub = s_mqtt.subscribe((s_base + "/cmd").c_str(), 1);
    LOGI("云端 MQTT 已连接 %s:%d cmd订阅%s", host.c_str(), port, sub ? "成功" : "失败");
  } else {
    LOGW("云端连接失败 rc=%d（检查 cloud.* 配置/网络）", s_mqtt.state());
  }
  return ok;
}

// 遥测上行（与 WS tel 帧 d 字段同构，App 复用解析）
static void publishTelNow() {
  Telemetry s = sensors.snapshot();
  JsonDocument d;
  if (s.temp.fresh) d["temp"] = r2f(s.temp.v);
  if (s.ph.fresh) d["ph"] = r2f(s.ph.v);
  if (s.orp.fresh) d["orp"] = r2f(s.orp.v);
  if (s.tds1.fresh) d["tds1"] = r2f(s.tds1.v);
  if (s.tds2.fresh) d["tds2"] = r2f(s.tds2.v);
  if (s.lux.fresh) d["lux"] = r2f(s.lux.v);
  if (s.level.fresh) d["lvl"] = r2f(s.level.v);
  d["rssi"] = s.rssi;
  d["heap"] = s.freeHeap;
  d["up"] = s.uptimeS;
  d["wifi"] = s.wifiUp;
  d["time"] = s.timeOk;
  d["rev"] = config.rev();
  JsonArray act = d["act"].to<JsonArray>();
  for (uint8_t ch = 0; ch < CH_COUNT; ch++) act.add(actuators.on(ch) ? 1 : 0);

  String out;
  serializeJson(d, out);
  s_mqtt.publish((s_base + "/tel").c_str(), out.c_str(), true);  // retained：App 连上立即拿到
}

void CloudLink::taskFn(void*) {
  for (;;) {
    vTaskDelay(pdMS_TO_TICKS(200));
    // 云端喂食：锁外延迟执行（回调只记请求，驱动动作不放在 MQTT 回调内）
    if (s_feedPendMs) {
      uint32_t ms = s_feedPendMs;
      s_feedPendMs = 0;
      actuators.feedPulse((uint16_t)ms);
    }
    const bool en = config.getL<bool>("cloud.en", false);
    if (!en || WiFi.status() != WL_CONNECTED) {
      if (s_connected) {
        if (xSemaphoreTake(s_mux, pdMS_TO_TICKS(200)) == pdTRUE) {
          s_mqtt.disconnect();
          xSemaphoreGive(s_mux);
        }
        setConnected(false);
      }
      s_nextConnect = 0;  // 条件恢复后立即可连
      continue;
    }
    if (!s_mqtt.connected()) {
      if ((int32_t)(millis() - s_nextConnect) >= 0) {
        if (xSemaphoreTake(s_mux, pdMS_TO_TICKS(1000)) == pdTRUE) {
          connectNow();  // 阻塞数秒：独立任务，不影响主循环
          xSemaphoreGive(s_mux);
        }
        s_nextConnect = millis() + 30000;  // 失败 30s 退避
      }
      continue;
    }
    const bool telDue = (int32_t)(millis() - s_nextTel) >= 0;
    if (xSemaphoreTake(s_mux, pdMS_TO_TICKS(100)) == pdTRUE) {
      s_mqtt.loop();  // 保活收包
      if (!s_mqtt.connected()) {
        setConnected(false);
        s_nextConnect = 0;
      } else if (telDue) {
        publishTelNow();
        s_nextTel = millis() + 30000;
      }
      xSemaphoreGive(s_mux);
    }
  }
}

void CloudLink::publishEvt(uint8_t ch, bool on, const char* src) {
  if (s_mux == nullptr || !s_connected || ch >= CH_COUNT) return;
  if (xSemaphoreTake(s_mux, pdMS_TO_TICKS(50)) != pdTRUE) return;
  if (s_mqtt.connected()) {
    char payload[96];
    snprintf(payload, sizeof(payload), "{\"ch\":\"%s\",\"on\":%s,\"src\":\"%s\"}",
             kChName[ch], on ? "true" : "false", src);
    s_mqtt.publish((s_base + "/evt").c_str(), payload);
  }
  xSemaphoreGive(s_mux);
}

}  // namespace iaq
