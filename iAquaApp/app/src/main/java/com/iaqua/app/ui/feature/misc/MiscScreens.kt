package com.iaqua.app.ui.feature.misc

import androidx.compose.foundation.Image
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.ViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.iaqua.app.R
import com.iaqua.app.core.theme.Muted
import com.iaqua.app.core.theme.TealDark
import com.iaqua.app.data.db.LivestockEntity
import com.iaqua.app.data.repo.LivestockRepository
import com.iaqua.app.data.repo.TankRepository
import com.iaqua.app.ui.components.EmptyHint
import com.iaqua.app.ui.components.ScreenHeader
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.flatMapLatest
import kotlinx.coroutines.flow.flowOf
import kotlinx.coroutines.flow.stateIn
import javax.inject.Inject

// ================= 09/10 生物·水草·设备列表 =================

@OptIn(ExperimentalCoroutinesApi::class)
@HiltViewModel
class LivestockViewModel @Inject constructor(
    livestockRepo: LivestockRepository,
    tankRepo: TankRepository,
) : ViewModel() {
    var kind: String = "生物"

    val entries = tankRepo.activeTankId
        .flatMapLatest { id ->
            if (id == null) flowOf(emptyList()) else livestockRepo.observeByTank(id, kind)
        }
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), emptyList())
}

/** 生物/水草/设备列表（原型 09/10 同构页，kind 区分） */
@Composable
fun LivestockScreen(
    kind: String,
    onBack: () -> Unit,
    vm: LivestockViewModel = hiltViewModel(),
) {
    vm.kind = kind
    val entries by vm.entries.collectAsStateWithLifecycle()

    Column(Modifier.fillMaxSize().padding(horizontal = 14.dp)) {
        Spacer(Modifier.height(6.dp))
        ScreenHeader("$kind · 列表", onBack)
        if (entries.isEmpty()) {
            EmptyHint("暂无${kind}条目（TODO M2：新增/编辑表单）")
        } else {
            LazyColumn(verticalArrangement = androidx.compose.foundation.layout.Arrangement.spacedBy(8.dp)) {
                items(entries, key = { it.id }) { e -> LivestockRow(e) }
            }
        }
    }
}

@Composable
private fun LivestockRow(e: LivestockEntity) {
    Surface(
        shape = RoundedCornerShape(14.dp),
        color = MaterialTheme.colorScheme.surface,
        border = androidx.compose.foundation.BorderStroke(1.dp, MaterialTheme.colorScheme.outline),
        modifier = Modifier.fillMaxWidth(),
    ) {
        Row(Modifier.padding(12.dp), verticalAlignment = Alignment.CenterVertically) {
            Column(Modifier.weight(1f)) {
                Text("${e.name} × ${e.count}", fontWeight = FontWeight.Bold, fontSize = 13.5.sp)
                if (e.note.isNotEmpty()) Text(e.note, fontSize = 11.5.sp, color = Muted, modifier = Modifier.padding(top = 2.dp))
            }
            Text("›", color = Muted, fontSize = 16.sp)
        }
    }
}

// ================= 12 数据与导出 =================

@Composable
fun ExportScreen(onBack: () -> Unit) {
    Column(Modifier.fillMaxSize().padding(horizontal = 14.dp)) {
        Spacer(Modifier.height(6.dp))
        ScreenHeader("数据与导出", onBack)
        EntryRow("生成 PDF 报告", "可打印的鱼缸报告（趋势 + 统计 + 日志摘要）", onClick = {})
        EntryRow("导出 CSV", "读数打包 ZIP · 列格式与 PC 上位机一致", onClick = {})
        EntryRow("备份与恢复", "本地完整备份 · 一键恢复", onClick = {})
        Text(
            "TODO M2：PDF 生成（Android PdfDocument）、CSV 打包、Room→JSON 备份恢复。",
            fontSize = 11.sp, color = Muted, modifier = Modifier.padding(top = 10.dp),
        )
    }
}

// ================= 13 摄像头全屏 =================

@Composable
fun CameraScreen(onBack: () -> Unit) {
    Column(Modifier.fillMaxSize()) {
        Spacer(Modifier.height(40.dp))
        ScreenHeader("实时画面", onBack)
        Surface(
            color = Color(0xFF0D2B27),
            modifier = Modifier.fillMaxWidth().height(360.dp).padding(horizontal = 14.dp),
            shape = RoundedCornerShape(18.dp),
        ) {
            Column(Modifier.padding(20.dp), verticalArrangement = androidx.compose.foundation.layout.Arrangement.Center) {
                Text("MJPEG 画面区域", color = Color.White, fontSize = 14.sp)
                Text(
                    "TODO M2：自研 MJPEG 流解析（http://<cam>:81/stream，固件支持 3 客户端并发）；降级 /capture 快照轮询。",
                    color = Color(0xFF9DB8B3), fontSize = 11.sp, modifier = Modifier.padding(top = 8.dp),
                )
            }
        }
    }
}

// ================= 15 设置 =================

@Composable
fun SettingsScreen(onBack: () -> Unit) {
    Column(Modifier.fillMaxSize().padding(horizontal = 14.dp)) {
        Spacer(Modifier.height(6.dp))
        ScreenHeader("设置", onBack)

        Column(
            Modifier.fillMaxWidth().padding(top = 18.dp, bottom = 20.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
        ) {
            Image(
                painter = painterResource(R.drawable.logo_iaquaria),
                contentDescription = "iAquaria logo",
                modifier = Modifier.size(84.dp),
            )
            Text("iAquaria", fontWeight = FontWeight.ExtraBold, fontSize = 20.sp, modifier = Modifier.padding(top = 10.dp))
            Text("集美大学", fontSize = 12.sp, color = Muted, modifier = Modifier.padding(top = 2.dp))
        }

        EntryRow("账号与云同步（M3 预留）", "多设备同步 · 厂商推送通道", onClick = {})
        EntryRow("提醒", "系统通知 · 免打扰", onClick = {})
        EntryRow("外观 / 语言", "跟随系统 · 简体中文", onClick = {})
        EntryRow("关于", "iAquaria 0.1.0 · 集美大学 · M1", onClick = {})
    }
}

@Composable
private fun EntryRow(title: String, sub: String, onClick: () -> Unit) {
    Surface(
        onClick = onClick,
        shape = RoundedCornerShape(14.dp),
        color = MaterialTheme.colorScheme.surface,
        border = androidx.compose.foundation.BorderStroke(1.dp, MaterialTheme.colorScheme.outline),
        modifier = Modifier.fillMaxWidth().padding(bottom = 8.dp),
    ) {
        Row(Modifier.padding(horizontal = 14.dp, vertical = 12.dp), verticalAlignment = Alignment.CenterVertically) {
            Column(Modifier.weight(1f)) {
                Text(title, fontWeight = FontWeight.SemiBold, fontSize = 13.5.sp)
                Text(sub, fontSize = 11.5.sp, color = Muted, modifier = Modifier.padding(top = 2.dp))
            }
            Text("›", color = Muted, fontSize = 16.sp)
        }
    }
}
