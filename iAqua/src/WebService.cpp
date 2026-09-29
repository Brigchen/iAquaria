#include "WebService.h"
#include <ArduinoJson.h>
#include "Config.h"
#include "ConfigStore.h"
#include "SensorStore.h"
#include "Actuators.h"
#include "ControlEngine.h"
#include "HistStore.h"
#include "TfStore.h"
#include "CloudLink.h"
#include "Log.h"
#include "web/www_gz.h"

// ---- WS 协议 ----
// 服务端帧: {"ev":"hello","fw":...,"rev":N} | {"ev":"tel","d":{...}}
//          | {"ev":"cfg","cfg":{...}} | {"ev":"log","rows":[[ms,lv,txt],..]}
//          | {"ev":"ack","ok":bool,"msg":".."}
//          | {"ev":"evt","ch":"co2|feed|light|heater|pump","on":bool,"src":"auto|manual|feed"}
//          | {"ev":"hist","hours":N,"n":N,"src":"tf|lfs",...}
// 客户端帧: {"cmd":"tel"} {"cmd":"cfg"}
//          {"cmd":"cfg.set","path":"a.b","value":x,"rev":N}
//          {"cmd":"ctrl","ch":"co2|light|heater|pump","on":true} 或 {"mode":"auto"}
//          {"cmd":"feed","ms":800} {"cmd":"wifi","ssid":"..","pass":".."}
//          {"cmd":"hist","hours":24|168|720|8760}
//          {"cmd":"log"} {"cmd":"reboot"}

namespace iaq {

static float r2f(float v) { return roundf(v * 100.0f) / 100.0f; }

static const char* chName(uint8_t ch) {
  static const char* N[CH_COUNT] = {"co2", "feed", "light", "heater", "pump"};
  return ch < CH_COUNT ? N[ch] : "?";
}
static uint8_t chFromName(const char* s) {
  for (uint8_t i = 0; i < CH_COUNT; i++)
    if (!strcmp(s, chName(i))) return i;
  return 255;
}

void WebService::begin() {
  _srv.on("/", HTTP_GET, [](AsyncWebServerRequest* req) {
    AsyncWebServerResponse* res =
      req->beginResponse_P(200, "text/html", WWW_GZ, WWW_GZ_LEN);
    res->addHeader("Content-Encoding", "gzip");
    req->send(res);
  });
  _srv.on("/cfg", HTTP_GET, [](AsyncWebServerRequest* req) {
    req->send(200, "application/json", config.dumpL());
  });
  _srv.on("/reboot", HTTP_GET, [this](AsyncWebServerRequest* req) {
    _rebootAt = millis() + 500;
    req->send(200, "application/json", "{\"ok\":true}");
  });

  _ws.onEvent([this](AsyncWebSocket*, AsyncWebSocketClient* client,
                     AwsEventType type, void* arg, uint8_t* data, size_t len) {
    if (type == WS_EVT_CONNECT) {
      LOGI("WS 客户端接入 #%u", client->id());
      String s = "{\"ev\":\"hello\",\"fw\":\"" IAQ_FW_VERSION "\",\"rev\":";
      s += config.rev();
      s += "}";
      client->text(s);
      sendCfgTo(client);
    } else if (type == WS_EVT_DATA) {
      AwsFrameInfo* info = (AwsFrameInfo*)arg;
      if (info->final && info->index == 0 && info->len == len &&
          info->opcode == WS_TEXT)
        handleWsMsg(client, data, len);
    }
  });
  _srv.addHandler(&_ws);
  _srv.begin();
  LOGI("HTTP/WS 服务已启动 :80");
}

void WebService::sendAck(AsyncWebSocketClient* client, bool ok, const char* msg) {
  if (!client || !client->canSend()) return;
  String s = "{\"ev\":\"ack\",\"ok\":";
  s += ok ? "true" : "false";
  if (*msg) {
    s += ",\"msg\":\"";
    s += msg;
    s += "\"";
  }
  s += "}";
  client->text(s);
}

void WebService::broadcastEvt(uint8_t ch, bool on, const char* src) {
  cloud.publishEvt(ch, on, src);  // 云端同步（未启用/未连接时内部静默）
  if (!_ws.count()) return;
  String s = "{\"ev\":\"evt\",\"ch\":\"";
  s += chName(ch);
  s += "\",\"on\":";
  s += on ? "true" : "false";
  s += ",\"src\":\"";
  s += src;
  s += "\"}";
  _ws.textAll(s);
}

void WebService::buildTel(String& out) {
  Telemetry s = sensors.snapshot();
  JsonDocument d;
  JsonObject o = d["d"].to<JsonObject>();
  if (s.temp.fresh) o["temp"] = r2f(s.temp.v);
  if (s.ph.fresh) o["ph"] = r2f(s.ph.v);
  if (s.orp.fresh) o["orp"] = r2f(s.orp.v);
  if (s.tds1.fresh) o["tds1"] = r2f(s.tds1.v);
  if (s.tds2.fresh) o["tds2"] = r2f(s.tds2.v);
  if (s.lux.fresh) o["lux"] = r2f(s.lux.v);
  if (s.level.fresh) o["lvl"] = r2f(s.level.v);
  if (!isnan(s.levelMm)) o["lvlmm"] = r2f(s.levelMm);
  o["rssi"] = s.rssi;
  o["heap"] = s.freeHeap;
  o["up"] = s.uptimeS;
  o["wifi"] = s.wifiUp;
  o["ap"] = s.apMode;
  o["time"] = s.timeOk;
  o["tf"] = tf.mounted();
  o["rev"] = config.rev();

  JsonArray act = o["act"].to<JsonArray>();
  JsonArray man = o["man"].to<JsonArray>();
  for (uint8_t ch = 0; ch < CH_COUNT; ch++) {
    act.add(actuators.on(ch));
    man.add(control.isManual(ch));
  }
  d["ev"] = "tel";  // 前端/上位机按事件类型分发，缺了会被整体丢弃
  serializeJson(d, out);
}

void WebService::sendCfgTo(AsyncWebSocketClient* client) {
  String s = "{\"ev\":\"cfg\",\"cfg\":";
  s += config.dumpL();
  s += "}";
  if (client) client->text(s);
  else _ws.textAll(s);
}

void WebService::handleWsMsg(AsyncWebSocketClient* client, uint8_t* data, size_t len) {
  JsonDocument doc;
  DeserializationError e = deserializeJson(doc, data, len);
  if (e) {
    sendAck(client, false, "JSON 解析失败");
    return;
  }
  const char* cmd = doc["cmd"] | "";

  if (!strcmp(cmd, "tel")) {
    String s;
    buildTel(s);
    client->text(s);
  } else if (!strcmp(cmd, "cfg")) {
    sendCfgTo(client);
  } else if (!strcmp(cmd, "cfg.set")) {
    String err;
    const char* path = doc["path"] | "";
    bool ok = config.setByPathL(path, doc["value"], doc["rev"] | 0u, err);
    sendAck(client, ok, ok ? "已保存" : err.c_str());
    if (ok) sendCfgTo(nullptr);  // 广播新配置给所有客户端
  } else if (!strcmp(cmd, "cfg.setMany")) {
    String err;
    bool ok = config.setManyByPathL(doc["sets"].as<JsonArrayConst>(),
                                    doc["rev"] | 0u, err);
    sendAck(client, ok, ok ? "已保存" : err.c_str());
    if (ok) sendCfgTo(nullptr);
  } else if (!strcmp(cmd, "ctrl")) {
    uint8_t ch = chFromName(doc["ch"] | "");
    if (ch == 255 || ch == CH_FEEDER) {
      sendAck(client, false, "通道无效");
      return;
    }
    if (!strcmp(doc["mode"] | "", "auto")) {
      control.clearManual(ch);
    } else if (!doc["on"].isNull()) {
      control.setManual(ch, doc["on"].as<bool>());
    } else {
      sendAck(client, false, "缺 on/mode");
      return;
    }
    sendAck(client, true, "已下发");
  } else if (!strcmp(cmd, "feed")) {
    uint16_t defMs = (uint16_t)config.getL<float>("ctrl.feeder.pulse_ms", 800.0f);
    uint32_t ms = doc["ms"] | (uint32_t)defMs;
    _feedPendMs = constrain((uint32_t)ms, 100u, 5000u);
    sendAck(client, true, "喂食中");
  } else if (!strcmp(cmd, "wifi")) {
    String ssid = doc["ssid"] | "";
    String pass = doc["pass"] | "";
    if (!ssid.length()) {
      sendAck(client, false, "ssid 不能为空");
      return;
    }
    config.lock();
    config.setWifi(ssid, pass);
    config.unlock();
    _wifiPend = true;  // tick 里延迟重启生效
    sendAck(client, true, "WiFi 已保存，2s 后重启生效");
  } else if (!strcmp(cmd, "hist")) {
    uint32_t h = doc["hours"] | 24u;
    if (h < 1u) h = 1u;
    if (h > 8760u) h = 8760u;
    _histPendHours = h;
    _histPendClient = client->id();
    sendAck(client, true, "查询中");  // 结果以 {"ev":"hist",...} 异步返回
  } else if (!strcmp(cmd, "log")) {
    JsonDocument d;
    JsonArray rows = d["rows"].to<JsonArray>();
    size_t n = Log::count();
    for (size_t i = 0; i < n; i++) {
      const LogEntry& le = Log::at(i);
      JsonArray r = rows.add<JsonArray>();
      r.add(le.ms);
      r.add(String(le.level));
      r.add(le.text);
    }
    d["ev"] = "log";
    String s;
    serializeJson(d, s);
    client->text(s);
  } else if (!strcmp(cmd, "reboot")) {
    _rebootAt = millis() + 500;
    sendAck(client, true, "重启中");
  } else {
    sendAck(client, false, "未知指令");
  }
}

void WebService::tick() {
  uint32_t now = millis();

  // 延迟动作（挪到 loop 任务执行，避免跨任务驱动执行器）
  if (_feedPendMs) {
    actuators.feedPulse((uint16_t)_feedPendMs);
    _feedPendMs = 0;
  }
  if (_wifiPend) {
    _wifiPend = false;
    _rebootAt = now + 2000;
  }
  if (_histPendHours) {  // 历史查询：24h/7d 优先 TF 任务读卡，否则 LittleFS
    uint32_t h = _histPendHours;
    AsyncWebSocketClient* c = _ws.client(_histPendClient);
    auto finish = [&](bool ok, const String& s) {
      _histPendHours = 0;
      _histAwaitTf = false;
      if (c) {
        if (ok) c->text(s);
        else sendAck(c, false, "历史数据读取失败");
      }
    };
    if (_histAwaitTf) {
      String s;
      int r = tf.takeHist(s);
      if (r == 0 && (int32_t)(now - _histAwaitAt) < 8000) {
        // 仍在读卡，下一圈再取，避免堵住 loop/WDT
      } else if (r == 1) {
        finish(true, s);
      } else {
        String s2;
        bool ok = hist.query(h, s2);
        finish(ok, ok ? s2 : s);
      }
    } else if (h <= TF_HIST_HOURS_MAX && tf.mounted() && tf.requestHist(h)) {
      _histAwaitTf = true;
      _histAwaitAt = now;
    } else {
      String s;
      bool ok = hist.query(h, s);
      finish(ok, s);
    }
  }
  if (_rebootAt && (int32_t)(now - _rebootAt) >= 0) {
    LOGI("重启...");
    delay(100);
    ESP.restart();
  }

  if ((int32_t)(now - _lastClean) >= 5000) {
    _lastClean = now;
    _ws.cleanupClients();
  }

  if ((int32_t)(now - _lastPush) >= (int32_t)_pushMs) {
    _lastPush = now;
    _pushMs = config.getL<uint32_t>("telemetry_ms", 1000u);  // 广播周期才读配置
    if (_ws.count()) {
      String s;
      buildTel(s);
      _ws.textAll(s);
    }
  }
}

}  // namespace iaq
