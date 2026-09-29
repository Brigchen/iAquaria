package com.iaqua.app.di

import android.content.Context
import androidx.room.Room
import com.iaqua.app.data.db.AlertDao
import com.iaqua.app.data.db.AppDatabase
import com.iaqua.app.data.db.JournalDao
import com.iaqua.app.data.db.TaskDao
import com.iaqua.app.data.db.TankDao
import dagger.Module
import dagger.Provides
import dagger.hilt.InstallIn
import dagger.hilt.android.qualifiers.ApplicationContext
import dagger.hilt.components.SingletonComponent
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import okhttp3.OkHttpClient
import java.time.Duration
import javax.inject.Singleton

@Module
@InstallIn(SingletonComponent::class)
object AppModule {

    @Provides
    @Singleton
    fun okHttp(): OkHttpClient = OkHttpClient.Builder()
        .pingInterval(Duration.ofSeconds(20))
        .build()

    @Provides
    @Singleton
    fun database(@ApplicationContext ctx: Context): AppDatabase =
        Room.databaseBuilder(ctx, AppDatabase::class.java, "iaqua.db").build()

    @Provides fun tankDao(db: AppDatabase): TankDao = db.tankDao()
    @Provides fun journalDao(db: AppDatabase): JournalDao = db.journalDao()
    @Provides fun taskDao(db: AppDatabase): TaskDao = db.taskDao()
    @Provides fun alertDao(db: AppDatabase): AlertDao = db.alertDao()

    /** 应用级协程作用域（WS 收包、告警评估等常驻任务） */
    @Provides
    @Singleton
    fun appScope(): CoroutineScope = CoroutineScope(SupervisorJob() + Dispatchers.Default)
}
