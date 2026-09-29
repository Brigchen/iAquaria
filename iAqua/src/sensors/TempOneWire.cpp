#include "TempOneWire.h"
#include <OneWire.h>
#include <DallasTemperature.h>
#include "../Config.h"
#include "../SensorStore.h"
#include "../Log.h"

namespace iaq {

static OneWire s_oneWire(PIN_DS18B20);
static DallasTemperature s_sensors(&s_oneWire);
static uint32_t s_lastReq = 0;

void TempOneWire::begin() {
  s_sensors.begin();
  s_sensors.setWaitForConversion(false);  // 异步模式：请求后 750ms 再读
  LOGI("DS18B20 就绪，探测到 %d 个探头", s_sensors.getDeviceCount());
}

void TempOneWire::tick() {
  uint32_t now = millis();
  switch (_phase) {
    case IDLE:
      if (now - s_lastReq >= TEMP_PERIOD_MS) {
        s_sensors.requestTemperatures();  // 触发转换，立即返回
        _phase = WAIT;
        _t0 = now;
        if (!s_lastReq) s_lastReq = now;  // 首次
      }
      break;
    case WAIT:
      if (now - _t0 >= 800) {  // 12bit 转换最长 750ms
        float c = s_sensors.getTempCByIndex(0);
        if (isnan(c) || c <= -100.0f) {  // DEVICE_DISCONNECTED_C = -127
          sensors.live.temp.fresh = false;
          LOGW("DS18B20 读数无效");
        } else {
          sensors.live.temp.v = c;
          sensors.live.temp.ms = now;
          sensors.live.temp.fresh = true;
        }
        s_lastReq = now;
        _phase = IDLE;
      }
      break;
  }
}

}  // namespace iaq
