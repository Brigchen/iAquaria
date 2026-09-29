package com.iaqua.app.data.repo

import com.iaqua.app.data.db.TaskDao
import com.iaqua.app.data.db.TaskEntity
import kotlinx.coroutines.flow.Flow
import javax.inject.Inject
import javax.inject.Singleton

/** 周期任务（方案 §4.4）：完成/跳过自动顺延 nextDue */
@Singleton
class TaskRepository @Inject constructor(
    private val dao: TaskDao,
) {
    fun observeByTank(tankId: Long): Flow<List<TaskEntity>> = dao.observeByTank(tankId)

    suspend fun add(task: TaskEntity): Long = dao.upsert(task)

    /** 完成一次任务：nextDue 顺延一个周期（timesPerDay>1 时顺延 1 天内均分，骨架按 1 天处理） */
    suspend fun complete(task: TaskEntity) {
        val dayMs = 24 * 60 * 60 * 1000L
        dao.update(task.copy(nextDue = task.nextDue + task.periodDays * dayMs))
    }

    suspend fun skip(task: TaskEntity) = complete(task)

    suspend fun delete(id: Long) = dao.delete(id)
}
