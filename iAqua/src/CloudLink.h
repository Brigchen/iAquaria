#pragma once
#include <Arduino.h>

namespace iaq {

// 云链路：通过 MQTT over TLS Broker（EMQX Serverless 等）把遥测与执行器
// 事件上行发布，供局域网外的 App 订阅查看。
// 主题：iaquaria/<cloud.dev_id>/tel（30s 保留帧）| iaquaria/<cloud.dev_id>/evt
// 独立 FreeRTOS 任务运行：TLS 握手可阻塞数秒，绝不能占用主循环/看门狗。
class CloudLink {
public:
  void begin();
  // 执行器翻转事件（任意任务可调，内部加锁；未连接时静默丢弃）
  void publishEvt(uint8_t ch, bool on, const char* src);

private:
  static void taskFn(void* arg);
  char _devId[24] = {0};
};

extern CloudLink cloud;

}  // namespace iaq
