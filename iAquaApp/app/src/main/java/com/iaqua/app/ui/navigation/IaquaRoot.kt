package com.iaqua.app.ui.navigation

import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.MenuBook
import androidx.compose.material.icons.filled.CalendarMonth
import androidx.compose.material.icons.filled.Home
import androidx.compose.material.icons.filled.Waves
import androidx.compose.material3.Icon
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.navigation.NavGraph.Companion.findStartDestination
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.currentBackStackEntryAsState
import androidx.navigation.compose.rememberNavController
import com.iaqua.app.ui.feature.addtank.AddTankScreen
import com.iaqua.app.ui.feature.alerts.AlertCenterScreen
import com.iaqua.app.ui.feature.journal.JournalScreen
import com.iaqua.app.ui.feature.journal.NewRecordScreen
import com.iaqua.app.ui.feature.misc.CameraScreen
import com.iaqua.app.ui.feature.misc.ExportScreen
import com.iaqua.app.ui.feature.misc.LivestockScreen
import com.iaqua.app.ui.feature.misc.SettingsScreen
import com.iaqua.app.ui.feature.overview.OverviewScreen
import com.iaqua.app.ui.feature.plan.PlanScreen
import com.iaqua.app.ui.feature.rules.RulesScreen
import com.iaqua.app.ui.feature.tank.TankScreen
import com.iaqua.app.ui.feature.trend.TrendScreen

/** 应用根：底部四 Tab + NavHost（对齐方案 §3 信息架构与 17 屏原型） */
@Composable
fun IaquaRoot() {
    val nav = rememberNavController()
    val backStack by nav.currentBackStackEntryAsState()
    val currentRoute = backStack?.destination?.route
    val isTopLevel = TopTab.entries.any { it.route == currentRoute }

    Scaffold(
        bottomBar = {
            if (isTopLevel) {
                NavigationBar {
                    TopTab.entries.forEach { tab ->
                        val selected = currentRoute == tab.route
                        NavigationBarItem(
                            selected = selected,
                            onClick = {
                                nav.navigate(tab.route) {
                                    popUpTo(nav.graph.findStartDestination().id) { saveState = true }
                                    launchSingleTop = true
                                    restoreState = true
                                }
                            },
                            icon = {
                                Icon(
                                    when (tab) {
                                        TopTab.OVERVIEW -> Icons.Filled.Home
                                        TopTab.JOURNAL -> Icons.AutoMirrored.Filled.MenuBook
                                        TopTab.PLAN -> Icons.Filled.CalendarMonth
                                        TopTab.TANK -> Icons.Filled.Waves
                                    },
                                    contentDescription = tab.label,
                                )
                            },
                            label = { Text(tab.label) },
                        )
                    }
                }
            }
        },
    ) { pad ->
        NavHost(
            navController = nav,
            startDestination = TopTab.OVERVIEW.route,
            modifier = Modifier.padding(pad),
        ) {
            // ---- 顶层 Tab ----
            composable(TopTab.OVERVIEW.route) {
                OverviewScreen(
                    onOpenTrend = { nav.navigate(Routes.trend(it)) },
                    onOpenAlerts = { nav.navigate(Routes.ALERT_CENTER) },
                    onOpenCamera = { nav.navigate(Routes.CAMERA) },
                    onAddTank = { nav.navigate(Routes.ADD_TANK) },
                )
            }
            composable(TopTab.JOURNAL.route) {
                JournalScreen(onNewRecord = { nav.navigate(Routes.NEW_RECORD) })
            }
            composable(TopTab.PLAN.route) { PlanScreen() }
            composable(TopTab.TANK.route) {
                TankScreen(
                    onOpenLivestock = { nav.navigate(Routes.livestock(it)) },
                    onOpenExport = { nav.navigate(Routes.EXPORT) },
                    onOpenRules = { nav.navigate(Routes.RULES) },
                    onOpenSettings = { nav.navigate(Routes.SETTINGS) },
                    onAddTank = { nav.navigate(Routes.ADD_TANK) },
                )
            }

            // ---- 二级页 ----
            composable(Routes.TREND) { entry ->
                TrendScreen(metric = entry.arguments?.getString("metric") ?: "temp", onBack = { nav.popBackStack() })
            }
            composable(Routes.NEW_RECORD) { NewRecordScreen(onBack = { nav.popBackStack() }) }
            composable(Routes.ADD_TANK) { AddTankScreen(onBack = { nav.popBackStack() }) }
            composable(Routes.RULES) { RulesScreen(onBack = { nav.popBackStack() }) }
            composable(Routes.ALERT_CENTER) { AlertCenterScreen(onBack = { nav.popBackStack() }) }
            composable(Routes.EXPORT) { ExportScreen(onBack = { nav.popBackStack() }) }
            composable(Routes.CAMERA) { CameraScreen(onBack = { nav.popBackStack() }) }
            composable(Routes.SETTINGS) { SettingsScreen(onBack = { nav.popBackStack() }) }
            composable(Routes.LIVESTOCK) { entry ->
                LivestockScreen(kind = entry.arguments?.getString("kind") ?: "生物", onBack = { nav.popBackStack() })
            }
        }
    }
}
