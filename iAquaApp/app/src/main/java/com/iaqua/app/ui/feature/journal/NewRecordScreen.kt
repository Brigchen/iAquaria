package com.iaqua.app.ui.feature.journal

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.iaqua.app.core.theme.Muted
import com.iaqua.app.data.db.JournalEntity
import com.iaqua.app.data.repo.JournalRepository
import com.iaqua.app.data.repo.TankRepository
import com.iaqua.app.ui.components.ScreenHeader
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.launch
import javax.inject.Inject

@HiltViewModel
class NewRecordViewModel @Inject constructor(
    private val journalRepo: JournalRepository,
    private val tankRepo: TankRepository,
) : ViewModel() {
    fun save(type: String, title: String, detail: String, onDone: () -> Unit) = viewModelScope.launch {
        val tankId = tankRepo.activeTankId.first() ?: return@launch
        journalRepo.add(
            JournalEntity(
                tankId = tankId,
                ts = System.currentTimeMillis(),
                type = type,
                title = title.ifEmpty { type },
                detail = detail,
                source = "手动",
            ),
        )
        onDone()
    }
}

/** 新建记录（原型 04）：类型 / 数值备注 / 照片（M2）/ 关联缸 */
@Composable
fun NewRecordScreen(
    onBack: () -> Unit,
    vm: NewRecordViewModel = hiltViewModel(),
) {
    var type by remember { mutableStateOf("换水") }
    var detail by remember { mutableStateOf("") }
    val scope = rememberCoroutineScope()

    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(horizontal = 14.dp)) {
        Spacer(Modifier.height(6.dp))
        ScreenHeader("新建记录", onBack)

        Text("类型", fontSize = 12.5.sp, color = Muted, modifier = Modifier.padding(top = 10.dp, bottom = 4.dp))
        Row(Modifier.fillMaxWidth(), horizontalArrangement = androidx.compose.foundation.layout.Arrangement.spacedBy(8.dp)) {
            listOf("水质检测", "换水", "喂食", "维护").forEach { t ->
                Button(
                    onClick = { type = t },
                    shape = RoundedCornerShape(12.dp),
                    colors = if (type == t) {
                        androidx.compose.material3.ButtonDefaults.buttonColors()
                    } else {
                        androidx.compose.material3.ButtonDefaults.buttonColors(
                            containerColor = MaterialTheme.colorScheme.surface,
                            contentColor = Muted,
                        )
                    },
                    modifier = Modifier.weight(1f),
                ) { Text(t, fontSize = 11.5.sp) }
            }
        }

        OutlinedTextField(
            value = detail,
            onValueChange = { detail = it },
            label = { Text("备注（如：换水量 30%，添加水质稳定剂）") },
            modifier = Modifier.fillMaxWidth().padding(top = 12.dp),
            minLines = 3,
        )

        // TODO(M2): 照片选择（≤9 张）与保存到应用私有目录

        Button(
            onClick = { scope.launch { vm.save(type, type, detail) { onBack() } } },
            modifier = Modifier.fillMaxWidth().padding(top = 16.dp),
            shape = RoundedCornerShape(14.dp),
        ) { Text("保存记录") }

        Text(
            "保存后写入养护日志；若为周期任务类型，将自动顺延下次到期时间。",
            fontSize = 11.sp,
            color = Muted,
            modifier = Modifier.padding(top = 10.dp),
        )
        Spacer(Modifier.height(30.dp))
    }
}
