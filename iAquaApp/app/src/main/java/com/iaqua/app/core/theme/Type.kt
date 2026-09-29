package com.iaqua.app.core.theme

import androidx.compose.material3.Typography
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.sp

val IaquaTypography = Typography(
    titleLarge = TextStyle(fontWeight = FontWeight.ExtraBold, fontSize = 21.sp, color = Ink),
    titleMedium = TextStyle(fontWeight = FontWeight.Bold, fontSize = 15.sp, color = Ink),
    bodyMedium = TextStyle(fontSize = 13.sp, color = Ink),
    bodySmall = TextStyle(fontSize = 11.5.sp, color = Muted),
    labelSmall = TextStyle(fontSize = 10.5.sp, color = Muted),
)
