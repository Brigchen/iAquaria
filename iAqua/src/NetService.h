#pragma once
#include <Arduino.h>

namespace iaq {

// WiFi STA（带 AP 配网回退）+ NTP 校时 + mDNS(<host>.local，按 MAC/cloud.dev_id 唯一)
class NetService {
public:
  void begin();
  void tick();  // 每轮 loop，内部 3s 节流
  const char* hostname() const { return _host; }

private:
  void resolveHost();  // 优先 cloud.dev_id，否则 MAC 后 4 位 → iaqua-a1b2
  void startAp();
  void startNtp();

  char _host[24] = "iaqua";  // DHCP hostname + mDNS 名（无 .local）
  uint32_t _nextCheck = 0;
  uint32_t _staStart = 0;
  bool _apMode = false;
  bool _ntpSet = false;
  bool _mdnsSet = false;
};

extern NetService net;

}  // namespace iaq
