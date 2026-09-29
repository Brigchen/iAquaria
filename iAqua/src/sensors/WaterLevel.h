#pragma once
#include <Arduino.h>

namespace iaq {

// HC-SR04 水位：5s 一次，3 采样取中位数 + 野值过滤，两点标定换算百分比
class WaterLevel {
public:
  void begin();
  void measure();  // 每 5s 调用（内部含约 150ms 阻塞采样，可接受）
private:
  float _lastGoodMm = NAN;
  uint8_t _jumpCount = 0;
};

}  // namespace iaq
