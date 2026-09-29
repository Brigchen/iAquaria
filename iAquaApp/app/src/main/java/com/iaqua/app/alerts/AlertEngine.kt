package com.iaqua.app.alerts

import com.iaqua.app.data.db.AlertEventEntity
import com.iaqua.app.data.db.AlertRuleEntity
import javax.inject.Inject
import javax.inject.Singleton

/**
 * 阈值告警引擎（方案 §5.1，M1 本地评估）：
 * 越界持续 holdN 次确认 → 触发；同规则 cooldownMin 冷却防轰炸。
 * 免打扰时段与静默范围、恢复判定、建议层趋势规则为 M1 后续迭代。
 */
@Singleton
class AlertEngine @Inject constructor() {

    private val counters = HashMap<Long, Int>()   // ruleId -> 连续越界计数
    private val lastFired = HashMap<Long, Long>() // ruleId -> 上次触发时间

    /** 逐帧评估单条规则；命中返回待入库事件，否则 null */
    fun evaluate(rule: AlertRuleEntity, value: Double, now: Long): AlertEventEntity? {
        if (!rule.enabled) return null

        val outOfRange = when (rule.mode) {
            MODE_RANGE -> {
                val min = rule.minVal ?: return null
                val max = rule.maxVal ?: return null
                value < min || value > max
            }
            MODE_BASELINE -> {
                val base = rule.baseline ?: return null
                val pct = (rule.pct ?: 30.0) / 100.0
                value < base * (1 - pct) || value > base * (1 + pct)
            }
            else -> return null
        }

        if (!outOfRange) {
            counters[rule.id] = 0
            return null
        }

        val n = (counters[rule.id] ?: 0) + 1
        counters[rule.id] = n
        if (n < rule.holdN) return null

        val last = lastFired[rule.id] ?: 0L
        if (now - last < rule.cooldownMin * 60_000L) return null
        lastFired[rule.id] = now

        return AlertEventEntity(
            tankId = rule.tankId,
            ruleId = rule.id,
            ts = now,
            level = "warn",
            snapshot = value.toString(),
        )
    }

    companion object {
        const val MODE_RANGE = "range"
        const val MODE_BASELINE = "baseline"
    }
}
