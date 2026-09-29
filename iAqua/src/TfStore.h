#pragma once
#include <Arduino.h>
#include "Config.h"

namespace iaq {

// TF 卡归档：独立任务挂载/掉卡重试，避免阻塞 loop（2s WDT）。
//   /iaqua/tel/YYYY-MM-DD.csv|.bin  遥测（默认 10s，bin 供 hist 抽稀）
//   /iaqua/evt/YYYY-MM-DD.log       事件/日志
class TfStore {
public:
  void begin();  // 只建队列+任务，SD.begin 在任务里做
  bool mounted() const { return _mounted; }

  // 非阻塞：Log::write / 任意任务可调用；队列满则丢
  void pushLog(char level, const char* text);

  // hist：loop 发起，任务内读卡。request 失败表示未挂载或忙。
  bool requestHist(uint32_t hours);
  // 0=等待  1=成功且 n>0  2=成功但 n=0  -1=失败
  int takeHist(String& out);

private:
  static void taskFn(void* self);
  void loop();
  bool tryMount();
  void unmount();
  void drainLogs();
  void sampleTel();
  void runHist();
  bool ensureDirs();
  bool dayPaths(char* csv, char* bin, char* evt, size_t cap);
  bool queryHist(uint32_t hours, String& out);

  QueueHandle_t _logQ = nullptr;
  volatile bool _mounted = false;
  uint32_t _nextMount = 0;
  uint32_t _nextTel = 0;
  uint32_t _nextCheck = 0;
  uint32_t _spiHz = 0;
  uint64_t _sizeMb = 0;
  uint8_t _cs = PIN_TF_CS;
  char _cardType[8] = "";

  volatile uint8_t _histSt = 0;  // 0 idle  1 req  2 busy  3 done  4 fail
  volatile uint32_t _histHours = 0;
  String _histJson;
};

extern TfStore tf;

}  // namespace iaq
