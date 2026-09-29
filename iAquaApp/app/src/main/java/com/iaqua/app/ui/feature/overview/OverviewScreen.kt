package com.iaqua.app.ui.feature.overview

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.ViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.iaqua.app.core.Metrics
import com.iaqua.app.core.theme.Line
import com.iaqua.app.core.theme.Muted
import com.iaqua.app.core.theme.Teal
import com.iaqua.app.core.theme.TealDark
import com.iaqua.app.core.theme.TealLight
import com.iaqua.app.core.ws.ConnState
import com.iaqua.app.data.repo.DeviceRepository
import com.iaqua.app.data.repo.TankRepository
import com.iaqua.app.data.repo.TelSnapshot
import com.iaqua.app.ui.components.AlertBanner
import com.iaqua.app.ui.components.EmptyHint
import com.iaqua.app.ui.components.MetricCard
import com.iaqua.app.ui.components.MetricState
import com.iaqua.app.ui.components.SectionCard
import dagger.hilt.android.lifecycle.HiltViewModel
import javax.inject.Inject

@HiltViewModel
class OverviewViewModel @Inject constructor(
    device: DeviceRepository,
    tankRepo: TankRepository,
) : ViewModel() {
    val telemetry = device.telemetry
    val connState = device.connState
    val activeTank = tankRepo.activeTank
}

/** 概览页（原型 01）：缸切换 / 告警横幅 / 摄像头 / 指标网格 / 今日任务 */
@Composable
fun OverviewScreen(
    onOpenTrend: (String) -> Unit,
    onOpenAlerts: () -> Unit,
    onOpenCamera: () -> Unit,
    onAddTank: () -> Unit,
    vm: OverviewViewModel = hiltViewModel(),
) {
    val tel by vm.telemetry.collectAsStateWithLifecycle()
    val conn by vm.connState.collectAsStateWithLifecycle()
    val tank by vm.activeTank.collectAsStateWithLifecycle(initialValue = null)

    Column(
        Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(horizontal = 14.dp),
    ) {
        Spacer(Modifier.height(6.dp))

        // ---- 顶部：缸切换器 + 连接状态 ----
        Row(
            Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Surface(
                onClick = onAddTank,
                shape = RoundedCornerShape(12.dp),
                color = MaterialTheme.colorScheme.surface,
                border = androidx.compose.foundation.BorderStroke(1.dp, Line),
            ) {
                Row(
                    Modifier.padding(horizontal = 12.dp, vertical = 8.dp),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Text(tank?.name ?: "选择鱼缸", fontWeight = FontWeight.SemiBold, fontSize = 14.sp)
                    Spacer(Modifier.width(4.dp))
                    Text("▾", color = Muted)
                }
            }
            Text(
                when (conn) {
                    is ConnState.Connected -> "在线"
                    is ConnState.Connecting -> "连接中…"
                    is ConnState.Failed -> "离线"
                    ConnState.Disconnected -> "未连接"
                },
                fontSize = 12.sp,
                color = if (conn is ConnState.Connected) Teal else Muted,
            )
        }

        Spacer(Modifier.height(10.dp))

        if (tank == null) {
            EmptyHint("还没有鱼缸，点上方「选择鱼缸 → 添加新缸」开始")
            return@Column
        }

        // ---- 告警横幅（骨架：接 AlertEvent 进行中条目后动态显示）----
        if (tel.temp != null && tel.temp!! > 28.0) {
            AlertBanner(
                title = "水温 ${tel.temp}℃ 接近上限",
                detail = "点击查看曲线 · 建议关注加热棒",
                onClick = { onOpenTrend("temp") },
            )
            Spacer(Modifier.height(10.dp))
        }

        // ---- 摄像头画面占位（M2 接 MJPEG 解析；固件已支持 3 客户端并发）----
        Surface(
            onClick = onOpenCamera,
            shape = RoundedCornerShape(18.dp),
            color = TealLight,
            modifier = Modifier.fillMaxWidth().height(150.dp),
        ) {
            Box(contentAlignment = Alignment.Center) {
                Text("实时画面（点击全屏）", color = TealDark, fontSize = 13.sp)
            }
        }

        Spacer(Modifier.height(10.dp))

        // ---- 指标网格（对齐 Web 端指标集；海水缸只显示单个盐度 = tds1，无滤后）----
        val wt = tank?.waterType
        val metrics = buildList {
            add(Triple("水温", tel.temp, "℃"))
            add(Triple("pH", tel.ph, ""))
            add(Triple("ORP", tel.orp, "mV"))
            add(Triple(Metrics.metricLabel("tds1", wt), tel.tds1, Metrics.metricUnit("tds1", wt)))
            if (!Metrics.isSalt(wt)) {
                add(Triple(Metrics.metricLabel("tds2", wt), tel.tds2, Metrics.metricUnit("tds2", wt)))
            }
            add(Triple("水位", tel.lvl, "%"))
            add(Triple("光照", tel.lux, "lx"))
            add(Triple("485水温", tel.mtemp, "℃"))
        }
        metrics.chunked(2).forEach { rowPairs ->
            Row(
                Modifier.fillMaxWidth().padding(bottom = 8.dp),
                horizontalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                rowPairs.forEach { (label, v, unit) ->
                    Box(Modifier.weight(1f)) {
                        MetricCard(
                            label = label,
                            value = v?.let { fmt(it) } ?: "--",
                            unit = unit,
                            state = if (v == null) MetricState.OFF else MetricState.OK,
                        )
                    }
                }
            }
        }

        // ---- 今日任务摘要 ----
        SectionCard(title = "今日任务", trailing = { Text("全部 ›", fontSize = 12.sp, color = TealDark) }) {
            Text("完成 / 待办任务将在此显示（接计划数据后生效）", fontSize = 12.sp, color = Muted)
        }
        Spacer(Modifier.height(90.dp))
    }
}

private fun fmt(v: Double): String = if (v >= 100) "%.0f".format(v) else "%.2f".format(v)
