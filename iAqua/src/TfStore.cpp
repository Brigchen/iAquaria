#include "TfStore.h"
#include <SD.h>
#include <SPI.h>
#include <time.h>
#include "Config.h"
#include "ConfigStore.h"
#include "SensorStore.h"
#include "Actuators.h"
#include "HistStore.h"
#include "Log.h"

namespace iaq {

TfStore tf;

namespace {
struct LogItem {
  char level;
  char text[96];
};

struct DayBin {
  char path[40];
  size_t nrec;
};

uint32_t localDayStart(int y, int mo, int d) {
  struct tm t = {};
  t.tm_year = y - 1900;
  t.tm_mon = mo - 1;
  t.tm_mday = d;
  t.tm_isdst = -1;
  time_t e = mktime(&t);
  return e > 0 ? (uint32_t)e : 0;
}

bool parseDayName(const char* name, int* y, int* mo, int* d) {
  const char* base = strrchr(name, '/');
  base = base ? base + 1 : name;
  return sscanf(base, "%d-%d-%d", y, mo, d) == 3 && *y >= 2020 && *mo >= 1 && *mo <= 12 && *d >= 1 && *d <= 31;
}

void csvVal(String& line, float v, bool fresh, uint8_t dec) {
  line += ',';
  if (!fresh || isnan(v)) return;
  char buf[16];
  snprintf(buf, sizeof(buf), "%.*f", dec, v);
  line += buf;
}
}  // namespace

void TfStore::begin() {
  _logQ = xQueueCreate(48, sizeof(LogItem));
  _nextMount = millis() + 500;  // 任务内挂载，避免 setup/loop 被 SD.begin 堵住 2s WDT
  xTaskCreatePinnedToCore(taskFn, "tf", 16384, this, 1, nullptr, 1);
}

void TfStore::taskFn(void* self) { ((TfStore*)self)->loop(); }

void TfStore::pushLog(char level, const char* text) {
  if (!_logQ) return;
  LogItem it;
  it.level = level;
  strncpy(it.text, text ? text : "", sizeof(it.text) - 1);
  it.text[sizeof(it.text) - 1] = 0;
  xQueueSend(_logQ, &it, 0);
}

bool TfStore::requestHist(uint32_t hours) {
  if (!_mounted || _histSt != 0) return false;
  _histHours = hours;
  _histSt = 1;
  return true;
}

int TfStore::takeHist(String& out) {
  uint8_t st = _histSt;
  if (st == 1 || st == 2) return 0;
  if (st == 0) return -1;
  out = _histJson;
  _histJson = "";
  bool ok = (st == 3);
  _histSt = 0;
  if (!ok) return -1;
  return (out.indexOf("\"n\":0}") >= 0 || out.indexOf("\"n\":0,") >= 0) ? 2 : 1;
}

void TfStore::loop() {
  for (;;) {
    vTaskDelay(pdMS_TO_TICKS(200));
    uint32_t now = millis();

    if (!_mounted) {
      if ((int32_t)(now - _nextMount) >= 0) {
        if (!tryMount()) _nextMount = now + 10000;
      }
      continue;
    }

    drainLogs();

    if (_histSt == 1) {
      _histSt = 2;
      runHist();
    }

    uint32_t periodMs = config.getL<int>("tf.period_s", TF_PERIOD_S_DEFAULT) * 1000u;
    if (periodMs < 5000) periodMs = 5000;
    if (periodMs > 3600000u) periodMs = 3600000u;  // 上限 1 小时（默认 300s）
    if ((int32_t)(now - _nextTel) >= 0) {
      _nextTel = now + periodMs;
      sampleTel();
    }

    if ((int32_t)(now - _nextCheck) >= 0) {
      _nextCheck = now + 5000;
      if (SD.cardType() == CARD_NONE) {
        LOGW("TF 卡已拔出");
        unmount();
      }
    }
  }
}

bool TfStore::ensureDirs() {
  if (!SD.exists("/iaqua") && !SD.mkdir("/iaqua")) return false;
  if (!SD.exists("/iaqua/tel") && !SD.mkdir("/iaqua/tel")) return false;
  if (!SD.exists("/iaqua/evt") && !SD.mkdir("/iaqua/evt")) return false;
  return true;
}

bool TfStore::tryMount() {
  pinMode(PIN_TF_CS, OUTPUT);
  digitalWrite(PIN_TF_CS, HIGH);
  pinMode(PIN_TF_MISO, INPUT);  // GPIO34 无内部上拉，模块侧建议 10k→3.3V
  delay(50);

  static const uint32_t kHz[] = {400000, 1000000, 4000000};
  bool ok = false;
  uint32_t used = 0;
  for (uint32_t hz : kHz) {
    SPI.end();
    SD.end();
    SPI.begin(PIN_TF_SCK, PIN_TF_MISO, PIN_TF_MOSI, PIN_TF_CS);
    digitalWrite(PIN_TF_CS, HIGH);
    delay(20);
    if (SD.begin(PIN_TF_CS, SPI, hz)) {
      ok = true;
      used = hz;
      break;
    }
  }
  if (!ok) {
    LOGW("TF 卡未就绪 CS=%u CLK=%u MOSI=%u MISO=%u（查线；MISO 加10k上拉；模块可试5V）",
         PIN_TF_CS, PIN_TF_SCK, PIN_TF_MOSI, PIN_TF_MISO);
    return false;
  }

  uint8_t t = SD.cardType();
  if (t == CARD_NONE) {
    unmount();
    LOGW("TF 卡槽无卡");
    return false;
  }
  if (t == CARD_MMC) strncpy(_cardType, "MMC", sizeof(_cardType));
  else if (t == CARD_SD) strncpy(_cardType, "SDSC", sizeof(_cardType));
  else if (t == CARD_SDHC) strncpy(_cardType, "SDHC", sizeof(_cardType));
  else strncpy(_cardType, "SD", sizeof(_cardType));
  _sizeMb = SD.cardSize() / (1024ull * 1024ull);
  _spiHz = used;
  _cs = PIN_TF_CS;
  if (!ensureDirs()) {
    LOGW("TF 卡目录创建失败");
    unmount();
    return false;
  }
  _mounted = true;
  LOGI("TF 卡就绪 type=%s size=%lluMB spi=%uHz cs=GPIO%u", _cardType,
       (unsigned long long)_sizeMb, (unsigned)_spiHz, (unsigned)_cs);
  return true;
}

void TfStore::unmount() {
  _mounted = false;
  SD.end();
}

bool TfStore::dayPaths(char* csv, char* bin, char* evt, size_t cap) {
  time_t now = time(nullptr);
  if (now < 1700000000) return false;
  struct tm tmNow;
  localtime_r(&now, &tmNow);
  snprintf(csv, cap, "/iaqua/tel/%04d-%02d-%02d.csv", tmNow.tm_year + 1900, tmNow.tm_mon + 1, tmNow.tm_mday);
  snprintf(bin, cap, "/iaqua/tel/%04d-%02d-%02d.bin", tmNow.tm_year + 1900, tmNow.tm_mon + 1, tmNow.tm_mday);
  snprintf(evt, cap, "/iaqua/evt/%04d-%02d-%02d.log", tmNow.tm_year + 1900, tmNow.tm_mon + 1, tmNow.tm_mday);
  return true;
}

void TfStore::drainLogs() {
  if (!_logQ) return;
  LogItem it;
  char csv[48], bin[48], evt[48];
  bool dated = dayPaths(csv, bin, evt, sizeof(evt));
  if (!dated) strncpy(evt, "/iaqua/evt/boot.log", sizeof(evt));
  File f;
  bool opened = false;
  while (xQueueReceive(_logQ, &it, 0) == pdTRUE) {
    if (!opened) {
      f = SD.open(evt, FILE_APPEND);
      if (!f) {
        unmount();
        return;
      }
      opened = true;
    }
    char line[160];
    time_t now = time(nullptr);
    if (now > 1700000000) {
      struct tm tmNow;
      localtime_r(&now, &tmNow);
      snprintf(line, sizeof(line), "%04d-%02d-%02dT%02d:%02d:%02d [%c] %s\n",
               tmNow.tm_year + 1900, tmNow.tm_mon + 1, tmNow.tm_mday,
               tmNow.tm_hour, tmNow.tm_min, tmNow.tm_sec, it.level, it.text);
    } else {
      snprintf(line, sizeof(line), "up=%lu [%c] %s\n", (unsigned long)millis(), it.level, it.text);
    }
    size_t n = strlen(line);
    if (f.write((uint8_t*)line, n) != n) {
      f.close();
      unmount();
      return;
    }
  }
  if (opened) f.close();
}

void TfStore::sampleTel() {
  Telemetry s = sensors.snapshot();
  if (!s.timeOk) return;
  uint32_t ts = (uint32_t)time(nullptr);
  if (ts < 1700000000u) return;

  char csv[48], bin[48], evt[48];
  if (!dayPaths(csv, bin, evt, sizeof(csv))) return;

  HistRec rec;
  histFillRec(rec, s, ts);
  File fb = SD.open(bin, FILE_APPEND);
  if (!fb) { unmount(); return; }
  size_t nw = fb.write((uint8_t*)&rec, HIST_REC_BYTES);
  fb.close();
  if (nw != HIST_REC_BYTES) { unmount(); return; }

  bool needHdr = !SD.exists(csv);
  File fc = SD.open(csv, FILE_APPEND);
  if (!fc) { unmount(); return; }
  if (needHdr) {
    const char* hdr = "ts,temp,ph,orp,tds1,tds2,lux,lvl,rssi,heap,up,co2,feed,light,heater,pump\n";
    fc.write((const uint8_t*)hdr, strlen(hdr));
  }
  String line;
  line.reserve(128);
  line += ts;
  csvVal(line, s.temp.v, s.temp.fresh, 2);
  csvVal(line, s.ph.v, s.ph.fresh, 2);
  csvVal(line, s.orp.v, s.orp.fresh, 0);
  csvVal(line, s.tds1.v, s.tds1.fresh, 0);
  csvVal(line, s.tds2.v, s.tds2.fresh, 0);
  csvVal(line, s.lux.v, s.lux.fresh, 0);
  csvVal(line, s.level.v, s.level.fresh, 1);
  line += ',';
  line += s.rssi;
  line += ',';
  line += s.freeHeap;
  line += ',';
  line += s.uptimeS;
  for (uint8_t ch = 0; ch < CH_COUNT; ch++) {
    line += ',';
    line += actuators.on(ch) ? '1' : '0';
  }
  line += '\n';
  fc.write((const uint8_t*)line.c_str(), line.length());
  fc.close();
}

void TfStore::runHist() {
  String s;
  bool ok = queryHist(_histHours, s);
  _histJson = ok ? s : String();
  _histSt = ok ? 3 : 4;
}

bool TfStore::queryHist(uint32_t hours, String& out) {
  time_t nowT = time(nullptr);
  if (nowT < 1700000000) {
    out = "{\"ev\":\"hist\",\"hours\":" + String(hours) + ",\"n\":0}";
    return true;
  }
  uint32_t now = (uint32_t)nowT;
  uint32_t from = now > hours * 3600u ? now - hours * 3600u : 0;

  // 动态收集范围内日期文件：1 年查询可达 365+ 个，原固定 10 个会截断长周期
  DayBin* files = nullptr;
  size_t nFiles = 0, capFiles = 0;
  bool oom = false;
  File dir = SD.open("/iaqua/tel");
  if (!dir || !dir.isDirectory()) {
    if (dir) dir.close();
    out = "{\"ev\":\"hist\",\"hours\":" + String(hours) + ",\"n\":0}";
    return true;
  }
  File ent = dir.openNextFile();
  while (ent) {
    const char* nm = ent.name();
    size_t nrec = ent.size() / HIST_REC_BYTES;
    bool isBin = nm && strstr(nm, ".bin");
    int y = 0, mo = 0, d = 0;
    if (isBin && nrec && parseDayName(nm, &y, &mo, &d)) {
      uint32_t ds = localDayStart(y, mo, d);
      uint32_t de = ds + 86400;
      if (ds && de >= from && ds <= now) {
        if (nFiles == capFiles) {
          size_t ncap = capFiles ? capFiles * 2 : 16;
          DayBin* nf = (DayBin*)realloc(files, ncap * sizeof(DayBin));
          if (nf) { files = nf; capFiles = ncap; }
          else oom = true;  // 内存不足：用已收集部分继续（优雅降级）
        }
        if (!oom) {
          if (nm[0] == '/') strncpy(files[nFiles].path, nm, sizeof(files[nFiles].path) - 1);
          else snprintf(files[nFiles].path, sizeof(files[nFiles].path), "/iaqua/tel/%s", nm);
          files[nFiles].path[sizeof(files[nFiles].path) - 1] = 0;
          files[nFiles].nrec = nrec;
          nFiles++;
        }
      }
    }
    ent.close();
    ent = dir.openNextFile();
  }
  dir.close();

  // 按文件名排序（YYYY-MM-DD 字典序 = 时间序）
  for (size_t i = 0; i < nFiles; i++) {
    for (size_t j = i + 1; j < nFiles; j++) {
      if (strcmp(files[j].path, files[i].path) < 0) {
        DayBin tmp = files[i];
        files[i] = files[j];
        files[j] = tmp;
      }
    }
  }

  size_t total = 0;
  for (size_t i = 0; i < nFiles; i++) total += files[i].nrec;
  if (!total) {
    free(files);
    out = "{\"ev\":\"hist\",\"hours\":" + String(hours) + ",\"n\":0}";
    return true;
  }

  struct Ctx {
    DayBin* files;
    size_t nFiles;
    File f;
    int openIdx;
  } ctx;
  ctx.files = files;
  ctx.nFiles = nFiles;
  ctx.openIdx = -1;

  auto readIdx = [](void* p, size_t i, HistRec* r) -> bool {
    Ctx* c = (Ctx*)p;
    size_t acc = 0;
    int fi = -1;
    size_t local = 0;
    for (size_t k = 0; k < c->nFiles; k++) {
      if (i < acc + c->files[k].nrec) {
        fi = (int)k;
        local = i - acc;
        break;
      }
      acc += c->files[k].nrec;
    }
    if (fi < 0) return false;
    if (c->openIdx != fi) {
      if (c->openIdx >= 0 && c->f) c->f.close();
      c->f = SD.open(c->files[fi].path, FILE_READ);
      c->openIdx = c->f ? fi : -1;
      if (!c->f) return false;
    }
    if (!c->f.seek(local * HIST_REC_BYTES)) return false;
    return c->f.read((uint8_t*)r, HIST_REC_BYTES) == HIST_REC_BYTES;
  };

  // 稀疏单遍构建：只读 ~400 个采样点。原 histBuildJson 全量 9 遍扫描
  // 在 SD 卡上 7 天查询（6 万条）耗时 60s+ 直接超时
  bool ok = histBuildJsonSparse(hours, total, +readIdx, &ctx, out);
  if (ctx.openIdx >= 0 && ctx.f) ctx.f.close();
  free(files);
  if (ok) {
    // 标记数据来源，前端可忽略未知字段
    out.replace("\"src\":\"lfs\"", "\"src\":\"tf\"");
    if (out.indexOf("\"src\":") < 0) {
      out.replace("\"hours\":", String("\"src\":\"tf\",\"hours\":"));
    }
  }
  return ok;
}

}  // namespace iaq
