package com.iaqua.app.notify

import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import androidx.core.app.NotificationCompat
import androidx.core.app.NotificationManagerCompat
import com.iaqua.app.MainActivity
import com.iaqua.app.R
import dagger.hilt.android.qualifiers.ApplicationContext
import javax.inject.Inject
import javax.inject.Singleton

/** 本地通知（方案 §6.2 M1：App 在前台/后台时本地告警；二期切厂商推送通道） */
@Singleton
class Notifier @Inject constructor(
    @ApplicationContext private val ctx: Context,
) {
    fun createChannels() {
        val mgr = ctx.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        mgr.createNotificationChannel(
            NotificationChannel(
                CH_ALERTS,
                "水质与设备告警",
                NotificationManager.IMPORTANCE_HIGH,
            ).apply { description = "水温/pH/TDS/水位等阈值告警与操作建议" },
        )
        mgr.createNotificationChannel(
            NotificationChannel(
                CH_TASKS,
                "养护任务提醒",
                NotificationManager.IMPORTANCE_DEFAULT,
            ).apply { description = "换水/喂食/检测等到期提醒" },
        )
    }

    fun notifyAlert(title: String, text: String) {
        notify(CH_ALERTS, 1001, title, text)
    }

    fun notifyTask(title: String, text: String) {
        notify(CH_TASKS, 1002, title, text)
    }

    private fun notify(channelId: String, id: Int, title: String, text: String) {
        val mgr = NotificationManagerCompat.from(ctx)
        if (!mgr.areNotificationsEnabled()) return
        val intent = PendingIntent.getActivity(
            ctx, 0,
            Intent(ctx, MainActivity::class.java),
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT,
        )
        val n = NotificationCompat.Builder(ctx, channelId)
            .setSmallIcon(R.drawable.ic_stat_drop)
            .setContentTitle(title)
            .setContentText(text)
            .setAutoCancel(true)
            .setContentIntent(intent)
            .build()
        runCatching { mgr.notify(id, n) }
    }

    companion object {
        const val CH_ALERTS = "alerts"
        const val CH_TASKS = "tasks"
    }
}
