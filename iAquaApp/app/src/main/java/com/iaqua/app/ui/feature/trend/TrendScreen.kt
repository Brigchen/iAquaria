package com.iaqua.app.ui.feature.trend

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.SegmentedButton
import androidx.compose.material3.SegmentedButtonDefaults
import androidx.compose.material3.SingleChoiceSegmentedButtonRow
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.SavedStateHandle
import androidx.lifecycle.ViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewModelScope
import com.iaqua.app.core.Metrics
import com.iaqua.app.core.protocol.HistResponse
import com.iaqua.app.core.protocol.IaquaProtocol
import com.iaqua.app.core.theme.Muted
import com.iaqua.app.core.theme.Teal
import com.iaqua.app.data.repo.DeviceRepository
import com.iaqua.app.data.repo.TankRepository
import com.iaqua.app.ui.components.ScreenHeader
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject

@HiltViewModel
class TrendViewModel @Inject constructor(
    savedState: SavedStateHandle,
    private val device: DeviceRepository,
    tankRepo: TankRepository,
) : ViewModel() {
    /** 指标键：temp/ph/orp/tds1/tds2/lux/lvl */
    val metric: String = savedState.get<String>("metric") ?: "temp"

    val activeTank = tankRepo.activeTank

    private val _hist = MutableStateFlow<HistResponse?>(null)
    val hist: StateFlow<HistResponse?> = _hist

    fun load(hours: Int) = viewModelScope.launch {
        _hist.value = device.fetchHist(hours)
    }
}

/** 数据详情（原型 02）：时段切换 + 单指标曲线（Web 端 hist 接口，≤400 点降采样由固件保证） */
@Composable
fun TrendScreen(
    metric: String,
    onBack: () -> Unit,
    vm: TrendViewModel = hiltViewModel(),
) {
    val hist by vm.hist.collectAsStateWithLifecycle()
    val tank by vm.activeTank.collectAsStateWithLifecycle(initialValue = null)

    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(horizontal = 14.dp)) {
        Spacer(Modifier.height(6.dp))
        ScreenHeader(Metrics.metricLabel(metric, tank?.waterType) + " · 历史趋势", onBack)

        SingleChoiceSegmentedButtonRow(Modifier.fillMaxWidth()) {
            listOf(
                IaquaProtocol.HOURS_24H to "24h",
                IaquaProtocol.HOURS_7D to "7 天",
                IaquaProtocol.HOURS_30D to "30 天",
                IaquaProtocol.HOURS_1Y to "1 年",
            ).forEachIndexed { i, (hours, label) ->
                SegmentedButton(
                    selected = hours == hist?.hours || (hist == null && hours == IaquaProtocol.HOURS_24H),
                    onClick = { vm.load(hours) },
                    shape = SegmentedButtonDefaults.itemShape(i, 4),
                ) { Text(label, fontSize = 12.sp) }
            }
        }
        Spacer(Modifier.height(10.dp))

        val series = hist?.series?.get(metric)
        if (series.isNullOrEmpty()) {
            Text("暂无数据（未连接或该时段无记录）", fontSize = 13.sp, color = Muted)
        } else {
            SimpleLineChart(series, Modifier.fillMaxWidth().height(180.dp))
        }
        Spacer(Modifier.height(20.dp))
    }
}

fun metricLabel(metric: String): String = Metrics.metricLabel(metric)

/** 极简折线图（M1 占位实现；后续可换 Vico 或自绘增强：阈值线/归一化多曲线） */
@Composable
fun SimpleLineChart(values: List<Double?>, modifier: Modifier = Modifier) {
    Canvas(modifier) {
        val pts = values.filterNotNull()
        if (pts.size < 2) return@Canvas
        val min = pts.min()
        val max = pts.max()
        val range = (max - min).takeIf { it > 1e-9 } ?: 1.0
        val w = size.width
        val h = size.height
        val stepX = w / (values.size - 1).coerceAtLeast(1)

        val path = Path()
        var started = false
        values.forEachIndexed { i, v ->
            val x = i * stepX
            if (v == null) {
                started = false // 缺测断线（与 Web 端一致）
                return@forEachIndexed
            }
            val y = (h - ((v - min) / range * h * 0.9 + h * 0.05)).toFloat()
            if (started) path.lineTo(x.toFloat(), y) else {
                path.moveTo(x.toFloat(), y); started = true
            }
        }
        drawPath(path, color = Teal, style = Stroke(width = 4f))
        // 起止参考点
        drawCircle(Teal, radius = 6f, center = Offset(w, h / 2))
    }
}
