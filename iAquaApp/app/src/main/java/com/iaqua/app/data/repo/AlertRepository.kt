package com.iaqua.app.data.repo

import com.iaqua.app.data.db.AlertDao
import com.iaqua.app.data.db.AlertEventEntity
import com.iaqua.app.data.db.AlertRuleEntity
import kotlinx.coroutines.flow.Flow
import javax.inject.Inject
import javax.inject.Singleton

/** 提醒规则与事件（方案 §5）：规则 CRUD + 事件查询/恢复 */
@Singleton
class AlertRepository @Inject constructor(
    private val dao: AlertDao,
) {
    fun observeRules(tankId: Long): Flow<List<AlertRuleEntity>> = dao.observeRules(tankId)

    fun observeEvents(tankId: Long): Flow<List<AlertEventEntity>> = dao.observeEvents(tankId)

    suspend fun upsertRule(rule: AlertRuleEntity): Long = dao.upsertRule(rule)

    suspend fun insertEvent(event: AlertEventEntity): Long = dao.insertEvent(event)

    suspend fun resolve(id: Long, note: String = "") =
        dao.resolve(id, System.currentTimeMillis(), note)
}
