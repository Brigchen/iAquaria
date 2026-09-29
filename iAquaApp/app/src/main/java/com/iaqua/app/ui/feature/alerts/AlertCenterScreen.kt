package com.iaqua.app.ui.feature.alerts

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
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
import com.iaqua.app.core.theme.Ok
import com.iaqua.app.core.theme.Warn
import com.iaqua.app.core.theme.WarnBg
import com.iaqua.app.data.db.AlertEventEntity
import com.iaqua.app.data.repo.AlertRepository
import com.iaqua.app.data.repo.TankRepository
import com.iaqua.app.ui.components.EmptyHint
import com.iaqua.app.ui.components.ScreenHeader
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
class AlertCenterViewModel @Inject constructor(
    private val alertRepo: AlertRepository,
    tankRepo: TankRepository,
) : ViewModel() {
    val events = tankRepo.activeTankId
        .flatMapLatest { id ->
            if (id == null) flowOf(emptyList()) else alertRepo.observeEvents(id)
        }
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), emptyList())

    fun resolve(event: AlertEventEntity) = viewModelScope.launch {
        alertRepo.resolve(event.id, "手动处理")
    }
}

/** 提醒中心（原型 11）：进行中 / 已恢复事件列表 */
@Composable
fun AlertCenterScreen(
    onBack: () -> Unit,
    vm: AlertCenterViewModel = hiltViewModel(),
) {
    val events by vm.events.collectAsStateWithLifecycle()

    Column(Modifier.fillMaxSize().padding(horizontal = 14.dp)) {
        Spacer(Modifier.height(6.dp))
        ScreenHeader("提醒中心", onBack)

        if (events.isEmpty()) {
            EmptyHint("暂无告警事件")
        } else {
            LazyColumn(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                items(events, key = { it.id }) { e ->
                    val active = !e.resolved
                    Surface(
                        shape = RoundedCornerShape(14.dp),
                        color = if (active) WarnBg else MaterialTheme.colorScheme.surface,
                        border = androidx.compose.foundation.BorderStroke(1.dp, if (active) Warn else MaterialTheme.colorScheme.outline),
                        modifier = Modifier.fillMaxWidth(),
                    ) {
                        Row(Modifier.padding(12.dp), verticalAlignment = Alignment.CenterVertically) {
                            Column(Modifier.weight(1f)) {
                                Text(
                                    if (active) "进行中 · 快照 ${e.snapshot}" else "已恢复 · 快照 ${e.snapshot}",
                                    fontWeight = FontWeight.Bold,
                                    fontSize = 13.5.sp,
                                    color = if (active) Warn else Ok,
                                )
                                val time = SimpleDateFormat("MM-dd HH:mm", Locale.getDefault()).format(Date(e.ts))
                                Text(time + (e.note.takeIf { it.isNotBlank() }?.let { " · $it" } ?: ""), fontSize = 11.5.sp, color = Muted, modifier = Modifier.padding(top = 2.dp))
                            }
                            if (active) TextButton(onClick = { vm.resolve(e) }) { Text("去处理") }
                        }
                    }
                }
            }
        }
    }
}
