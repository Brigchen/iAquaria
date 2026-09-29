#pragma once
#include "RegMap.h"
// pH/ORP 模块（KWL-PO-01A）设备档案。
// 假定为国产 OEM 通用协议（Supmea 风格）：
//   9600 8N1，地址默认 01（本项目改为 03 避免 TDS 冲突）
//   0x0000 = 模组温度 ×0.1℃（仅模块内部温补，不采集；水温用 DS18B20）
//   0x0001 = pH ×0.01
//   0x0002 = pH mV ×0.1
//   0x0009 = ORP ×0.1mV
// 如与实际不符：在 Web/PC 配置页修改 cfg.regs.ph.map 即可热更（无需重编译）。
namespace iaq {
inline DevProfile phOrpDefaults();  // 定义见 RegMap.h
}
