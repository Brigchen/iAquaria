#pragma once
#include <Arduino.h>
#include <ArduinoJson.h>
#include "../SensorStore.h"

namespace iaq {

// 寄存器字段：名称 / 寄存器地址 / 缩放系数（实际值 = 原始值 × scale）
struct RegField {
  const char* name;
  uint16_t reg;
  float scale;
};

// 485 从机设备档案：地址 / 功能码 / 字段表
struct DevProfile {
  uint8_t addr;
  uint8_t fc;  // 3 = 保持寄存器, 4 = 输入寄存器
  RegField fields[6];
  uint8_t n;
};

// 连续寄存器读取段
struct RegRun {
  uint16_t addr;
  uint16_t count;
  uint8_t fields[6];  // 落在该段内的字段下标
  uint8_t nFields;
};

// ---- 默认设备档案（国产 OEM 通用协议，M3 探测后通过 cfg.regs 修正）----
// 实测（2026-09-15，2×TDS+2×NTC温度 四通道模块，9600 8N1，出厂地址 2）：
//   reg0 = TDS1(ppm)  reg2 = TDS2(ppm)
//   reg1/reg3 = 模组内部 NTC 温度通道，仅用于 TDS 温补，协议恒返回 128
//   （占位码，不对外发布温度）；reg4+ 不存在。
//   水温统一使用板载 DS18B20（telemetry.temp）。
inline DevProfile phOrpDefaults() {
  DevProfile p{};
  p.addr = 3;  // pH/ORP 模块（避开 TDS 占用的地址 2）
  p.fc = 3;
  // reg0 = 模组自带温度（仅模块内部温补用，不采集；水温用 DS18B20）
  p.fields[0] = {"ph", 1, 0.01f};
  p.fields[1] = {"orp", 9, 0.1f};
  p.n = 2;
  return p;
}

inline DevProfile tdsEcDefaults() {
  DevProfile p{};
  p.addr = 2;  // 实测出厂地址为 2
  p.fc = 3;
  p.fields[0] = {"ch1", 0, 1.0f};  // TDS(滤前)
  p.fields[1] = {"ch2", 2, 1.0f};  // TDS(滤后)，注意是 reg2 不是 reg1
  p.n = 2;
  return p;
}

// 用 cfg.regs.<dev> 覆盖默认档案（map 里按字段名匹配 reg/scale）
inline void loadProfile(JsonVariantConst cfgDev, const DevProfile& dflt, DevProfile& out) {
  out = dflt;
  if (cfgDev.isNull()) return;
  out.addr = cfgDev["addr"] | (int)dflt.addr;
  out.fc = cfgDev["fc"] | (int)dflt.fc;
  JsonVariantConst map = cfgDev["map"];
  if (!map.isNull()) {
    for (uint8_t i = 0; i < out.n; i++) {
      JsonVariantConst f = map[out.fields[i].name];
      if (!f.isNull()) {
        out.fields[i].reg = f["reg"] | (int)out.fields[i].reg;
        out.fields[i].scale = f["scale"] | out.fields[i].scale;
      }
    }
  }
}

// 把字段表合并为尽量少的连续读取段（gap ≤ 2 的字段并入同段）
inline uint8_t buildRuns(const DevProfile& p, RegRun* runs, uint8_t maxRuns) {
  uint8_t order[6];
  for (uint8_t i = 0; i < p.n; i++) order[i] = i;
  for (uint8_t i = 0; i < p.n; i++)  // 按寄存器地址插入排序
    for (uint8_t j = i; j > 0 && p.fields[order[j]].reg < p.fields[order[j - 1]].reg; j--)
      { uint8_t t = order[j]; order[j] = order[j - 1]; order[j - 1] = t; }

  uint8_t n = 0, i = 0;
  while (i < p.n && n < maxRuns) {
    RegRun& r = runs[n];
    r = {};
    r.addr = p.fields[order[i]].reg;
    uint16_t end = r.addr;
    while (i < p.n && p.fields[order[i]].reg <= (uint16_t)(end + 2)) {
      r.fields[r.nFields++] = order[i];
      end = p.fields[order[i]].reg;
      i++;
    }
    r.count = end - r.addr + 1;
    if (r.count > 32) r.count = 32;  // 单次读上限
    n++;
  }
  return n;
}

inline Metric* fieldMetric(const char* name, Telemetry& t) {
  if (!strcmp(name, "ph")) return &t.ph;
  if (!strcmp(name, "orp")) return &t.orp;
  if (!strcmp(name, "ch1")) return &t.tds1;
  if (!strcmp(name, "ch2")) return &t.tds2;
  return nullptr;
}

// 把一段读回的寄存器原始值分发到遥测字段
inline void applyRun(const DevProfile& p, const RegRun& r, const uint16_t* vals, Telemetry& t) {
  uint32_t now = millis();
  for (uint8_t i = 0; i < r.nFields; i++) {
    const RegField& f = p.fields[r.fields[i]];
    if (f.reg >= r.addr && f.reg < r.addr + r.count) {
      if (Metric* m = fieldMetric(f.name, t)) {
        m->v = (float)vals[f.reg - r.addr] * f.scale;
        m->ms = now;
        m->fresh = true;
      }
    }
  }
}

}  // namespace iaq
