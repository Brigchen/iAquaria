#include "ConfigStore.h"
#include "Config.h"

namespace iaq {

ConfigStore config;

void ConfigStore::load() {
  if (!_mux) _mux = xSemaphoreCreateMutex();
  _prefs.begin("iaqua", false);
  _ssid = _prefs.getString("wifissid", "");
  _pass = _prefs.getString("wifipass", "");

  String s = _prefs.getString("cfgjson", "");
  bool ok = false;
  if (s.length()) {
    DeserializationError e = deserializeJson(doc, s);
    ok = (e == DeserializationError::Ok);
    if (!ok) LOGW("cfg NVS 解析失败(%s)，恢复默认", e.c_str());
  }
  if (!ok || !doc["ctrl"].is<JsonObject>()) {
    buildDefaults();
    save();
    LOGI("配置已写入默认值");
  } else {
    // 旧配置升级：补齐新增键（灯光强联动、补水泵默认关）
    bool migrated = false;
    JsonVariant ctrlV = doc["ctrl"];
    JsonVariant lV = ctrlV["light"];
    if (lV.isNull()) { ctrlV["light"].to<JsonObject>(); lV = ctrlV["light"]; }
    if (lV["mode"].isNull())   { lV["mode"] = "lux";  migrated = true; }
    if (lV["lux_on"].isNull()) { lV["lux_on"] = 100.0; migrated = true; }
    if (lV["lux_off"].isNull()) { lV["lux_off"] = 300.0; migrated = true; }
    JsonVariant pV = ctrlV["pump"];
    if (pV.isNull()) { ctrlV["pump"].to<JsonObject>(); pV = ctrlV["pump"]; }
    if (pV["default_on"].isNull()) {
      pV["default_on"] = false;
      migrated = true;
    } else if (migrated && pV["default_on"].as<bool>()) {
      pV["default_on"] = false;  // 老配置一次性从「常开」改为「默认关」
    }
    if (doc["cam"].isNull()) {  // 摄像头节点配置（0.1.1 新增）
      JsonObject camV = doc["cam"].to<JsonObject>();
      camV["url"] = "";
      migrated = true;
    }
    if (doc["tf"].isNull()) {
      JsonObject tfV = doc["tf"].to<JsonObject>();
      tfV["period_s"] = TF_PERIOD_S_DEFAULT;
      migrated = true;
    } else {
      // 旧默认 10s 写卡太频繁（每天 8640 条），一次性迁移到新默认 300s；
      // pmig 标记保证只迁一次，用户之后手动改回小值不会被重置
      JsonVariant tfV = doc["tf"];
      if (tfV["pmig"].isNull()) {
        tfV["pmig"] = 2;
        if (tfV["period_s"].isNull() || tfV["period_s"].as<int>() <= 60) {
          tfV["period_s"] = TF_PERIOD_S_DEFAULT;
        }
        migrated = true;
      }
    }
    if (migrated) save();
  }
  _rev = doc["rev"] | 1u;
  LOGI("配置加载完成 rev=%u", (unsigned)_rev);
}

void ConfigStore::save() {
  String s;
  serializeJson(doc, s);
  _prefs.putString("cfgjson", s);
}

void ConfigStore::buildDefaults() {
  doc.clear();
  doc["rev"] = 1;

  JsonObject ctrl = doc["ctrl"].to<JsonObject>();
  JsonObject h = ctrl["heater"].to<JsonObject>();
  h["sp_c"] = 25.0;
  h["hyst_c"] = 0.5;
  h["max_on_min"] = 45;

  JsonObject c = ctrl["co2"].to<JsonObject>();
  c["ph_on"] = 7.0;   // pH 高于该值才补 CO2
  c["ph_off"] = 6.8;  // pH 低于该值关阀（回差）
  c["follow_light"] = true;
  c["max_on_min"] = 120;

  JsonObject l = ctrl["light"].to<JsonObject>();
  l["on"] = "08:00";
  l["off"] = "20:00";
  l["mode"] = "lux";     // time=定时 | lux=光强联动
  l["lux_on"] = 100.0;   // 光照 ≤ 该值开灯
  l["lux_off"] = 300.0;  // 光照 ≥ 该值关灯（区间内保持 = 回差）

  JsonObject f = ctrl["feeder"].to<JsonObject>();
  f["pulse_ms"] = 800;

  JsonObject p = ctrl["pump"].to<JsonObject>();
  p["default_on"] = false;  // 补水泵默认关（避免误启动）

  JsonObject lv = ctrl["level"].to<JsonObject>();
  lv["mm_empty"] = 420;  // 水位 0% 时的超声波距离 mm
  lv["mm_full"] = 80;    // 水位 100% 时的距离 mm
  lv["warn_hi"] = 95;
  lv["warn_lo"] = 20;

  doc["telemetry_ms"] = 1000;

  JsonObject cam = doc["cam"].to<JsonObject>();
  cam["url"] = "";  // 摄像头节点基地址，如 http://iaqua-cam.local（流=:81/stream 快照=/capture）

  JsonObject tf = doc["tf"].to<JsonObject>();
  tf["period_s"] = TF_PERIOD_S_DEFAULT;  // 遥测写卡间隔秒（5–3600，默认 300）

  // 云链路（EMQX Serverless 等 MQTT over TLS Broker）：App 局域网外云查看
  JsonObject cl = doc["cloud"].to<JsonObject>();
  cl["en"] = false;      // 上行开关
  cl["host"] = "";       // Broker 域名，如 xxxx.ala.cn-hangzhou.emqxsl.cn
  cl["port"] = 8883;     // MQTT over TLS
  cl["user"] = "";       // 认证用户名
  cl["pass"] = "";       // 认证密码（仅存设备 NVS）
  cl["dev_id"] = "";     // 设备标识（主题 iaquaria/<dev_id>/tel|evt），空则按 MAC 生成

  // 485 从机寄存器映射（未知设备先按国产 OEM 通用表，M3 探测后修正）
  JsonObject regs = doc["regs"].to<JsonObject>();
  JsonObject ph = regs["ph"].to<JsonObject>();
  ph["addr"] = 2;
  ph["fc"] = 3;
  JsonObject phm = ph["map"].to<JsonObject>();
  phm["temp"]["reg"] = 0;  phm["temp"]["scale"] = 0.1;
  phm["ph"]["reg"] = 1;    phm["ph"]["scale"] = 0.01;
  phm["orp"]["reg"] = 9;   phm["orp"]["scale"] = 0.1;

  JsonObject td = regs["tds"].to<JsonObject>();
  td["addr"] = 1;
  td["fc"] = 3;
  JsonObject tdm = td["map"].to<JsonObject>();
  tdm["ch1"]["reg"] = 0;  tdm["ch1"]["scale"] = 1;
  tdm["ch2"]["reg"] = 1;  tdm["ch2"]["scale"] = 1;

  JsonObject wf = doc["wifi"].to<JsonObject>();
  wf["ssid"] = _ssid;  // 只存 ssid 展示，密码在独立 NVS 键
}

JsonVariantConst ConfigStore::constPath(const char* path) const {
  JsonVariantConst cur = doc.as<JsonVariantConst>();
  const char* p = path;
  while (*p) {
    const char* dot = strchr(p, '.');
    size_t n = dot ? (size_t)(dot - p) : strlen(p);
    char key[24];
    if (n >= sizeof(key)) return JsonVariantConst();
    memcpy(key, p, n);
    key[n] = 0;
    cur = cur[key];
    if (cur.isNull()) return cur;
    p = dot ? dot + 1 : p + n;
  }
  return cur;
}

bool ConfigStore::setByPath(const char* path, JsonVariantConst value,
                            uint32_t revIn, String& err) {
  if (revIn != _rev) {
    err = "BAD_REV: 配置已被其他端修改(rev=" + String(_rev) + ")，请重新获取";
    return false;
  }
  if (!path || !*path) {
    err = "空路径";
    return false;
  }
  JsonVariant cur = doc.as<JsonVariant>();
  const char* p = path;
  for (;;) {
    const char* dot = strchr(p, '.');
    size_t n = dot ? (size_t)(dot - p) : strlen(p);
    char key[24];
    if (n == 0 || n >= sizeof(key)) {
      err = "非法路径";
      return false;
    }
    memcpy(key, p, n);
    key[n] = 0;
    if (!dot) {  // 最后一段
      cur[key].set(value);
      break;
    }
    if (!cur[key].is<JsonObject>()) cur[key].to<JsonObject>();
    cur = cur[key];
    p = dot + 1;
  }
  _rev++;
  doc["rev"] = _rev;
  save();
  LOGI("配置更新 %s → rev=%u", path, (unsigned)_rev);
  return true;
}

String ConfigStore::dump() {
  String s;
  serializeJson(doc, s);
  return s;
}

void ConfigStore::setWifi(const String& ssid, const String& pass) {
  _ssid = ssid;
  _prefs.putString("wifissid", ssid);
  if (pass.length()) _prefs.putString("wifipass", pass);
  doc["wifi"]["ssid"] = ssid;
  LOGI("WiFi 凭据已保存 ssid=%s", ssid.c_str());
}

}  // namespace iaq
