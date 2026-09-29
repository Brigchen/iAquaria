#pragma once
#include <Arduino.h>

namespace iaq {

// DS18B20 双相异步采集：REQUEST → 800ms 后读取，全程不阻塞 loop
class TempOneWire {
public:
  void begin();
  void tick();  // 每轮 loop 调用（内部状态机自带节流）
private:
  enum Phase : uint8_t { IDLE, WAIT };
  Phase _phase = IDLE;
  uint32_t _t0 = 0;
};

}  // namespace iaq
