package com.iaqua.app.data.repo

import com.iaqua.app.data.db.TankDao
import com.iaqua.app.data.db.TankEntity
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.flatMapLatest
import kotlinx.coroutines.flow.flowOf
import javax.inject.Inject
import javax.inject.Singleton

/** 多缸管理（方案 §4.1）：缸档案 CRUD + 全局缸切换 */
@Singleton
class TankRepository @Inject constructor(
    private val dao: TankDao,
) {
    private val _activeTankId = MutableStateFlow<Long?>(null)

    /** 当前选中缸（M1 内存态；TODO: 持久化到 DataStore） */
    val activeTankId: StateFlow<Long?> = _activeTankId.asStateFlow()

    fun observeTanks(): Flow<List<TankEntity>> = dao.observeAll()

    @OptIn(ExperimentalCoroutinesApi::class)
    val activeTank: Flow<TankEntity?> =
        _activeTankId.flatMapLatest { id ->
            if (id == null) flowOf(null) else dao.observeById(id)
        }

    suspend fun addTank(tank: TankEntity): Long {
        val id = dao.upsert(tank)
        if (_activeTankId.value == null) _activeTankId.value = id
        return id
    }

    suspend fun saveTank(tank: TankEntity): Long = dao.upsert(tank)

    suspend fun archiveTank(id: Long) {
        dao.archive(id)
        if (_activeTankId.value == id) _activeTankId.value = null
    }

    fun setActive(id: Long) {
        _activeTankId.value = id
    }
}
