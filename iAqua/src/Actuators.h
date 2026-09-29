#pragma once
#include <Arduino.h>

namespace iaq {

// 通道编号（遥测帧 act/man 数组也按此顺序）
enum Ch : uint8_t { CH_CO2, CH_FEEDER, CH_LIGHT, CH_HEATER, CH_PUMP, CH_COUNT };

// 执行器驱动：MOS 管 CO2 电磁阀（高电平有效）+ 4 路继电器（低电平触发）。
// 上电安全态：全部断开（继电器控制脚拉高 = 断开）。
class Actuators {
public:
  void begin();
  // src: 动作来源（auto/manual/feed），随状态翻转事件广播给 WS 客户端
  void set(uint8_t ch, bool on, const char* src = "auto");  // 幂等；内部记录持续时长
  bool on(uint8_t ch) const { return _on[ch]; }
  uint32_t sinceS(uint8_t ch) const;          // 当前状态已持续秒数
  void feedPulse(uint16_t ms);                // 喂食：闭合 ms 后自动断开
  void tick();                                // 处理喂食脉冲收尾

private:
  bool _on[CH_COUNT] = {};
  uint32_t _since[CH_COUNT] = {};
  uint32_t _pulseEnd = 0;
};

extern Actuators actuators;

}  // namespace iaq
