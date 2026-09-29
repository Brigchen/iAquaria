package com.iaqua.app.ui.components

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.iaqua.app.core.theme.Danger
import com.iaqua.app.core.theme.Line
import com.iaqua.app.core.theme.Muted
import com.iaqua.app.core.theme.Ok
import com.iaqua.app.core.theme.Warn
import com.iaqua.app.core.theme.WarnBg

/** 指标状态点 */
@Composable
fun StatusDot(state: MetricState, modifier: Modifier = Modifier) {
    val color = when (state) {
        MetricState.OK -> Ok
        MetricState.WARN -> Warn
        MetricState.OFF -> Muted
    }
    Box(modifier.size(8.dp).background(color, CircleShape))
}

enum class MetricState { OK, WARN, OFF }

/** 指标卡（概览网格单元，原型 01） */
@Composable
fun MetricCard(
    label: String,
    value: String,
    unit: String = "",
    state: MetricState = MetricState.OK,
    modifier: Modifier = Modifier,
) {
    Card(
        modifier = modifier,
        shape = RoundedCornerShape(14.dp),
        colors = CardDefaults.cardColors(
            containerColor = if (state == MetricState.WARN) WarnBg else MaterialTheme.colorScheme.surface,
        ),
        border = androidx.compose.foundation.BorderStroke(1.dp, if (state == MetricState.WARN) Warn else Line),
    ) {
        Column(Modifier.padding(horizontal = 12.dp, vertical = 10.dp)) {
            Row(
                Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Text(label, fontSize = 11.5.sp, color = Muted)
                StatusDot(state)
            }
            Spacer(Modifier.height(3.dp))
            Row(verticalAlignment = Alignment.Bottom) {
                Text(value, fontSize = 19.sp, fontWeight = FontWeight.ExtraBold)
                if (unit.isNotEmpty()) {
                    Spacer(Modifier.width(2.dp))
                    Text(unit, fontSize = 11.sp, color = Muted, modifier = Modifier.padding(bottom = 2.dp))
                }
            }
        }
    }
}

/** 区块卡片（统一标题+内容容器） */
@Composable
fun SectionCard(
    title: String,
    modifier: Modifier = Modifier,
    trailing: (@Composable () -> Unit)? = null,
    content: @Composable () -> Unit,
) {
    Card(
        modifier = modifier.fillMaxWidth(),
        shape = RoundedCornerShape(18.dp),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
        border = androidx.compose.foundation.BorderStroke(1.dp, Line),
    ) {
        Column(Modifier.padding(12.dp)) {
            Row(
                Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Text(title, fontSize = 13.sp, color = Muted, fontWeight = FontWeight.SemiBold)
                trailing?.invoke()
            }
            Spacer(Modifier.height(8.dp))
            content()
        }
    }
}

/** 告警横幅（概览顶部，原型 01；点击跳数据详情） */
@Composable
fun AlertBanner(
    title: String,
    detail: String,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
) {
    Surface(
        modifier = modifier.fillMaxWidth(),
        shape = RoundedCornerShape(18.dp),
        color = WarnBg,
        border = androidx.compose.foundation.BorderStroke(1.dp, Warn),
        onClick = onClick,
    ) {
        Column(Modifier.padding(12.dp)) {
            Text(title, fontSize = 13.sp, fontWeight = FontWeight.Bold, color = Warn)
            Text(detail, fontSize = 12.sp, color = Warn, modifier = Modifier.padding(top = 2.dp))
        }
    }
}

/** 页头（二级页通用：返回 + 标题 + 右侧动作） */
@Composable
fun ScreenHeader(
    title: String,
    onBack: (() -> Unit)?,
    modifier: Modifier = Modifier,
    trailing: (@Composable () -> Unit)? = null,
) {
    Row(
        modifier.fillMaxWidth().padding(vertical = 10.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        if (onBack != null) {
            Surface(
                onClick = onBack,
                shape = RoundedCornerShape(12.dp),
                color = MaterialTheme.colorScheme.surface,
                border = androidx.compose.foundation.BorderStroke(1.dp, Line),
            ) {
                Text("‹", fontSize = 20.sp, modifier = Modifier.padding(horizontal = 12.dp, vertical = 2.dp))
            }
            Spacer(Modifier.width(10.dp))
        }
        Text(title, style = MaterialTheme.typography.titleMedium, fontSize = 17.sp)
        Spacer(Modifier.weight(1f))
        trailing?.invoke()
    }
}

/** 底部导航项图标占位 */
@Composable
fun NavIcon(icon: ImageVector, tint: Color, modifier: Modifier = Modifier) {
    Icon(icon, contentDescription = null, tint = tint, modifier = modifier.size(22.dp))
}

/** 空态提示 */
@Composable
fun EmptyHint(text: String, modifier: Modifier = Modifier) {
    Box(modifier.fillMaxWidth().height(120.dp), contentAlignment = Alignment.Center) {
        Text(text, color = Muted, fontSize = 13.sp)
    }
}
