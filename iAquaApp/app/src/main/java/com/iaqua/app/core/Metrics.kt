package com.iaqua.app.core

/**
 * 指标显示映射（水型驱动，方案 §4.2）：
 * - 淡水/草缸：tds1/tds2 显示为 TDS(滤前)/TDS(滤后)，单位 ppm
 * - 海水：485 滤前通道换装盐度探头，协议键仍为 tds1，显示为单个"盐度"，单位 ‰；
 *   海水缸不显示 tds2（无滤后盐度），见 visibleMetricKeys()
 * 其余指标各水型一致。
 */
object Metrics {

    const val WATER_FRESH = "淡水"
    const val WATER_SALT = "海水"
    const val WATER_PLANTED = "草缸"

    fun isSalt(waterType: String?): Boolean = waterType == WATER_SALT

    fun metricLabel(metric: String, waterType: String? = WATER_FRESH): String = when {
        metric == "tds1" -> if (isSalt(waterType)) "盐度" else "TDS(滤前)"
        metric == "tds2" -> if (isSalt(waterType)) "盐度(滤后)" else "TDS(滤后)"
        metric == "temp" -> "水温"
        metric == "ph" -> "pH"
        metric == "orp" -> "ORP"
        metric == "mtemp" -> "485水温"
        metric == "lux" -> "光照"
        metric == "lvl" -> "水位"
        else -> metric
    }

    fun metricUnit(metric: String, waterType: String? = WATER_FRESH): String = when (metric) {
        "temp", "mtemp" -> "℃"
        "orp" -> "mV"
        "tds1", "tds2" -> if (isSalt(waterType)) "‰" else "ppm"
        "lux" -> "lx"
        "lvl" -> "%"
        else -> ""
    }

    /** 全量协议指标键 */
    val metricKeys = listOf("temp", "ph", "orp", "tds1", "tds2", "mtemp", "lux", "lvl")

    /** 当前水型下可显示/可配置的指标（海水缸只有单个盐度 = tds1，不含 tds2） */
    fun visibleMetricKeys(waterType: String?): List<String> =
        if (isSalt(waterType)) metricKeys.filter { it != "tds2" } else metricKeys

    /** 添加缸时的传感器配置提示 */
    fun sensorHint(waterType: String): String = when (waterType) {
        WATER_SALT -> "海水缸：485 滤前通道配置盐度探头，App 内显示为单个\"盐度\"，单位 ‰"
        else -> "淡水/草缸：485 双通道配置 TDS 探头（滤前/滤后），单位 ppm"
    }
}
