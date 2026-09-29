package com.iaqua.app.data.db

import androidx.room.Dao
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.Query
import androidx.room.Update
import kotlinx.coroutines.flow.Flow

@Dao
interface TankDao {
    @Query("SELECT * FROM tank WHERE archived = 0 ORDER BY id")
    fun observeAll(): Flow<List<TankEntity>>

    @Query("SELECT * FROM tank WHERE id = :id")
    fun observeById(id: Long): Flow<TankEntity?>

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsert(tank: TankEntity): Long

    @Query("UPDATE tank SET archived = 1 WHERE id = :id")
    suspend fun archive(id: Long)
}

@Dao
interface JournalDao {
    @Query("SELECT * FROM journal WHERE tankId = :tankId ORDER BY ts DESC")
    fun observeByTank(tankId: Long): Flow<List<JournalEntity>>

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsert(entry: JournalEntity): Long

    @Query("DELETE FROM journal WHERE id = :id")
    suspend fun delete(id: Long)
}

@Dao
interface LivestockDao {
    @Query("SELECT * FROM livestock WHERE tankId = :tankId AND kind = :kind ORDER BY id")
    fun observeByTank(tankId: Long, kind: String): Flow<List<LivestockEntity>>

    @Query("SELECT COUNT(*) FROM livestock WHERE tankId = :tankId AND kind = :kind")
    suspend fun countByKind(tankId: Long, kind: String): Int

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsert(entry: LivestockEntity): Long

    @Query("DELETE FROM livestock WHERE id = :id")
    suspend fun delete(id: Long)
}

@Dao
interface TaskDao {
    @Query("SELECT * FROM task WHERE tankId = :tankId AND paused = 0 ORDER BY nextDue")
    fun observeByTank(tankId: Long): Flow<List<TaskEntity>>

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsert(task: TaskEntity): Long

    @Update
    suspend fun update(task: TaskEntity)

    @Query("DELETE FROM task WHERE id = :id")
    suspend fun delete(id: Long)
}

@Dao
interface AlertDao {
    @Query("SELECT * FROM alert_rule WHERE tankId = :tankId ORDER BY kind, metric")
    fun observeRules(tankId: Long): Flow<List<AlertRuleEntity>>

    @Query("SELECT * FROM alert_event WHERE tankId = :tankId ORDER BY ts DESC LIMIT 100")
    fun observeEvents(tankId: Long): Flow<List<AlertEventEntity>>

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsertRule(rule: AlertRuleEntity): Long

    @Insert
    suspend fun insertEvent(event: AlertEventEntity): Long

    @Query("UPDATE alert_event SET resolved = 1, resolvedTs = :ts, note = :note WHERE id = :id")
    suspend fun resolve(id: Long, ts: Long, note: String)

    @Query("SELECT * FROM alert_rule WHERE tankId = :tankId AND enabled = 1")
    suspend fun enabledRules(tankId: Long): List<AlertRuleEntity>
}
