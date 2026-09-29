#include "NetService.h"
#include <WiFi.h>
#include <ESPmDNS.h>
#include "ConfigStore.h"
#include "SensorStore.h"
#include "Log.h"

namespace iaq {

void NetService::resolveHost() {
  // 与 CloudLink 对齐：已有 cloud.dev_id 则复用；否则 MAC 后 4 位生成
  String id = config.getStrL("cloud.dev_id", "");
  if (id.isEmpty()) {
    uint8_t mac[6];
    WiFi.macAddress(mac);
    snprintf(_host, sizeof(_host), "iaqua-%02x%02x", mac[4], mac[5]);
  } else {
    // 主机名仅允许字母数字与 '-'，过长截断
    size_t n = 0;
    for (size_t i = 0; i < id.length() && n + 1 < sizeof(_host); ++i) {
      char c = id[i];
      if ((c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') ||
          (c >= '0' && c <= '9') || c == '-') {
        _host[n++] = (char)tolower((unsigned char)c);
      }
    }
    _host[n] = '\0';
    if (n == 0) snprintf(_host, sizeof(_host), "iaqua");
  }
}

void NetService::begin() {
  WiFi.persistent(false);
  resolveHost();
  WiFi.setHostname(_host);
  String ssid = config.wifiSsid();
  WiFi.mode(WIFI_AP_STA);  // AP 常备：STA 失联时自动兜底，配网不中断
  if (ssid.length()) {
    WiFi.begin(ssid.c_str(), config.wifiPass().c_str());
    _staStart = millis();
    LOGI("WiFi 连接中 ssid=%s host=%s", ssid.c_str(), _host);
  } else {
    LOGW("未配置 WiFi，请连 AP: iAqua-Setup / 12345678 → http://192.168.4.1");
    startAp();
  }
}

void NetService::startAp() {
  if (_apMode) return;
  WiFi.softAP("iAqua-Setup", "12345678");
  _apMode = true;
  LOGI("AP 已启动 ssid=iAqua-Setup pass=12345678 http://192.168.4.1");
}

void NetService::startNtp() {
  if (_ntpSet) return;
  configTzTime("CST-8", "ntp.aliyun.com", "ntp1.aliyun.com", "pool.ntp.org");
  _ntpSet = true;
  LOGI("NTP 校时启动 (CST-8)");
}

void NetService::tick() {
  uint32_t now = millis();
  if ((int32_t)(now - _nextCheck) < 0) return;
  _nextCheck = now + 3000;

  Telemetry& t = sensors.live;
  bool staUp = (WiFi.status() == WL_CONNECTED);
  t.wifiUp = staUp;
  t.apMode = _apMode;
  t.timeOk = staUp && time(nullptr) > 1700000000;  // 2023 之后的合理时间戳

  if (staUp) {
    t.rssi = WiFi.RSSI();
    startNtp();
    if (!_mdnsSet) {
      if (MDNS.begin(_host)) {
        MDNS.addService("http", "tcp", 80);
        _mdnsSet = true;
        LOGI("mDNS 就绪 http://%s.local  ip=%s", _host, WiFi.localIP().toString().c_str());
      }
    }
    if (_apMode) {  // STA 恢复后关掉 AP
      WiFi.softAPdisconnect(true);
      _apMode = false;
      LOGI("STA 已恢复，关闭 AP");
    }
  } else {
    t.rssi = 0;
    if (!_staStart) _staStart = now;
    if (config.wifiSsid().length() && (now - _staStart > 20000) && !_apMode) {
      LOGW("STA 20s 未连上，进入 AP 配网模式");
      startAp();
    }
    if (_apMode && config.wifiSsid().length() && (now % 60000 < 3000)) {
      WiFi.begin(config.wifiSsid().c_str(), config.wifiPass().c_str());  // 每 60s 重试
      _staStart = now;
    }
  }
}

}  // namespace iaq
