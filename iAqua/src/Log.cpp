#include "Log.h"
#include "TfStore.h"

namespace iaq {

LogEntry Log::_buf[Log::CAP];
size_t Log::_head = 0;
size_t Log::_count = 0;
static portMUX_TYPE s_logMux = portMUX_INITIALIZER_UNLOCKED;

void Log::write(char level, const char* fmt, ...) {
  LogEntry e;
  e.ms = millis();
  e.level = level;
  va_list args;
  va_start(args, fmt);
  vsnprintf(e.text, sizeof(e.text), fmt, args);
  va_end(args);

  portENTER_CRITICAL(&s_logMux);  // loop 与 async_tcp 两个任务都会写
  _buf[_head] = e;
  _head = (_head + 1) % CAP;
  if (_count < CAP) _count++;
  portEXIT_CRITICAL(&s_logMux);

  Serial.printf("[%10lu][%c] %s\r\n", (unsigned long)e.ms, level, e.text);
  tf.pushLog(e.level, e.text);
}

const LogEntry& Log::at(size_t i) {
  // i: 0 = 最旧（调用方持有日志临界区时读取或尽快拷贝）
  size_t start = (_count < CAP) ? 0 : _head;
  return _buf[(start + i) % CAP];
}

}  // namespace iaq
