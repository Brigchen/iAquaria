package com.iaqua.app.ui.feature.addtank

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
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
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.iaqua.app.core.Metrics
import com.iaqua.app.core.theme.TealDark
import com.iaqua.app.data.db.TankEntity
import com.iaqua.app.data.repo.DeviceRepository
import com.iaqua.app.data.repo.TankRepository
import com.iaqua.app.ui.components.ScreenHeader
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.launch
import javax.inject.Inject

@HiltViewModel
class AddTankViewModel @Inject constructor(
    private val tankRepo: TankRepository,
    private val device: DeviceRepository,
) : ViewModel() {
    suspend fun probe(url: String): Boolean = device.probe(url)
    fun save(tank: TankEntity, onDone: () -> Unit) = viewModelScope.launch {
        tankRepo.addTank(tank)
        onDone()
    }
}

/** 添加缸（原型 07）：缸档案 + 主板/摄像头地址 + 连通测试 */
@Composable
fun AddTankScreen(
    onBack: () -> Unit,
    vm: AddTankViewModel = hiltViewModel(),
) {
    var name by remember { mutableStateOf("") }
    var location by remember { mutableStateOf("") }
    var capacity by remember { mutableStateOf("") }
    var waterType by remember { mutableStateOf(Metrics.WATER_FRESH) }
    var ws by remember { mutableStateOf("") }
    var cam by remember { mutableStateOf("") }
    var probeMsg by remember { mutableStateOf("") }
    val scope = rememberCoroutineScope()

    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(horizontal = 14.dp)) {
        Spacer(Modifier.height(6.dp))
        ScreenHeader("添加鱼缸", onBack)

        Field("缸名称", name, { name = it }, placeholder = "如：客厅缸")
        Field("位置", location, { location = it }, placeholder = "如：客厅 · 南侧")
        Field("容量（升）", capacity, { capacity = it })

        Text("水型", fontSize = 12.5.sp, color = com.iaqua.app.core.theme.Muted, modifier = Modifier.padding(top = 10.dp, bottom = 4.dp))
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            listOf(Metrics.WATER_FRESH, Metrics.WATER_SALT, Metrics.WATER_PLANTED).forEach { wt ->
                val selected = waterType == wt
                Surface(
                    onClick = { waterType = wt },
                    shape = RoundedCornerShape(12.dp),
                    color = if (selected) TealDark else MaterialTheme.colorScheme.surface,
                    border = androidx.compose.foundation.BorderStroke(1.dp, if (selected) TealDark else MaterialTheme.colorScheme.outline),
                    modifier = Modifier.weight(1f),
                ) {
                    Text(
                        wt,
                        color = if (selected) Color.White else MaterialTheme.colorScheme.onSurface,
                        fontWeight = if (selected) FontWeight.Bold else FontWeight.Normal,
                        fontSize = 13.sp,
                        textAlign = TextAlign.Center,
                        modifier = Modifier.fillMaxWidth().padding(vertical = 10.dp),
                    )
                }
            }
        }
        Text(
            Metrics.sensorHint(waterType),
            fontSize = 11.5.sp,
            color = com.iaqua.app.core.theme.Muted,
            modifier = Modifier.padding(top = 6.dp),
        )

        Field("主板地址", ws, { ws = it }, placeholder = "ws://192.168.3.190/ws")
        Field("摄像头地址（可选）", cam, { cam = it }, placeholder = "http://192.168.3.191")

        Surface(
            onClick = {
                probeMsg = "测试中…"
                scope.launch {
                    val ok = vm.probe(ws)
                    probeMsg = if (ok) "已连接" else "连接失败，请检查地址"
                }
            },
            shape = RoundedCornerShape(12.dp),
            color = MaterialTheme.colorScheme.surface,
            border = androidx.compose.foundation.BorderStroke(1.dp, MaterialTheme.colorScheme.outline),
            modifier = Modifier.padding(top = 4.dp),
        ) {
            Text("测试主板连通", color = TealDark, fontWeight = FontWeight.SemiBold, fontSize = 13.sp, modifier = Modifier.padding(horizontal = 14.dp, vertical = 10.dp))
        }
        if (probeMsg.isNotEmpty()) {
            Text(probeMsg, fontSize = 12.sp, color = if (probeMsg == "已连接") TealDark else MaterialTheme.colorScheme.error, modifier = Modifier.padding(top = 6.dp))
        }

        Button(
            onClick = {
                vm.save(
                    TankEntity(
                        name = name.ifEmpty { "新鱼缸" },
                        location = location,
                        capacityL = capacity.toIntOrNull() ?: 0,
                        waterType = waterType,
                        deviceWs = ws,
                        camUrl = cam,
                    ),
                    onDone = onBack,
                )
            },
            modifier = Modifier.fillMaxWidth().padding(top = 16.dp),
            shape = RoundedCornerShape(14.dp),
        ) { Text("保存并创建") }

        Spacer(Modifier.height(30.dp))
    }
}

@Composable
private fun Field(
    label: String,
    value: String,
    onChange: (String) -> Unit,
    placeholder: String = "",
) {
    Text(label, fontSize = 12.5.sp, color = com.iaqua.app.core.theme.Muted, modifier = Modifier.padding(top = 10.dp, bottom = 4.dp))
    OutlinedTextField(
        value = value,
        onValueChange = onChange,
        placeholder = { Text(placeholder, fontSize = 13.sp) },
        singleLine = true,
        modifier = Modifier.fillMaxWidth(),
    )
}
