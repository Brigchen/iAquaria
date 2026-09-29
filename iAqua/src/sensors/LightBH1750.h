#pragma once
#include <Arduino.h>

namespace iaq {

// GY-30 (BH1750) 光照度采集：连续高分辨率模式（1 lx 分辨率）
// 异步状态机：发测量命令 → 200ms 后读 2 字节，全程不阻塞 loop
class LightBH1750 {
public:
  void begin();
  void tick();  // 每轮 loop 调用（内部自带 2s 节流）
private:
  enum Phase : uint8_t { IDLE, WAIT };
  Phase _phase = IDLE;
  uint32_t _t0 = 0;
  uint32_t _lastReq = 0;
  uint8_t _addr = 0;  // 0 = 未探测到设备
  bool _loggedFail = false;
};

}  // namespace iaq
