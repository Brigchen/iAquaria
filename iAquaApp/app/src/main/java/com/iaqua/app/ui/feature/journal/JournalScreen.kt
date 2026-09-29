package com.iaqua.app.ui.feature.journal

import androidx.compose.foundation.background
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
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.FloatingActionButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
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
import com.iaqua.app.core.theme.Teal
import com.iaqua.app.core.theme.TealDark
import com.iaqua.app.core.theme.TealLight
import com.iaqua.app.data.db.JournalEntity
import com.iaqua.app.data.repo.JournalRepository
import com.iaqua.app.data.repo.TankRepository
import com.iaqua.app.ui.components.EmptyHint
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.flatMapLatest
import kotlinx.coroutines.flow.flowOf
import kotlinx.coroutines.flow.stateIn
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import javax.inject.Inject

@OptIn(ExperimentalCoroutinesApi::class)
@HiltViewModel
class JournalViewModel @Inject constructor(
    journalRepo: JournalRepository,
    tankRepo: TankRepository,
) : ViewModel() {
    val entries = tankRepo.activeTankId
        .flatMapLatest { id ->
            if (id == null) flowOf(emptyList()) else journalRepo.observeByTank(id)
        }
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), emptyList())
}

/** 养护日志（原型 03）：时间线 + 分类筛选 + 图文记录 */
@Composable
fun JournalScreen(
    onNewRecord: () -> Unit,
    vm: JournalViewModel = hiltViewModel(),
) {
    val entries by vm.entries.collectAsStateWithLifecycle()

    Scaffold(
        floatingActionButton = {
            FloatingActionButton(
                onClick = onNewRecord,
                containerColor = Teal,
                contentColor = MaterialTheme.colorScheme.onPrimary,
                shape = RoundedCornerShape(18.dp),
            ) { Text("+", fontSize = 24.sp) }
        },
    ) { pad ->
        Column(Modifier.fillMaxSize().padding(pad).padding(horizontal = 14.dp)) {
            Spacer(Modifier.height(8.dp))
            Text("日志", style = MaterialTheme.typography.titleLarge)

            Spacer(Modifier.height(10.dp))
            // TODO(M1): 分类筛选 chips（水质检测/换水/喂食/维护）
            if (entries.isEmpty()) {
                EmptyHint("暂无记录，点右下角 + 新建")
            } else {
                LazyColumn(
                    verticalArrangement = Arrangement.spacedBy(8.dp),
                    modifier = Modifier.fillMaxSize(),
                ) {
                    items(entries, key = { it.id }) { e -> JournalRow(e) }
                }
            }
        }
    }
}

@Composable
private fun JournalRow(e: JournalEntity) {
    val time = SimpleDateFormat("MM-dd HH:mm", Locale.getDefault()).format(Date(e.ts))
    Surface(
        shape = RoundedCornerShape(14.dp),
        color = MaterialTheme.colorScheme.surface,
        border = androidx.compose.foundation.BorderStroke(1.dp, MaterialTheme.colorScheme.outline),
    ) {
        Row(Modifier.fillMaxWidth().padding(12.dp), verticalAlignment = Alignment.CenterVertically) {
            Box(Modifier.width(6.dp).height(36.dp).background(TealLight, RoundedCornerShape(3.dp)))
            Spacer(Modifier.width(10.dp))
            Column(Modifier.weight(1f)) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text(e.title, fontWeight = FontWeight.Bold, fontSize = 13.5.sp)
                    Spacer(Modifier.width(6.dp))
                    Text(
                        e.source,
                        fontSize = 10.sp,
                        color = TealDark,
                        modifier = Modifier
                            .background(TealLight, RoundedCornerShape(6.dp))
                            .padding(horizontal = 5.dp),
                    )
                }
                if (e.detail.isNotEmpty()) {
                    Text(e.detail, fontSize = 12.sp, color = Muted, modifier = Modifier.padding(top = 2.dp))
                }
            }
            Text(time, fontSize = 11.5.sp, color = Muted)
        }
    }
}
