#include "HistStore.h"
#include <LittleFS.h>
#include <time.h>
#include <esp_task_wdt.h>
#include "SensorStore.h"
#include "Log.h"

namespace iaq {

HistStore hist;

const char* const HIST_SERIES[7] = {"temp", "ph", "orp", "tds1", "tds2", "lux", "lvl"};
const uint8_t HIST_SERIES_DEC[7] = {2, 2, 0, 0, 0, 0, 1};
const uint8_t HIST_SERIES_SLOT[7] = {0, 1, 2, 4, 5, 6, 7};

namespace {
constexpr const char* HIST_PATH = "/hist.bin";
constexpr uint32_t PERIOD_S = 1800;       // 30 分钟
constexpr uint32_t CAP_BYTES = 640 * 1024;
constexpr size_t MAX_PTS = 400;
}  // namespace

void histFillRec(HistRec& r, const Telemetry& s, uint32_t ts) {
  r.ts = ts;
  float* p = r.v;
  *p++ = s.temp.fresh  ? s.temp.v  : NAN;
  *p++ = s.ph.fresh    ? s.ph.v    : NAN;
  *p++ = s.orp.fresh   ? s.orp.v   : NAN;
  *p++ = NAN;
  *p++ = s.tds1.fresh  ? s.tds1.v  : NAN;
  *p++ = s.tds2.fresh  ? s.tds2.v  : NAN;
  *p++ = s.lux.fresh   ? s.lux.v   : NAN;
  *p   = s.level.fresh ? s.level.v : NAN;
}

void histAppendVal(String& out, float v, uint8_t dec) {
  if (isnan(v)) { out += "null"; return; }
  char buf[16];
  snprintf(buf, sizeof(buf), "%.*f", dec, v);
  out += buf;
}

bool histBuildJson(uint32_t hours, size_t n,
                   bool (*read)(void* ctx, size_t i, HistRec* r), void* ctx,
                   String& out) {
  if (!n) {
    out = "{\"ev\":\"hist\",\"hours\":" + String(hours) + ",\"n\":0}";
    return true;
  }
  uint32_t now = (uint32_t)time(nullptr);
  uint32_t from = now > hours * 3600u ? now - hours * 3600u : 0;

  size_t lo = n, hi = 0, cnt = 0;
  HistRec r;
  for (size_t i = 0; i < n; i++) {
    if (!read(ctx, i, &r)) break;
    if (r.ts >= from) {
      if (i < lo) lo = i;
      hi = i;
      cnt++;
    }
  }
  if (!cnt) {
    out = "{\"ev\":\"hist\",\"hours\":" + String(hours) + ",\"n\":0}";
    return true;
  }
  size_t stride = (cnt + MAX_PTS - 1) / MAX_PTS;
  if (stride < 1) stride = 1;
  size_t nPick = (cnt + stride - 1) / stride;

  out = "{\"ev\":\"hist\",\"hours\":";
  out += hours;
  out += ",\"src\":\"lfs\"";
  out += ",\"n\":";
  out += nPick;
  out += ",\"ts\":[";

  size_t picked = 0, seen = 0;
  for (size_t i = lo; i <= hi; i++) {
    if (!read(ctx, i, &r)) break;
    if (r.ts < from) continue;
    if (seen++ % stride) continue;
    if (picked++) out += ",";
    out += r.ts;
  }
  out += "]";
  for (uint8_t s = 0; s < 7; s++) {
    out += ",\"";
    out += HIST_SERIES[s];
    out += "\":[";
    picked = 0;
    seen = 0;
    for (size_t i = lo; i <= hi; i++) {
      if (!read(ctx, i, &r)) break;
      if (r.ts < from) continue;
      if (seen++ % stride) continue;
      if (picked++) out += ",";
      histAppendVal(out, r.v[HIST_SERIES_SLOT[s]], HIST_SERIES_DEC[s]);
    }
    out += "]";
  }
  out += "}";
  return true;
}

// 慢速介质（TF 卡）专用：稀疏采样单遍构建。
// histBuildJson 需全量扫描 9 遍（找范围 + ts + 7 序列各一遍），SD 卡逐条
// seek+read 时 7 天查询（6 万条）耗时 60s+ 直接超时；本版本按 stride 只
// 读取 ~MAX_PTS 个采样点，一次遍历同时拼装 ts 与全部序列。
bool histBuildJsonSparse(uint32_t hours, size_t n,
                         bool (*read)(void* ctx, size_t i, HistRec* r), void* ctx,
                         String& out) {
  if (!n) {
    out = "{\"ev\":\"hist\",\"hours\":" + String(hours) + ",\"n\":0}";
    return true;
  }
  uint32_t now = (uint32_t)time(nullptr);
  uint32_t from = now > hours * 3600u ? now - hours * 3600u : 0;

  size_t stride = (n + MAX_PTS - 1) / MAX_PTS;
  if (stride < 1) stride = 1;

  String tsArr, serArr[7];
  HistRec r;
  size_t picked = 0;
  for (size_t i = 0; i < n; i += stride) {
    esp_task_wdt_reset();  // 逐条 seek+read 慢，防任务喂狗超时
    if (!read(ctx, i, &r)) break;
    if (r.ts < from || r.ts > now) continue;  // 跨日文件边界可能含范围外记录
    if (picked) {
      tsArr += ',';
      for (uint8_t s = 0; s < 7; s++) serArr[s] += ',';
    }
    tsArr += r.ts;
    for (uint8_t s = 0; s < 7; s++)
      histAppendVal(serArr[s], r.v[HIST_SERIES_SLOT[s]], HIST_SERIES_DEC[s]);
    picked++;
  }

  out = "{\"ev\":\"hist\",\"hours\":";
  out += hours;
  out += ",\"src\":\"lfs\"";
  out += ",\"n\":";
  out += picked;
  out += ",\"ts\":[";
  out += tsArr;
  out += "]";
  for (uint8_t s = 0; s < 7; s++) {
    out += ",\"";
    out += HIST_SERIES[s];
    out += "\":[";
    out += serArr[s];
    out += "]";
  }
  out += "}";
  return true;
}

namespace {
struct LfsCtx {
  File* f;
};
bool lfsRead(void* ctx, size_t i, HistRec* r) {
  if ((i & 0x3F) == 0) esp_task_wdt_reset();
  LfsCtx* c = (LfsCtx*)ctx;
  if (!c->f->seek(i * HIST_REC_BYTES)) return false;
  return c->f->read((uint8_t*)r, HIST_REC_BYTES) == HIST_REC_BYTES;
}
}  // namespace

void HistStore::begin() {
  _mounted = LittleFS.begin(true, "/h", 6, "spiffs");
  if (!_mounted) {
    LOGW("LittleFS 挂载失败，历史记录不可用");
    return;
  }
  compactIfNeeded();
  uint32_t now = (uint32_t)time(nullptr);
  if (now > 1600000000u)
    _nextTs = (now / PERIOD_S + 1) * PERIOD_S;
  if (LittleFS.exists(HIST_PATH)) {
    File f = LittleFS.open(HIST_PATH, FILE_READ);
    LOGI("历史存储就绪 记录=%u (%.0fKB)", (unsigned)(f ? f.size() / HIST_REC_BYTES : 0),
         f ? f.size() / 1024.0f : 0.0f);
    if (f) f.close();
  } else {
    LOGI("历史存储就绪 记录=0 (新库)");
  }
}

void HistStore::compactIfNeeded() {
  if (!LittleFS.exists(HIST_PATH)) return;
  File f = LittleFS.open(HIST_PATH, FILE_READ);
  if (!f) return;
  size_t sz = f.size();
  f.close();
  if (sz <= CAP_BYTES) return;
  size_t keep = sz / 2 / HIST_REC_BYTES * HIST_REC_BYTES;
  LittleFS.remove("/hist.tmp");
  File src = LittleFS.open(HIST_PATH, FILE_READ);
  File dst = LittleFS.open("/hist.tmp", FILE_WRITE);
  if (src && dst) {
    src.seek(sz - keep);
    uint8_t buf[512];
    while (keep) {
      size_t n = src.read(buf, keep < sizeof(buf) ? keep : sizeof(buf));
      if (!n) break;
      dst.write(buf, n);
      keep -= n;
    }
  }
  if (src) src.close();
  if (dst) dst.close();
  LittleFS.remove(HIST_PATH);
  LittleFS.rename("/hist.tmp", HIST_PATH);
  LOGW("历史数据已裁剪，保留最新 %.0fKB", sz / 2.0f / 1024.0f);
}

void HistStore::append(uint32_t ts) {
  HistRec r;
  histFillRec(r, sensors.snapshot(), ts);
  File f = LittleFS.open(HIST_PATH, FILE_APPEND);
  if (!f) return;
  f.write((uint8_t*)&r, HIST_REC_BYTES);
  f.close();
}

void HistStore::tick() {
  if (!_mounted) return;
  uint32_t now = (uint32_t)time(nullptr);
  if (now <= 1600000000u) return;
  if (!_nextTs) _nextTs = (now / PERIOD_S + 1) * PERIOD_S;
  if (now < _nextTs) return;
  _nextTs = (now / PERIOD_S + 1) * PERIOD_S;
  File f = LittleFS.open(HIST_PATH, FILE_READ);
  size_t sz = f ? f.size() : 0;
  if (f) f.close();
  if (sz + HIST_REC_BYTES > CAP_BYTES) {
    if (!_warned) { LOGW("历史存储已满，重启后裁剪"); _warned = true; }
    return;
  }
  append(now);
}

bool HistStore::query(uint32_t hours, String& out) {
  if (!_mounted) return false;
  if (!LittleFS.exists(HIST_PATH)) {
    out = "{\"ev\":\"hist\",\"hours\":" + String(hours) + ",\"n\":0}";
    return true;
  }
  File f = LittleFS.open(HIST_PATH, FILE_READ);
  if (!f) return false;
  size_t n = f.size() / HIST_REC_BYTES;
  LfsCtx ctx{&f};
  bool ok = histBuildJson(hours, n, lfsRead, &ctx, out);
  f.close();
  return ok;
}

}  // namespace iaq
