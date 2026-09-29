package com.iaqua.app.data.db

import androidx.room.Database
import androidx.room.RoomDatabase

@Database(
    entities = [
        TankEntity::class,
        LivestockEntity::class,
        JournalEntity::class,
        TaskEntity::class,
        AlertRuleEntity::class,
        AlertEventEntity::class,
    ],
    version = 1,
    exportSchema = false,
)
abstract class AppDatabase : RoomDatabase() {
    abstract fun tankDao(): TankDao
    abstract fun journalDao(): JournalDao
    abstract fun taskDao(): TaskDao
    abstract fun alertDao(): AlertDao
}
