package com.iaqua.app

import android.app.Application
import com.iaqua.app.notify.Notifier
import dagger.hilt.android.HiltAndroidApp
import javax.inject.Inject

@HiltAndroidApp
class IaquaApplication : Application() {

    @Inject lateinit var notifier: Notifier

    override fun onCreate() {
        super.onCreate()
        notifier.createChannels()
    }
}
