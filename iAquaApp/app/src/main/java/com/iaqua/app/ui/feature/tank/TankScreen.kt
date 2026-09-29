package com.iaqua.app.ui.feature.tank

import androidx.compose.foundation.layout.Arrangement
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
import androidx.compose.material3.MaterialTheme
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
import com.iaqua.app.core.theme.Muted
import com.iaqua.app.core.theme.TealDark
import com.iaqua.app.data.db.TankEntity
import com.iaqua.app.data.repo.TankRepository
import com.iaqua.app.ui.components.EmptyHint
import com.iaqua.app.ui.components.SectionCard
import dagger.hilt.android.lifecycle.HiltViewModel
import javax.inject.Inject

@HiltViewModel
class TankViewModel @Inject constructor(
    tankRepo: TankRepository,
) : ViewModel() {
    val activeTank = tankRepo.activeTank
}

/** 鱼缸页（原型 06）：缸档案 + 生物/水草/设备/提醒入口 + 导出/规则/设置 */
@Composable
fun TankScreen(
    onOpenLivestock: (String) -> Unit,
    onOpenExport: () -> Unit,
    onOpenRules: () -> Unit,
    onOpenSettings: () -> Unit,
    onAddTank: () -> Unit,
    vm: TankViewModel = hiltViewModel(),
) {
    val tank by vm.activeTank.collectAsStateWithLifecycle(initialValue = null)

    Column(
        Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(horizontal = 14.dp),
    ) {
        Spacer(Modifier.height(8.dp))
        Text("鱼缸", style = MaterialTheme.typography.titleLarge)
        Spacer(Modifier.height(10.dp))

        val t = tank
        if (t == null) {
            EmptyHint("还没有鱼缸，点击下方添加")
        } else {
            TankFacts(t)
        }

        SectionCard(title = "内容管理") {
            listOf(
                Triple("生物", "鱼类 / 虾 / 螺档案", "生物"),
                Triple("水草", "水草种类与状态", "水草"),
                Triple("设备", "设备档案与保养", "设备"),
            ).forEach { (name, sub, kind) ->
                EntryRow(name, sub) { onOpenLivestock(kind) }
            }
        }

        EntryRow("数据与导出", "PDF · CSV · 备份", onClick = onOpenExport)
        EntryRow("提醒规则", "阈值 · 建议 · 免打扰", onClick = onOpenRules)
        EntryRow("设置", "通知 · 通用 · 关于", onClick = onOpenSettings)

        Spacer(Modifier.height(10.dp))
        Surface(
            onClick = onAddTank,
            shape = RoundedCornerShape(14.dp),
            color = MaterialTheme.colorScheme.surface,
            border = androidx.compose.foundation.BorderStroke(1.dp, MaterialTheme.colorScheme.outline),
            modifier = Modifier.fillMaxWidth(),
        ) {
            Text(
                "+ 添加新缸",
                color = TealDark,
                fontWeight = FontWeight.SemiBold,
                fontSize = 13.5.sp,
                modifier = Modifier.padding(14.dp),
            )
        }
        Spacer(Modifier.height(90.dp))
    }
}

@Composable
private fun TankFacts(t: TankEntity) {
    SectionCard(title = t.name) {
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
            Fact("容量", if (t.capacityL > 0) "${t.capacityL} 升" else "--")
            Fact("水型", t.waterType)
            Fact("位置", t.location.ifEmpty { "--" })
        }
    }
}

@Composable
private fun Fact(k: String, v: String) {
    Column {
        Text(k, fontSize = 11.sp, color = Muted)
        Text(v, fontSize = 14.sp, fontWeight = FontWeight.Bold, modifier = Modifier.padding(top = 2.dp))
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
        Row(
            Modifier.padding(horizontal = 14.dp, vertical = 12.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Column(Modifier.weight(1f)) {
                Text(title, fontWeight = FontWeight.SemiBold, fontSize = 13.5.sp)
                Text(sub, fontSize = 11.5.sp, color = Muted, modifier = Modifier.padding(top = 2.dp))
            }
            Text("›", color = Muted, fontSize = 16.sp)
        }
    }
}
