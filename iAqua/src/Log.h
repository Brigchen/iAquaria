#pragma once
#include <Arduino.h>

// 简单分级日志：输出到 USB 串口控制台，并保留最近若干条环形缓冲
// （未来可通过 WS 拉取历史日志）
namespace iaq {

struct LogEntry {
  uint32_t ms;
  char level;
  char text[96];
};

class Log {
public:
  static constexpr size_t CAP = 32;
  static void write(char level, const char* fmt, ...);
  static size_t count() { return _count; }
  // 按时间序取第 i 条（i < count）
  static const LogEntry& at(size_t i);
private:
  static LogEntry _buf[CAP];
  static size_t _head;
  static size_t _count;
};

}  // namespace iaq

#define LOGI(...) ::iaq::Log::write('I', __VA_ARGS__)
#define LOGW(...) ::iaq::Log::write('W', __VA_ARGS__)
#define LOGE(...) ::iaq::Log::write('E', __VA_ARGS__)
