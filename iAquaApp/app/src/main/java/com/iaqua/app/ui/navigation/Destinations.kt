package com.iaqua.app.ui.navigation

/** 顶层四 Tab（对齐原型 01/03/05/06） */
enum class TopTab(val route: String, val label: String) {
    OVERVIEW("overview", "概览"),
    JOURNAL("journal", "日志"),
    PLAN("plan", "计划"),
    TANK("tank", "鱼缸"),
}

/** 二级路由（对齐原型 02/04/07/08/09–17） */
object Routes {
    const val TREND = "trend/{metric}"
    fun trend(metric: String) = "trend/$metric"

    const val NEW_RECORD = "newRecord"
    const val ADD_TANK = "addTank"
    const val RULES = "rules"
    const val ALERT_CENTER = "alertCenter"
    const val EXPORT = "export"
    const val CAMERA = "camera"
    const val SETTINGS = "settings"

    const val LIVESTOCK = "livestock/{kind}"
    fun livestock(kind: String) = "livestock/$kind"
}
