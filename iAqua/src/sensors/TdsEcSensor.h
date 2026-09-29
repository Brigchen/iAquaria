#pragma once
#include "RegMap.h"
// TDS/EC 双路水质模块设备档案。
// 9600 8N1，地址默认 01；寄存器表因厂家而异（未知 → M3 用探测工具确认后写入
// cfg.regs.tds.map 热更）。默认假定 ch1/ch2 位于 0x0000/0x0001。
namespace iaq {
inline DevProfile tdsEcDefaults();  // 定义见 RegMap.h
}
