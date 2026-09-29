#include "ModbusBus.h"
#include "../Config.h"
#include "../ConfigStore.h"
#include "../SensorStore.h"
#include "../Log.h"

namespace iaq {

uint16_t ModbusBus::_buf[32];
static ModbusBus* s_self = nullptr;

void ModbusBus::begin() {
  s_self = this;
  Serial1.begin(9600, SERIAL_8N1, PIN_485_RX, PIN_485_TX);
  _mb.begin(&Serial1, PIN_485_DE);  // DE 引脚收发方向控制（自动收发适配器传 -1）
  _mb.master();
  reloadProfiles();
  LOGI("Modbus RTU 主站就绪 (9600 8N1)");
}

void ModbusBus::tick() {
  _mb.task();  // 库内部收发状态机（回调也在此时机执行）
  if (_inFlight) return;
  if ((int32_t)(millis() - _nextAt) < 0) return;
  if (_lastRev != config.rev()) reloadProfiles();
  sendNext();
}

void ModbusBus::reloadProfiles() {
  _lastRev = config.rev();
  config.lock();
  loadProfile(config.doc["regs"]["tds"], tdsEcDefaults(), _dev[0].prof);
  loadProfile(config.doc["regs"]["ph"], phOrpDefaults(), _dev[1].prof);
  config.unlock();
  _dev[0].nRuns = buildRuns(_dev[0].prof, _dev[0].runs, 4);
  _dev[1].nRuns = buildRuns(_dev[1].prof, _dev[1].runs, 4);
  _curDev = _curRun = 0;
  LOGI("485 档案: tds@%u 段数=%u, ph@%u 段数=%u",
       _dev[0].prof.addr, _dev[0].nRuns, _dev[1].prof.addr, _dev[1].nRuns);
}

void ModbusBus::sendNext() {
  bool issued = false;
  for (uint8_t tried = 0; tried < 4 && !issued; tried++) {
    Dev& d = _dev[_curDev];
    if (d.nRuns && _curRun < d.nRuns) {
      const RegRun& r = d.runs[_curRun];
      issued = (d.prof.fc == 4)
        ? _mb.readIreg(d.prof.addr, r.addr, _buf, r.count, onResp)
        : _mb.readHreg(d.prof.addr, r.addr, _buf, r.count, onResp);
      if (issued) {
        _inFlight = true;
        return;
      }
    }
    advance();  // 该段不可发（设备离线/队列异常），跳到下一段
  }
  _nextAt = millis() + 1000;  // 没有任何事务可发，避免热循环
}

void ModbusBus::advance() {
  if (++_curRun >= _dev[_curDev].nRuns) {
    _curRun = 0;
    if (++_curDev >= 2) _curDev = 0;
  }
}

// 从机通信失败时清除该设备档案所有遥测字段的 fresh 标志，避免 Web 推送残留假值。
static void invalidateDevFields(const DevProfile& prof, Telemetry& t) {
  for (uint8_t i = 0; i < prof.n; i++) {
    Metric* m = fieldMetric(prof.fields[i].name, t);
    if (m) m->fresh = false;
  }
}

bool ModbusBus::onResp(Modbus::ResultCode ev, uint16_t, void*) {
  ModbusBus& self = *s_self;
  self._inFlight = false;
  self._nextAt = millis() + 200;  // 事务间隔
  Dev& d = self._dev[self._curDev];

  if (ev != Modbus::EX_SUCCESS) {
    invalidateDevFields(d.prof, sensors.live);  // 任何失败都清除残留值
    if (d.fails == 0) LOGW("485 addr=%u 无响应(%d)", d.prof.addr, (int)ev);
    if (d.fails < 255) d.fails++;
    if (d.fails == 3) LOGW("485 addr=%u 判定离线", d.prof.addr);
    self.advance();
    return true;
  }
  if (d.fails >= 3) LOGI("485 addr=%u 恢复在线", d.prof.addr);
  d.fails = 0;

  const RegRun& r = d.runs[self._curRun];
  applyRun(d.prof, r, self._buf, sensors.live);
  self.advance();
  return true;
}

}  // namespace iaq
