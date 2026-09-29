#include <Arduino.h>
#include <esp_task_wdt.h>
#include "Config.h"
#include "Log.h"
#include "ConfigStore.h"
#include "SensorStore.h"
#include "Actuators.h"
#include "ControlEngine.h"
#include "NetService.h"
#include "WebService.h"
#include "HistStore.h"
#include "TfStore.h"
#include "CloudLink.h"
#include "sensors/ModbusBus.h"
#include "sensors/TempOneWire.h"
#include "sensors/WaterLevel.h"
#include "sensors/LightBH1750.h"

// 全局实例（头文件里均为 extern 声明；config 在 ConfigStore.cpp 定义）
namespace iaq {
SensorStore sensors;
Actuators actuators;
ControlEngine control;
NetService net;
WebService web;
ModbusBus modbus;
}  // namespace iaq

using namespace iaq;

static TempOneWire temp1w;
static WaterLevel water;
static LightBH1750 light;
static uint32_t s_nextLevel = 0;
static uint32_t s_nextCtrl = 0;

void setup() {
  Serial.begin(115200);
  delay(300);
  LOGI("iAqua v%s 启动 (ESP32)", IAQ_FW_VERSION);

  esp_task_wdt_init(WDT_TIMEOUT_S, true);  // 任务级看门狗：loop 卡死自动复位
  esp_task_wdt_add(NULL);

  config.load();
  actuators.begin();  // 最先初始化：执行器立即进入安全态
  modbus.begin();
  temp1w.begin();
  water.begin();
  light.begin();
  hist.begin();  // flash 历史存储（挂载 + 容量整理）
  tf.begin();    // TF 在 WiFi 之前挂载（VSPI）；失败则任务内重试，不堵 loop WDT
  net.begin();
  web.begin();
  cloud.begin(); // 云链路（EMQX MQTT 上行，独立任务；cloud.en=false 时静默待机）
  LOGI("初始化完成，进入主循环");
}

void loop() {
  esp_task_wdt_reset();
  uint32_t now = millis();

  modbus.tick();   // 485 轮询（异步状态机）
  temp1w.tick();   // DS18B20（异步转换）
  light.tick();    // GY-30 光照（异步转换）

  if ((int32_t)(now - s_nextLevel) >= 0) {  // 水位：5s 一次（内部约 180ms 阻塞采样）
    water.measure();
    s_nextLevel = now + WATERLEVEL_PERIOD_MS;
  }

  if ((int32_t)(now - s_nextCtrl) >= 0) {   // 控制引擎：1s 节拍
    control.tick();
    s_nextCtrl = now + CONTROL_TICK_MS;
  }

  actuators.tick();  // 喂食脉冲收尾
  net.tick();        // WiFi/NTP/mDNS 维护
  hist.tick();       // 30 分钟历史落盘
  sensors.publish(); // 快照发布（WS 广播读快照）
  web.tick();        // 遥测广播 + 延迟动作
}
