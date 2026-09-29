package com.iaqua.app.data.repo

import com.iaqua.app.data.db.LivestockDao
import com.iaqua.app.data.db.LivestockEntity
import kotlinx.coroutines.flow.Flow
import javax.inject.Inject
import javax.inject.Singleton

/** 生物/水草/设备清单（方案 §4.1，kind 区分） */
@Singleton
class LivestockRepository @Inject constructor(
    private val dao: LivestockDao,
) {
    fun observeByTank(tankId: Long, kind: String): Flow<List<LivestockEntity>> =
        dao.observeByTank(tankId, kind)

    suspend fun countByKind(tankId: Long, kind: String): Int = dao.countByKind(tankId, kind)

    suspend fun add(entry: LivestockEntity): Long = dao.upsert(entry)

    suspend fun delete(id: Long) = dao.delete(id)
}
