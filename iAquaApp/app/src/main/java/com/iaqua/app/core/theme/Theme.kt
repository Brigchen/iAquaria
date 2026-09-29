package com.iaqua.app.core.theme

import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color

private val LightColors = lightColorScheme(
    primary = Teal,
    onPrimary = Color.White,
    primaryContainer = TealLight,
    onPrimaryContainer = TealDark,
    secondary = TealDark,
    background = PageBg,
    onBackground = Ink,
    surface = CardBg,
    onSurface = Ink,
    surfaceVariant = TealLight,
    onSurfaceVariant = Muted,
    outline = Line,
    outlineVariant = Line,
    error = Danger,
)

/** M1 仅提供浅色水系主题（与原型一致），深色主题后续版本补充 */
@Composable
fun IaquaTheme(content: @Composable () -> Unit) {
    MaterialTheme(colorScheme = LightColors, typography = IaquaTypography, content = content)
}
