#pragma once
#include <Arduino.h>
#include "Actuators.h"

namespace iaq {

// 控制引擎：1s 节拍，按遥测 + 配置计算各执行器目标态。
// 手动覆盖不持久化（重启回到 auto）；喂食为纯手动脉冲。
// 安全矩阵：
//   温度数据过期(>60s)     → 加热棒强制关
//   pH 数据过期(>120s)     → CO2 强制关
//   光照数据过期(>60s)     → 灯保持当前状态（lux 模式）
//   连续运行超 max_on_min  → 加热棒/CO2 强制关（灯/补水泵不限制）
//   校时未完成             → 灯强制关（定时模式）
//   补水泵默认关（ctrl.pump.default_on=false）
class ControlEngine {
public:
  void tick();  // 每 1s 调用

  void setManual(uint8_t ch, bool on);
  void clearManual(uint8_t ch);
  bool isManual(uint8_t ch) const { return _manual[ch]; }

private:
  bool autoTarget(uint8_t ch);

  bool _manual[CH_COUNT] = {};
  bool _manualVal[CH_COUNT] = {};
  bool _loggedStale = false;
};

extern ControlEngine control;

}  // namespace iaq
