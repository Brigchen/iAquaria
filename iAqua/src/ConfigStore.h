#pragma once
#include <Arduino.h>
#include <ArduinoJson.h>
#include <Preferences.h>
#include "Log.h"

namespace iaq {

// 运行时配置：NVS 存一个 JSON 串，带 rev 版本号做乐观并发控制。
// wifi 密码单独存 NVS 键，不进 cfg JSON（下发时天然脱敏）。
// doc 会被 loop 任务与 async_tcp 任务同时访问：跨任务读取一律走 *L() 加锁包装。
class ConfigStore {
public:
  void load();
  void save();

  void lock() const { xSemaphoreTake(_mux, portMAX_DELAY); }
  void unlock() const { xSemaphoreGive(_mux); }

  uint32_t rev() const { return _rev; }
  JsonDocument doc;  // loop 任务内直接访问

  // 点路径单点修改（"ctrl.heater.sp_c"）。rev 不匹配返回 false。
  bool setByPath(const char* path, JsonVariantConst value, uint32_t revIn, String& err);

  String dump();  // 序列化为字符串（cfg 帧用）

  // WiFi 凭据（不参与 rev 并发）
  String wifiSsid() const { return _ssid; }
  String wifiPass() const { return _pass; }
  void setWifi(const String& ssid, const String& pass);

  // 带默认值的点路径读取（loop 任务内使用）
  template <typename T>
  T get(const char* path, T def) const {
    JsonVariantConst v = constPath(path);
    if (v.isNull()) return def;
    return v.as<T>();
  }

  // ---- 跨任务加锁包装（async_tcp 任务与 loop 共用）----
  template <typename T>
  T getL(const char* path, T def) {
    lock();
    T v = get(path, def);
    unlock();
    return v;
  }
  String getStrL(const char* path, const char* def) {
    lock();
    JsonVariantConst v = constPath(path);
    String s = v.isNull() ? String(def) : v.as<String>();
    unlock();
    return s;
  }
  String dumpL() {
    lock();
    String s = dump();
    unlock();
    return s;
  }
  bool setByPathL(const char* path, JsonVariantConst value, uint32_t revIn, String& err) {
    lock();
    bool ok = setByPath(path, value, revIn, err);
    unlock();
    return ok;
  }
  // 批量修改：一次 rev 校验、一次保存（每项 {"path":"a.b","value":x}）
  bool setManyByPathL(JsonArrayConst sets, uint32_t revIn, String& err) {
    lock();
    if (revIn != _rev) {
      unlock();
      err = "BAD_REV: 配置已被其他端修改(rev=" + String(_rev) + ")，请刷新后重试";
      return false;
    }
    for (JsonObjectConst s : sets) {
      JsonVariant cur = doc.as<JsonVariant>();
      const char* p = s["path"] | "";
      bool ok = true;
      while (*p && ok) {  // 复用逐段写入，但不再重复校验 rev
        const char* dot = strchr(p, '.');
        size_t n = dot ? (size_t)(dot - p) : strlen(p);
        char key[24];
        if (n == 0 || n >= sizeof(key)) { ok = false; err = "非法路径"; break; }
        memcpy(key, p, n); key[n] = 0;
        if (!dot) { cur[key].set(s["value"]); break; }
        if (!cur[key].is<JsonObject>()) cur[key].to<JsonObject>();
        cur = cur[key];
        p = dot + 1;
      }
      if (!ok) break;
    }
    _rev++;
    doc["rev"] = _rev;
    save();
    unlock();
    LOGI("配置批量更新 %u 项 → rev=%u", sets.size(), (unsigned)_rev);
    return true;
  }

private:
  void buildDefaults();
  JsonVariantConst constPath(const char* path) const;

  Preferences _prefs;
  uint32_t _rev = 1;
  String _ssid, _pass;
  SemaphoreHandle_t _mux = nullptr;
};

extern ConfigStore config;

}  // namespace iaq
