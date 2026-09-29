#pragma once
#include <Arduino.h>
#include <ESPAsyncWebServer.h>

namespace iaq {

// HTTP + WebSocket 服务（含 WS 协议处理）：
//   GET /        嵌入式 gzip 仪表盘
//   GET /cfg     当前配置 JSON
//   GET /reboot  重启
//   WS   /ws     双向协议（见 WebService.cpp 顶部注释）
class WebService {
public:
  void begin();
  void tick();  // loop 调用：定时广播遥测 / 处理延迟动作
  void broadcastEvt(uint8_t ch, bool on, const char* src);  // 执行器状态翻转事件

private:
  void buildTel(String& out);
  void sendCfgTo(AsyncWebSocketClient* client);
  void handleWsMsg(AsyncWebSocketClient* client, uint8_t* data, size_t len);
  void sendAck(AsyncWebSocketClient* client, bool ok, const char* msg = "");

  AsyncWebServer _srv{80};
  AsyncWebSocket _ws{"/ws"};
  uint32_t _lastPush = 0;
  uint32_t _pushMs = 1000;
  uint32_t _lastClean = 0;
  uint32_t _rebootAt = 0;
  volatile uint32_t _feedPendMs = 0;
  volatile bool _wifiPend = false;
  uint32_t _histPendHours = 0;   // hist 查询挪到 loop 任务执行（文件 IO 不占用网络任务）
  uint32_t _histPendClient = 0;
  bool _histAwaitTf = false;
  uint32_t _histAwaitAt = 0;
};

extern WebService web;

}  // namespace iaq
