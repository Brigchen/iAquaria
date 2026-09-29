package com.iaqua.app.data.repo

import com.iaqua.app.data.db.JournalDao
import com.iaqua.app.data.db.JournalEntity
import kotlinx.coroutines.flow.Flow
import javax.inject.Inject
import javax.inject.Singleton

/** 养护日志（方案 §4.3）：手动图文记录 + 告警/任务完成自动写入 */
@Singleton
class JournalRepository @Inject constructor(
    private val dao: JournalDao,
) {
    fun observeByTank(tankId: Long): Flow<List<JournalEntity>> = dao.observeByTank(tankId)

    suspend fun add(entry: JournalEntity): Long = dao.upsert(entry)

    suspend fun delete(id: Long) = dao.delete(id)

    /** 告警恢复/任务完成等自动记录入口 */
    suspend fun addAuto(tankId: Long, type: String, title: String, detail: String) {
        dao.upsert(
            JournalEntity(
                tankId = tankId,
                ts = System.currentTimeMillis(),
                type = type,
                title = title,
                detail = detail,
                source = "自动",
            ),
        )
    }
}
