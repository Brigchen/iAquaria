#include "Actuators.h"
#include "Config.h"
#include "Log.h"
#include "WebService.h"

namespace iaq {

static const uint8_t PINS[CH_COUNT] = {
    PIN_MOS_CO2, PIN_RELAY_FEEDER, PIN_RELAY_LIGHT, PIN_RELAY_HEATER, PIN_RELAY_PUMP};
static const char* NAMES[CH_COUNT] = {"CO2", "喂食", "灯", "加热", "补水泵"};

void Actuators::begin() {
  for (uint8_t ch = 0; ch < CH_COUNT; ch++) {
    if (ch == CH_PUMP) pinMode(PINS[ch], INPUT_PULLUP);  // GPIO5：外接 10kΩ 上拉 3.3V；内部上拉作双保险
    pinMode(PINS[ch], OUTPUT);
    // 继电器低电平触发：断开 = HIGH；MOS 高电平有效：断开 = LOW
    digitalWrite(PINS[ch], (ch == CH_CO2) ? LOW : HIGH);
    _on[ch] = false;
    _since[ch] = millis();
  }
  LOGI("执行器初始化完成（全部断开）");
}

void Actuators::set(uint8_t ch, bool on0, const char* src) {
  if (ch >= CH_COUNT || _on[ch] == on0) return;
  bool drive = (ch == CH_CO2) ? on0 : !on0;
  digitalWrite(PINS[ch], drive ? HIGH : LOW);
  _on[ch] = on0;
  _since[ch] = millis();
  LOGI("%s(%s) → %s", NAMES[ch], src, on0 ? "ON" : "OFF");
  web.broadcastEvt(ch, on0, src);  // 状态翻转事件推送给所有 WS 客户端（App 日志/告警）
}

uint32_t Actuators::sinceS(uint8_t ch) const {
  return (millis() - _since[ch]) / 1000;
}

void Actuators::feedPulse(uint16_t ms) {
  if (_on[CH_FEEDER]) return;  // 正在喂食，忽略重复触发
  _pulseEnd = millis() + ms;
  set(CH_FEEDER, true, "feed");
}

void Actuators::tick() {
  if (_on[CH_FEEDER] && _pulseEnd && (int32_t)(millis() - _pulseEnd) >= 0) {
    _pulseEnd = 0;
    set(CH_FEEDER, false, "feed");
  }
}

}  // namespace iaq
