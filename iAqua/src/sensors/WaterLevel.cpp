#include "WaterLevel.h"
#include "../Config.h"
#include "../ConfigStore.h"
#include "../SensorStore.h"
#include "../Log.h"

namespace iaq {

static uint32_t readOnce() {
  digitalWrite(PIN_SR04_TRIG, LOW);
  delayMicroseconds(3);
  digitalWrite(PIN_SR04_TRIG, HIGH);
  delayMicroseconds(10);
  digitalWrite(PIN_SR04_TRIG, LOW);
  uint32_t us = pulseIn(PIN_SR04_ECHO, HIGH, 25000UL);  // 硬超时 25ms
  if (us == 0) return 0;
  return (uint32_t)(us * 0.1715f);  // → mm（声速 343m/s，往返减半）
}

void WaterLevel::begin() {
  pinMode(PIN_SR04_TRIG, OUTPUT);
  digitalWrite(PIN_SR04_TRIG, LOW);
  pinMode(PIN_SR04_ECHO, INPUT);
  LOGI("HC-SR04 就绪");
}

void WaterLevel::measure() {
  float mm_empty = config.getL<float>("ctrl.level.mm_empty", 420.0f);
  float mm_full = config.getL<float>("ctrl.level.mm_full", 80.0f);
  float span = mm_empty - mm_full;
  if (span <= 10.0f) {  // 标定不合法
    sensors.live.level.fresh = false;
    return;
  }

  uint32_t s[3] = {0, 0, 0};
  uint8_t n = 0;
  for (uint8_t i = 0; i < 3; i++) {
    uint32_t mm = readOnce();
    if (mm >= 20 && mm <= 4500) s[n++] = mm;
    delayMicroseconds(60000);  // 60ms 间隔防余波（5s 才进一次，阻塞可接受）
  }
  if (n < 2) {  // 有效采样不足
    sensors.live.level.fresh = false;
    return;
  }
  // 中位数（n≤3 直接比较）
  uint32_t med = s[0];
  if (n == 3) {
    if ((s[0] >= s[1] && s[0] <= s[2]) || (s[0] >= s[2] && s[0] <= s[1])) med = s[0];
    else if ((s[1] >= s[0] && s[1] <= s[2]) || (s[1] >= s[2] && s[1] <= s[0])) med = s[1];
    else med = s[2];
  } else med = (s[0] < s[1]) ? s[0] : s[1];

  // 野值过滤：单次跳变超过量程 20% 需连续 3 次确认才接受
  if (!isnan(_lastGoodMm)) {
    if (fabsf((float)med - _lastGoodMm) > span * 0.2f) {
      if (++_jumpCount < 3) return;  // 维持旧值
    }
  }
  _jumpCount = 0;
  _lastGoodMm = (float)med;

  float pct = (mm_empty - (float)med) * 100.0f / span;
  pct = constrain(pct, 0.0f, 100.0f);
  sensors.live.level.v = pct;
  sensors.live.levelMm = (float)med;
  sensors.live.level.ms = millis();
  sensors.live.level.fresh = true;
}

}  // namespace iaq
