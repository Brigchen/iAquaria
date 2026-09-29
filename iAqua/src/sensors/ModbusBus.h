#pragma once
#include <Arduino.h>
#include <ModbusRTU.h>
#include "RegMap.h"

namespace iaq {

// RS485 主站轮询引擎：按设备档案（RegMap）逐段读取寄存器，结果写回遥测。
// 设备 0 = TDS/EC(地址1)，设备 1 = pH/ORP(地址2)；档案可由 cfg.regs 热更。
class ModbusBus {
public:
  void begin();
  void tick();  // 每轮 loop 调用（内部状态机节流）

private:
  struct Dev {
    DevProfile prof{};
    RegRun runs[4]{};
    uint8_t nRuns = 0;
    uint8_t fails = 0;
  };

  void reloadProfiles();
  void sendNext();
  void advance();
  static bool onResp(Modbus::ResultCode ev, uint16_t tid, void* data);

  ModbusRTU _mb;
  Dev _dev[2];
  uint8_t _curDev = 0, _curRun = 0;
  bool _inFlight = false;
  uint32_t _nextAt = 0;
  uint32_t _lastRev = 0;
  static uint16_t _buf[32];
};

extern ModbusBus modbus;

}  // namespace iaq
