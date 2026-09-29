package com.iaqua.app.ui.feature.rules

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Surface
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.ViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewModelScope
import com.iaqua.app.core.theme.Muted
import com.iaqua.app.data.db.AlertRuleEntity
import com.iaqua.app.data.repo.AlertRepository
import com.iaqua.app.data.repo.TankRepository
import com.iaqua.app.ui.components.EmptyHint
import com.iaqua.app.ui.components.ScreenHeader
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.flatMapLatest
import kotlinx.coroutines.flow.flowOf
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch
import javax.inject.Inject

@OptIn(ExperimentalCoroutinesApi::class, ExperimentalLayoutApi::class)
@HiltViewModel
class RulesViewModel @Inject constructor(
    private val alertRepo: AlertRepository,
    private val tankRepo: TankRepository,
) : ViewModel() {
    val rules = tankRepo.activeTankId
        .flatMapLatest { id ->
            if (id == null) flowOf(emptyList()) else alertRepo.observeRules(id)
        }
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), emptyList())

    val activeTank = tankRepo.activeTank

    fun save(rule: AlertRuleEntity) = viewModelScope.launch { alertRepo.upsertRule(rule) }

    suspend fun currentTankId(): Long? = tankRepo.activeTankId.first()
}

/**
 * 提醒规则（原型 08 + 16/17 编辑弹层）：
 * 阈值区间/持续次数/冷却时间/免打扰时段与范围全部可自定义。
 */
@Composable
fun RulesScreen(
    onBack: () -> Unit,
    vm: RulesViewModel = hiltViewModel(),
) {
    val rules by vm.rules.collectAsStateWithLifecycle()
    val tank by vm.activeTank.collectAsStateWithLifecycle(initialValue = null)
    val wt = tank?.waterType
    var editing by remember { mutableStateOf<AlertRuleEntity?>(null) }
    val scope = rememberCoroutineScope()

    Column(Modifier.fillMaxSize().padding(horizontal = 14.dp)) {
        Spacer(Modifier.height(6.dp))
        ScreenHeader("提醒规则", onBack, trailing = {
            TextButton(onClick = {
                scope.launch {
                    val id = vm.currentTankId()
                    if (id != null) editing = AlertRuleEntity(tankId = id, metric = "temp")
                }
            }) { Text("+ 新增") }
        })

        if (rules.isEmpty()) {
            EmptyHint("暂无规则，点右上角 + 新增阈值告警")
        } else {
            LazyColumn(verticalArrangement = androidx.compose.foundation.layout.Arrangement.spacedBy(8.dp)) {
                items(rules, key = { it.id }) { r ->
                    RuleRow(r, wt, onToggle = { vm.save(r.copy(enabled = it)) }, onEdit = { editing = r })
                }
            }
        }
    }

    editing?.let { rule ->
        EditRuleSheet(
            rule = rule,
            waterType = wt,
            onSave = { vm.save(it); editing = null },
            onDismiss = { editing = null },
        )
    }
}

@Composable
private fun RuleRow(rule: AlertRuleEntity, waterType: String?, onToggle: (Boolean) -> Unit, onEdit: () -> Unit) {
    Surface(
        shape = RoundedCornerShape(14.dp),
        color = MaterialTheme.colorScheme.surface,
        border = androidx.compose.foundation.BorderStroke(1.dp, MaterialTheme.colorScheme.outline),
        modifier = Modifier.fillMaxWidth(),
    ) {
        Row(Modifier.padding(12.dp), verticalAlignment = Alignment.CenterVertically) {
            Column(Modifier.weight(1f)) {
                Text(Metrics.metricLabel(rule.metric, waterType), fontWeight = FontWeight.Bold, fontSize = 13.5.sp)
                val desc = when (rule.mode) {
                    "range" -> "${rule.minVal ?: "?"} ~ ${rule.maxVal ?: "?"} · 持续 ${rule.holdN} 次 · 冷却 ${rule.cooldownMin} 分钟"
                    else -> "基线 ${rule.baseline ?: "?"} ± ${rule.pct ?: "?"}%"
                }
                Text(desc, fontSize = 11.5.sp, color = Muted, modifier = Modifier.padding(top = 2.dp))
                if (!rule.silentFrom.isNullOrBlank()) {
                    Text("免打扰 ${rule.silentFrom} ~ ${rule.silentTo}", fontSize = 11.sp, color = Muted)
                }
            }
            TextButton(onClick = onEdit) { Text("编辑") }
            Switch(checked = rule.enabled, onCheckedChange = onToggle)
        }
    }
}

/** 阈值编辑弹层（原型 16；免打扰时段编辑在下方同表单内，原型 17 字段） */
@Composable
private fun EditRuleSheet(
    rule: AlertRuleEntity,
    waterType: String?,
    onSave: (AlertRuleEntity) -> Unit,
    onDismiss: () -> Unit,
) {
    var r by remember(rule.id) { mutableStateOf(rule) }

    ModalBottomSheet(onDismissRequest = onDismiss) {
        Column(
            Modifier
                .verticalScroll(rememberScrollState())
                .padding(horizontal = 18.dp)
                .padding(bottom = 30.dp),
        ) {
            Text("编辑阈值 · ${Metrics.metricLabel(r.metric, waterType)}", fontWeight = FontWeight.ExtraBold, fontSize = 16.sp)
            Spacer(Modifier.height(12.dp))

            Text("指标", fontSize = 12.5.sp, color = Muted, modifier = Modifier.padding(bottom = 6.dp))
            FlowRow(horizontalArrangement = Arrangement.spacedBy(6.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                Metrics.visibleMetricKeys(waterType).forEach { key ->
                    val selected = r.metric == key
                    Surface(
                        onClick = { r = r.copy(metric = key) },
                        shape = RoundedCornerShape(10.dp),
                        color = if (selected) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.surface,
                        border = androidx.compose.foundation.BorderStroke(
                            1.dp,
                            if (selected) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.outline,
                        ),
                    ) {
                        Text(
                            Metrics.metricLabel(key, waterType),
                            fontSize = 12.sp,
                            color = if (selected) MaterialTheme.colorScheme.onPrimary else MaterialTheme.colorScheme.onSurface,
                            modifier = Modifier.padding(horizontal = 10.dp, vertical = 7.dp),
                        )
                    }
                }
            }
            Spacer(Modifier.height(4.dp))

            if (r.mode == "range") {
                NumField("下限", r.minVal) { r = r.copy(minVal = it) }
                NumField("上限", r.maxVal) { r = r.copy(maxVal = it) }
            } else {
                NumField("基线", r.baseline) { r = r.copy(baseline = it) }
                NumField("允许偏差 %", r.pct) { r = r.copy(pct = it) }
            }
            NumField("持续确认次数", r.holdN.toDouble()) { r = r.copy(holdN = it.toInt()) }
            NumField("同规则冷却（分钟）", r.cooldownMin.toDouble()) { r = r.copy(cooldownMin = it.toInt()) }

            Text("免打扰（可选）", fontSize = 12.5.sp, color = Muted, modifier = Modifier.padding(top = 10.dp, bottom = 4.dp))
            OutlinedTextField(
                value = r.silentFrom ?: "",
                onValueChange = { r = r.copy(silentFrom = it.ifBlank { null }) },
                label = { Text("开始 如 23:00") },
                singleLine = true,
                modifier = Modifier.fillMaxWidth(),
            )
            OutlinedTextField(
                value = r.silentTo ?: "",
                onValueChange = { r = r.copy(silentTo = it.ifBlank { null }) },
                label = { Text("结束 如 07:00（早于开始按跨天）") },
                singleLine = true,
                modifier = Modifier.fillMaxWidth(),
            )

            Row(Modifier.padding(top = 12.dp), verticalAlignment = Alignment.CenterVertically) {
                TextButton(onClick = { r = if (r.mode == "range") r.copy(mode = "baseline") else r.copy(mode = "range") }) {
                    Text(if (r.mode == "range") "切换为基线±百分比" else "切换为固定区间")
                }
                Spacer(Modifier.weight(1f))
                Button(onClick = { onSave(r) }, shape = RoundedCornerShape(12.dp)) { Text("保存规则") }
            }
        }
    }
}

@Composable
private fun NumField(label: String, value: Double?, onChange: (Double) -> Unit) {
    OutlinedTextField(
        value = value?.toString() ?: "",
        onValueChange = { it.toDoubleOrNull()?.let(onChange) },
        label = { Text(label) },
        singleLine = true,
        modifier = Modifier.fillMaxWidth().padding(top = 8.dp),
    )
}
