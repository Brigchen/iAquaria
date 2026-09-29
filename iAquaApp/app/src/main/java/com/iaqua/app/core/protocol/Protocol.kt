package com.iaqua.app.core.protocol

import kotlinx.serialization.Serializable
import kotlinx.serialization.json.Json

/**
 * iAqua 主板 WS 协议帧模型（与固件 WebService.cpp 对齐，所有帧带 "ev" 字段）。
 * tel=遥测 / cfg=配置 / hist=历史 / ack=确认
 */
@Serializable
data class WsFrame(
    val ev: String,
    // ---- tel 帧遥测字段（缺测为 null，前端按 null 断线处理）----
    val temp: Double? = null,
    val ph: Double? = null,
    val orp: Double? = null,
    val mtemp: Double? = null,
    val tds1: Double? = null,
    val tds2: Double? = null,
    val lux: Double? = null,
    val lvl: Double? = null,
    val rssi: Int? = null,
    val heap: Long? = null,
    // ---- cfg 帧 ----
    val rev: Int? = null,
)

/** 历史查询响应：{"ev":"hist","hours":24,"series":{"temp":[...],...}}，null 表示该点缺测 */
@Serializable
data class HistResponse(
    val ev: String,
    val hours: Int = 24,
    val series: Map<String, List<Double?>> = emptyMap(),
)

object IaquaProtocol {
    val json = Json { ignoreUnknownKeys = true; isLenient = true }

    const val HOURS_24H = 24
    const val HOURS_7D = 168
    const val HOURS_30D = 720
    const val HOURS_1Y = 8760

    /** 历史查询请求（hours: 24/168/720/8760） */
    fun histRequest(hours: Int): String = """{"cmd":"hist","hours":$hours}"""
}
