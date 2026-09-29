#pragma once
#include <Arduino.h>

namespace iaq {

// 单个测量量：值 + 更新时刻 + 有效性
struct Metric {
  float v = NAN;
  uint32_t ms = 0;  // 最近更新时刻 millis()，0 = 从未更新
  bool fresh = false;
  uint32_t ageS() const { return ms ? (millis() - ms) / 1000 : 0xFFFFFFFFu; }
};

// 全量遥测快照
struct Telemetry {
  Metric temp;    // DS18B20 水温 ℃
  Metric ph;      // pH
  Metric orp;     // ORP mV
  Metric tds1;    // TDS(滤前) ppm
  Metric tds2;    // TDS(滤后) ppm
  Metric lux;     // GY-30 (BH1750) 光照度 lx
  Metric level;   // 水位百分比 %
  float levelMm = NAN;  // 超声波距离 mm
  int rssi = 0;
  uint32_t freeHeap = 0;
  uint32_t uptimeS = 0;
  bool wifiUp = false, apMode = false, timeOk = false;
};

// 全局唯一遥测数据交换点。
// 写方：仅 loop 任务（各采集器 / 控制引擎）直接改 live 字段。
// 读方：async_tcp 任务（WS 广播）经 snapshot() 短临界区拷贝。
class SensorStore {
public:
  Telemetry snapshot() const {
    Telemetry t;
    portENTER_CRITICAL(&_mux);
    t = _snap;
    portEXIT_CRITICAL(&_mux);
    return t;
  }
  // 由 loop 任务在每个 1s 节拍末发布，供网络任务读取
  void publish() {
    portENTER_CRITICAL(&_mux);
    _snap = live;
    portEXIT_CRITICAL(&_mux);
  }
  Telemetry live;  // loop 任务内直接读写
private:
  mutable portMUX_TYPE _mux = portMUX_INITIALIZER_UNLOCKED;
  Telemetry _snap;
};

extern SensorStore sensors;

}  // namespace iaq
