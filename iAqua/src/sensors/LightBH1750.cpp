#include "LightBH1750.h"
#include <Wire.h>
#include "../Config.h"
#include "../SensorStore.h"
#include "../Log.h"

namespace iaq {

// BH1750 命令字（数据手册 5.3 节指令集）
static const uint8_t CMD_CONT_HRES = 0x10;  // 连续高分辨率模式，1 lx，转换 180ms

void LightBH1750::begin() {
  Wire.begin(PIN_I2C_SDA, PIN_I2C_SCL, 100000);
  // 探测地址：ADO 悬空/接 GND = 0x23，接 VCC = 0x5C
  for (uint8_t a : {(uint8_t)BH1750_ADDR, (uint8_t)0x5C}) {
    Wire.beginTransmission(a);
    if (Wire.endTransmission() == 0) {
      _addr = a;
      break;
    }
  }
  if (_addr) {
    LOGI("BH1750 就绪 addr=0x%02X", _addr);
  } else {
    LOGW("未探测到 BH1750（检查 SDA=GPIO%u / SCL=GPIO%u 接线与上拉）", PIN_I2C_SDA, PIN_I2C_SCL);
  }
}

void LightBH1750::tick() {
  if (!_addr) return;  // 无设备，静默跳过
  uint32_t now = millis();

  switch (_phase) {
    case IDLE:
      if (now - _lastReq >= LIGHT_PERIOD_MS) {
        Wire.beginTransmission(_addr);
        Wire.write(CMD_CONT_HRES);
        if (Wire.endTransmission() != 0) {
          if (!_loggedFail) {
            LOGW("BH1750 命令发送失败");
            _loggedFail = true;
          }
          sensors.live.lux.fresh = false;
          _lastReq = now;
          return;
        }
        _phase = WAIT;
        _t0 = now;
        _loggedFail = false;
      }
      break;

    case WAIT:
      if (now - _t0 >= 200) {  // 高分辨率模式转换 180ms
        _lastReq = now;
        _phase = IDLE;
        if (Wire.requestFrom((int)_addr, 2) != 2) {
          sensors.live.lux.fresh = false;
          if (!_loggedFail) {
            LOGW("BH1750 读取失败");
            _loggedFail = true;
          }
          return;
        }
        uint16_t raw = ((uint16_t)Wire.read() << 8) | Wire.read();
        sensors.live.lux.v = (float)raw / 1.2f;
        sensors.live.lux.ms = now;
        sensors.live.lux.fresh = true;
      }
      break;
  }
}

}  // namespace iaq
