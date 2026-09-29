#pragma once
// ============================================================
// iAqua 编译期配置：引脚表与常量
// 板卡: 经典 ESP32 DevKitC (WROOM-32, ESP32-D0WD-V3, 4MB Flash)
// 引脚以 docs/ESP32硬件系统安装手册.pdf 表 4-1 为准（勿按常见 VSPI 5/18/19/23）
//   GPIO6-11 内部 Flash 禁用；GPIO0/2/12/15 strapping 不接负载；
//   GPIO1/3 UART0 日志；GPIO34-39 仅输入；GPIO5 仅补水泵（须 10kΩ 上拉 3.3V）
// ============================================================
#define IAQ_FW_VERSION "0.1.2"

// ---- RS485 (UART1) 表 4-1 ----
#define PIN_485_TX 17           // → 适配器 DI
#define PIN_485_RX 16           // ← 适配器 RO
#define PIN_485_DE 4            // → DE/RE；自动收发型改为 -1

// ---- 本地传感器 表 4-1 ----
#define PIN_DS18B20 13          // DATA，必须 4.7kΩ 上拉到 3.3V
#define PIN_SR04_TRIG 25        // → HC-SR04 TRIG
#define PIN_SR04_ECHO 26        // ← ECHO 经 1kΩ+2kΩ 分压（5V→3.3V）

// ---- I2C GY-30 BH1750 表 4-1 ----
#define PIN_I2C_SDA 21
#define PIN_I2C_SCL 22
#define BH1750_ADDR 0x23        // ADO 悬空=0x23

// ---- 执行器 表 4-1 / 图 4-4 ----
#define PIN_MOS_CO2 33          // MOS SIG，高电平有效
#define PIN_RELAY_FEEDER 27     // IN1 喂食器，低电平触发
#define PIN_RELAY_LIGHT 14      // IN2 水族灯
#define PIN_RELAY_HEATER 32     // IN3 加热棒
#define PIN_RELAY_PUMP 5        // IN4 补水泵；GPIO5 strapping，须 10kΩ 上拉 3.3V

// ---- TF 卡 SPI 表 4-1 / 图 4-6（GPIO5 已给泵，非默认 VSPI）----
#define PIN_TF_SCK 18
#define PIN_TF_MOSI 19          // 主板 → 卡
#define PIN_TF_MISO 34          // 卡 → 主板（仅输入；模块侧建议 10kΩ 上拉 3.3V）
#define PIN_TF_CS 23
#define PIN_SD_CS PIN_TF_CS
#define PIN_SD_SCK PIN_TF_SCK
#define PIN_SD_MISO PIN_TF_MISO
#define PIN_SD_MOSI PIN_TF_MOSI
#define TF_SPI_HZ 400000
#define TF_HIST_HOURS_MAX 168   // 24h/7d 走 TF 细数据；30d/1y 仍用 LittleFS
#define TF_PERIOD_S_DEFAULT 300  // 遥测写卡间隔秒（5–3600）；300s=每天288条，写卡压力小、曲线仍够用

// ---- 行为常量 ----
#define MODBUS_POLL_PERIOD_MS 2000   // 单个 485 从机轮询周期
#define CONTROL_TICK_MS 1000
#define WATERLEVEL_PERIOD_MS 5000
#define TEMP_PERIOD_MS 5000
#define LIGHT_PERIOD_MS 2000         // 光照测量周期
#define WDT_TIMEOUT_S 2
