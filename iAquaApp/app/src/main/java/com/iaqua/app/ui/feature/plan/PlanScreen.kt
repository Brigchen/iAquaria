package com.iaqua.app.ui.feature.plan

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.SegmentedButton
import androidx.compose.material3.SegmentedButtonDefaults
import androidx.compose.material3.SingleChoiceSegmentedButtonRow
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.remember
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
import com.iaqua.app.core.theme.Warn
import com.iaqua.app.core.theme.WarnBg
import com.iaqua.app.data.db.TaskEntity
import com.iaqua.app.data.repo.TaskRepository
import com.iaqua.app.data.repo.TankRepository
import com.iaqua.app.ui.components.EmptyHint
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.flatMapLatest
import kotlinx.coroutines.flow.flowOf
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import javax.inject.Inject

@OptIn(ExperimentalCoroutinesApi::class)
@HiltViewModel
class PlanViewModel @Inject constructor(
    private val taskRepo: TaskRepository,
    tankRepo: TankRepository,
) : ViewModel() {
    val tasks = tankRepo.activeTankId
        .flatMapLatest { id ->
            if (id == null) flowOf(emptyList()) else taskRepo.observeByTank(id)
        }
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), emptyList())

    fun complete(task: TaskEntity) = viewModelScope.launch { taskRepo.complete(task) }
}

/** 计划页（原型 05）：今天 / 即将到期 / 全部 分组 + 一键完成 */
@Composable
fun PlanScreen(vm: PlanViewModel = hiltViewModel()) {
    val tasks by vm.tasks.collectAsStateWithLifecycle()
    var seg by remember { mutableIntStateOf(0) }

    Column(Modifier.fillMaxSize().padding(horizontal = 14.dp)) {
        Spacer(Modifier.height(8.dp))
        Text("计划", style = MaterialTheme.typography.titleLarge)
        Spacer(Modifier.height(10.dp))

        SingleChoiceSegmentedButtonRow(Modifier.fillMaxWidth()) {
            listOf("今天", "即将到期", "全部").forEachIndexed { i, label ->
                SegmentedButton(
                    selected = seg == i,
                    onClick = { seg = i },
                    shape = SegmentedButtonDefaults.itemShape(i, 3),
                ) { Text(label, fontSize = 12.sp) }
            }
        }
        Spacer(Modifier.height(10.dp))

        if (tasks.isEmpty()) {
            EmptyHint("暂无周期任务")
            return@Column
        }

        val now = System.currentTimeMillis()
        val dayMs = 24 * 60 * 60 * 1000L
        val shown = when (seg) {
            0 -> tasks.filter { it.nextDue < now + dayMs }
            1 -> tasks.filter { it.nextDue >= now + dayMs && it.nextDue < now + 3 * dayMs }
            else -> tasks
        }
        if (shown.isEmpty()) {
            EmptyHint("该分组暂无任务")
            return@Column
        }

        LazyColumn(verticalArrangement = Arrangement.spacedBy(8.dp)) {
            items(shown, key = { it.id }) { t ->
                val overdue = t.nextDue < now
                Surface(
                    shape = RoundedCornerShape(14.dp),
                    color = if (overdue) WarnBg else MaterialTheme.colorScheme.surface,
                    border = androidx.compose.foundation.BorderStroke(1.dp, if (overdue) Warn else MaterialTheme.colorScheme.outline),
                ) {
                    Column(Modifier.fillMaxWidth().padding(12.dp)) {
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Text(t.title, fontWeight = FontWeight.Bold, fontSize = 13.5.sp)
                            Spacer(Modifier.weight(1f))
                            TextButton(onClick = { vm.complete(t) }) { Text("完成") }
                        }
                        val time = SimpleDateFormat("MM-dd HH:mm", Locale.getDefault()).format(Date(t.nextDue))
                        Text(
                            "${t.type} · 每 ${t.periodDays} 天 · 到期 $time" + if (overdue) " · 已逾期" else "",
                            fontSize = 11.5.sp,
                            color = if (overdue) Warn else Muted,
                        )
                    }
                }
            }
        }
    }
}
