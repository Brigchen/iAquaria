package com.iaqua.app.data.db

import androidx.room.Entity
import androidx.room.Index
import androidx.room.PrimaryKey

/** 缸档案（多缸管理，方案 §4.1） */
@Entity(tableName = "tank")
data class TankEntity(
    @PrimaryKey(autoGenerate = true) val id: Long = 0,
    val name: String,
    val location: String = "",
    val capacityL: Int = 0,
    val waterType: String = "淡水",      // 淡水 / 海水 / 草缸
    val createdDate: Long = 0L,          // 建缸日期 epoch 毫秒
    val deviceWs: String = "",           // ws://192.168.3.190/ws
    val camUrl: String = "",             // http://192.168.3.191
    val archived: Boolean = false,
)

/** 生物/水草/设备条目（kind: 生物|水草|设备） */
@Entity(
    tableName = "livestock",
    indices = [Index("tankId")],
)
data class LivestockEntity(
    @PrimaryKey(autoGenerate = true) val id: Long = 0,
    val tankId: Long,
    val kind: String,
    val name: String,
    val count: Int = 1,
    val since: Long = 0L,                // 入缸日期
    val note: String = "",
)

/** 养护日志（图文，source: 手动|自动） */
@Entity(
    tableName = "journal",
    indices = [Index("tankId"), Index("ts")],
)
data class JournalEntity(
    @PrimaryKey(autoGenerate = true) val id: Long = 0,
    val tankId: Long,
    val ts: Long,
    val type: String,                    // 水质检测 | 换水 | 喂食 | 维护 | 告警
    val title: String,
    val detail: String = "",
    val photos: String = "",             // 逗号分隔 uri
    val source: String = "手动",
)

/** 周期任务模板（方案 §4.4） */
@Entity(
    tableName = "task",
    indices = [Index("tankId")],
)
data class TaskEntity(
    @PrimaryKey(autoGenerate = true) val id: Long = 0,
    val tankId: Long,
    val type: String,                    // 喂食 | 换水 | 水质检测 | 设备保养
    val title: String,
    val periodDays: Int = 1,
    val timesPerDay: Int = 1,
    val nextDue: Long,                   // 下次到期 epoch 毫秒
    val paused: Boolean = false,
)

/** 告警/建议规则（方案 §5，全部字段可在 App 内自定义） */
@Entity(
    tableName = "alert_rule",
    indices = [Index("tankId")],
)
data class AlertRuleEntity(
    @PrimaryKey(autoGenerate = true) val id: Long = 0,
    val tankId: Long,
    val kind: String = "阈值",           // 阈值 | 建议
    val metric: String,                  // temp|ph|orp|tds1|tds2|lux|lvl
    /** range=固定区间 / baseline=基线±百分比（TDS 类） */
    val mode: String = "range",
    val minVal: Double? = null,
    val maxVal: Double? = null,
    val baseline: Double? = null,
    val pct: Double? = null,
    val holdN: Int = 3,                  // 持续确认次数
    val cooldownMin: Int = 30,           // 同规则冷却
    val silentFrom: String? = null,      // 免打扰开始 "23:00"
    val silentTo: String? = null,        // 免打扰结束 "07:00"（跨天自动处理）
    val silentScope: String = "",        // 静默范围，逗号分隔（光照,水位）
    val enabled: Boolean = true,
    val text: String = "",               // 建议文案
)

/** 告警事件（提醒中心，方案 §4.5） */
@Entity(
    tableName = "alert_event",
    indices = [Index("tankId"), Index("ts")],
)
data class AlertEventEntity(
    @PrimaryKey(autoGenerate = true) val id: Long = 0,
    val tankId: Long,
    val ruleId: Long,
    val ts: Long,
    val level: String = "warn",          // warn | info
    val snapshot: String = "",           // 触发时数值快照
    val resolved: Boolean = false,
    val resolvedTs: Long? = null,
    val note: String = "",               // 恢复原因 / 处理记录
)
