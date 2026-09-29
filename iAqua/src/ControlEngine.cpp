#include "ControlEngine.h"
#include "ConfigStore.h"
#include "SensorStore.h"
#include "Log.h"

namespace iaq {

void ControlEngine::setManual(uint8_t ch, bool on) {
  if (ch >= CH_COUNT || ch == CH_FEEDER) return;  // 喂食只走脉冲
  _manual[ch] = true;
  _manualVal[ch] = on;
  LOGI("%u 号通道切换手动 %s", ch, on ? "ON" : "OFF");
}

void ControlEngine::clearManual(uint8_t ch) {
  if (ch >= CH_COUNT) return;
  _manual[ch] = false;
  LOGI("%u 号通道恢复自动", ch);
}

bool ControlEngine::autoTarget(uint8_t ch) {
  Telemetry& t = sensors.live;
  bool cur = actuators.on(ch);

  switch (ch) {
    case CH_HEATER: {
      if (!t.temp.fresh || t.temp.ageS() > 60) {
        if (cur && !_loggedStale) LOGW("温度数据过期，加热棒强制关闭");
        return false;
      }
      float sp = config.getL<float>("ctrl.heater.sp_c", 25.0f);
      float hys = config.getL<float>("ctrl.heater.hyst_c", 0.5f);
      if (cur) {
        if (t.temp.v >= sp) return false;
      } else {
        if (t.temp.v <= sp - hys) return true;
      }
      return cur;
    }
    case CH_CO2: {
      if (config.getL<bool>("ctrl.co2.follow_light", true) && !actuators.on(CH_LIGHT))
        return false;
      if (!t.ph.fresh || t.ph.ageS() > 120) {
        if (cur && !_loggedStale) LOGW("pH 数据过期，CO2 强制关闭");
        return false;
      }
      float phOn = config.getL<float>("ctrl.co2.ph_on", 7.0f);
      float phOff = config.getL<float>("ctrl.co2.ph_off", 6.8f);
      if (cur) return t.ph.v > phOff;   // pH 掉到回差下限 → 关
      return t.ph.v >= phOn;            // pH 升到上限 → 开
    }
    case CH_LIGHT: {
      // 光强联动：lux ≤ lux_on 开灯；lux ≥ lux_off 关灯；回差区间内保持当前态
      String mode = config.getStrL("ctrl.light.mode", "lux");
      if (mode == "lux") {
        if (!t.lux.fresh || t.lux.ageS() > 60) {
          if (cur && !_loggedStale) LOGW("光照数据过期，水族灯保持当前状态");
          return cur;  // 数据失效时保持现状，避免误关
        }
        float luxOn = config.getL<float>("ctrl.light.lux_on", 100.0f);
        float luxOff = config.getL<float>("ctrl.light.lux_off", 300.0f);
        if (cur) return t.lux.v < luxOff;
        return t.lux.v <= luxOn;
      }
      // 定时模式（原逻辑，支持跨零点）
      if (!t.timeOk) return false;
      String onS = config.getStrL("ctrl.light.on", "08:00");
      String offS = config.getStrL("ctrl.light.off", "20:00");
      time_t nowT = time(nullptr);
      struct tm tmNow;
      localtime_r(&nowT, &tmNow);
      int curMin = tmNow.tm_hour * 60 + tmNow.tm_min;
      int onMin = atoi(onS.substring(0, 2).c_str()) * 60 + atoi(onS.substring(3, 5).c_str());
      int offMin = atoi(offS.substring(0, 2).c_str()) * 60 + atoi(offS.substring(3, 5).c_str());
      bool inWin = (onMin <= offMin) ? (curMin >= onMin && curMin < offMin)
                                     : (curMin >= onMin || curMin < offMin);  // 支持跨零点
      return inWin;
    }
    case CH_PUMP: {
      // 补水泵自动模式：水位低于 lvl_on 开泵补水，补到 lvl_off 以上关泵（回差控制）
      if (config.getL<bool>("ctrl.pump.auto_en", false)) {
        if (!t.level.fresh || t.level.ageS() > 60) {
          if (cur && !_loggedStale) LOGW("水位数据过期，补水泵保持当前状态");
          return cur;  // 数据失效保持现状，防止误开/误关
        }
        float lvlOn = config.getL<float>("ctrl.pump.lvl_on", 30.0f);
        float lvlOff = config.getL<float>("ctrl.pump.lvl_off", 60.0f);
        if (cur) return t.level.v < lvlOff;
        return t.level.v <= lvlOn;
      }
      // 非自动模式：默认关（防止缺水干烧/误启动）；需要常开时在配置中改 default_on
      return config.getL<bool>("ctrl.pump.default_on", false);
    }
    default:
      return cur;
  }
}

void ControlEngine::tick() {
  Telemetry& t = sensors.live;
  _loggedStale = false;

  for (uint8_t ch = 0; ch < CH_COUNT; ch++) {
    if (ch == CH_FEEDER) continue;  // 喂食由 feedPulse 管理
    bool target = _manual[ch] ? _manualVal[ch] : autoTarget(ch);

    // 连续运行超时保护（仅加热棒/CO2；灯与补水泵允许长时运行）
    if (!_manual[ch] && target && (ch == CH_HEATER || ch == CH_CO2)) {
      uint32_t limitMin = (ch == CH_HEATER)
        ? (uint32_t)config.getL<float>("ctrl.heater.max_on_min", 45.0f)
        : (uint32_t)config.getL<float>("ctrl.co2.max_on_min", 120.0f);
      if (limitMin && actuators.sinceS(ch) > limitMin * 60) {
        LOGW("%u 号通道连续运行超时，强制断开", ch);
        target = false;
      }
    }
    actuators.set(ch, target, _manual[ch] ? "manual" : "auto");
  }

  // 系统指标（发布前填好）
  t.uptimeS = millis() / 1000;
  t.freeHeap = ESP.getFreeHeap();
}

}  // namespace iaq
