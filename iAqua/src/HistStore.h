#pragma once
#include <Arduino.h>
#include "SensorStore.h"

namespace iaq {

// 历史记录 36B：uint32 epoch + 8×float（槽3 已废弃模组温度恒 NAN）
struct HistRec {
  uint32_t ts;
  float v[8];
};
static constexpr uint32_t HIST_REC_BYTES = 36;

void histFillRec(HistRec& r, const Telemetry& s, uint32_t ts);
void histAppendVal(String& out, float v, uint8_t dec);
// n 条按时间递增的记录；read(ctx,i,&r) 取第 i 条。成功写 JSON 返回 true。
bool histBuildJson(uint32_t hours, size_t n,
                   bool (*read)(void* ctx, size_t i, HistRec* r), void* ctx,
                   String& out);
// 慢速介质（TF 卡）专用：稀疏采样单遍构建，read 次数 ≈ MAX_PTS 而非全量 9 遍。
// 记录需按时间递增；范围外记录（跨日文件边界）在采样点处过滤。
bool histBuildJsonSparse(uint32_t hours, size_t n,
                         bool (*read)(void* ctx, size_t i, HistRec* r), void* ctx,
                         String& out);

extern const char* const HIST_SERIES[7];
extern const uint8_t HIST_SERIES_DEC[7];
extern const uint8_t HIST_SERIES_SLOT[7];

// 历史数据存储：flash(LittleFS) 二进制追加，每 30 分钟一条
// 缺测字段 = NAN → 查询时输出 null
// 容量: ~1.9KB/天，上限 640KB ≈ 一年，超限后启动时自动裁掉最旧一半
// 24h/7d 若 TF 卡有数据则优先走 TfStore（更高采样率）
class HistStore {
public:
  void begin();               // 挂载分区 + 容量整理
  void tick();                // loop 调用：整点/半点落一条记录
  bool query(uint32_t hours, String& out);  // JSON，含自动抽稀(~400点/序列)

private:
  void append(uint32_t ts);
  void compactIfNeeded();
  uint32_t _nextTs = 0;
  bool _mounted = false;
  bool _warned = false;
};

extern HistStore hist;

}  // namespace iaq
