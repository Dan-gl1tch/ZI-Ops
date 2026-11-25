package ziops

import androidx.compose.foundation.*
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.material3.ProvideTextStyle
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.ui.Alignment
import androidx.compose.foundation.text.BasicTextField
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.input.VisualTransformation
import androidx.compose.ui.graphics.SolidColor
import androidx.compose.ui.graphics.CompositingStrategy
import androidx.compose.ui.graphics.BlendMode
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.draw.drawWithContent
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.luminance
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

val OriginalDark = darkColorScheme(
    primary = Color(0xFF89B4FA), onPrimary = Color(0xFF1E1E2E),
    background = Color(0xFF1E1E2E), onBackground = Color(0xFFCDD6F4),
    surface = Color(0xFF191925), onSurface = Color(0xFFCDD6F4),
    surfaceVariant = Color(0xFF313244), onSurfaceVariant = Color(0xFFBAC2DE),
    outline = Color(0xFF585B70), secondary = Color(0xFFCBA6F7), error = Color(0xFFF38BA8)
)
val OriginalLight = lightColorScheme(
    primary = Color(0xFF334AA8), onPrimary = Color.White,
    background = Color(0xFFEFF1F5), onBackground = Color(0xFF4C4F69),
    surface = Color(0xFFE6E9EF), onSurface = Color(0xFF4C4F69),
    surfaceVariant = Color(0xFFCCD0DA), onSurfaceVariant = Color(0xFF5C5F77), outline = Color(0xFF7C7F93)
)
val WindowsFont = if (java.io.File("C:/Windows/Fonts/segoeui.ttf").isFile) FontFamily(
    androidx.compose.ui.text.platform.Font(java.io.File("C:/Windows/Fonts/segoeui.ttf"), weight = FontWeight.Normal),
    androidx.compose.ui.text.platform.Font(java.io.File("C:/Windows/Fonts/segoeuib.ttf"), weight = FontWeight.Bold)
) else FontFamily.SansSerif
val OriginalTypography = Typography(
    bodyLarge = TextStyle(fontFamily = WindowsFont, fontSize = 13.sp, lineHeight = 17.sp),
    bodyMedium = TextStyle(fontFamily = WindowsFont, fontSize = 13.sp, lineHeight = 17.sp),
    bodySmall = TextStyle(fontFamily = WindowsFont, fontSize = 12.sp, lineHeight = 16.sp),
    labelLarge = TextStyle(fontFamily = WindowsFont, fontSize = 13.sp, fontWeight = FontWeight.Bold),
    titleLarge = TextStyle(fontSize = 14.sp, fontWeight = FontWeight.Bold),
    titleMedium = TextStyle(fontSize = 13.sp, fontWeight = FontWeight.Bold)
)

@Composable fun Section(title: String, modifier: Modifier = Modifier, content: @Composable ColumnScope.() -> Unit) {
    Column(modifier.fillMaxWidth().border(1.dp, MaterialTheme.colorScheme.outline, RoundedCornerShape(4.dp))
        .background(MaterialTheme.colorScheme.surface, RoundedCornerShape(4.dp)).padding(10.dp),
        verticalArrangement = Arrangement.spacedBy(4.dp)) {
        Text(title, Modifier.monochrome(MaterialTheme.colorScheme.primary), color = MaterialTheme.colorScheme.primary, fontWeight = FontWeight.Bold)
        content()
    }
}

@Composable fun Button(onClick: () -> Unit, modifier: Modifier = Modifier, enabled: Boolean = true, content: @Composable RowScope.() -> Unit) {
    Row(modifier.height(32.dp).background(MaterialTheme.colorScheme.surfaceVariant, RoundedCornerShape(1.dp))
        .clickable(enabled = enabled, onClick = onClick).padding(horizontal = 14.dp),
        verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.Center) {
        CompositionLocalProvider(LocalContentColor provides MaterialTheme.colorScheme.onSurface.copy(alpha = if (enabled) 1f else .7f)) {
            Row(Modifier.monochrome(MaterialTheme.colorScheme.onSurface.copy(alpha = if (enabled) 1f else .7f))) {
                ProvideTextStyle(MaterialTheme.typography.labelLarge) { content() }
            }
        }
    }
}

@Composable fun AccentButton(text: String, enabled: Boolean = true, color: Color = MaterialTheme.colorScheme.primary, onClick: () -> Unit) {
    Box(Modifier.height(32.dp).background(color.copy(alpha = if (enabled) 1f else .5f), RoundedCornerShape(1.dp))
        .clickable(enabled = enabled, onClick = onClick).padding(horizontal = 14.dp), contentAlignment = Alignment.Center) {
        val foreground = readableForeground(color)
        Text(text, Modifier.monochrome(foreground), color = foreground, style = MaterialTheme.typography.labelLarge)
    }
}

fun Modifier.monochrome(color: Color): Modifier = graphicsLayer { compositingStrategy = CompositingStrategy.Offscreen }
    .drawWithContent { drawContent(); drawRect(color, blendMode = BlendMode.SrcIn) }

@Composable fun SmallInput(value: String, change: (String) -> Unit, modifier: Modifier = Modifier, secret: Boolean = false, multiline: Boolean = false) {
    val frame = if (multiline) Modifier else Modifier.border(2.dp, MaterialTheme.colorScheme.onSurfaceVariant)
    BasicTextField(value, change, modifier.background(MaterialTheme.colorScheme.surfaceVariant)
        .then(frame).padding(horizontal = 5.dp, vertical = 4.dp),
        textStyle = MaterialTheme.typography.bodyMedium.copy(color = MaterialTheme.colorScheme.onSurface,
            fontFamily = if (multiline) FontFamily.Monospace else WindowsFont),
        cursorBrush = SolidColor(MaterialTheme.colorScheme.primary), singleLine = !multiline,
        visualTransformation = if (secret) PasswordVisualTransformation() else VisualTransformation.None)
}
@Composable fun SmallCheck(checked: Boolean, text: String, change: (Boolean) -> Unit, modifier: Modifier = Modifier) {
    Row(modifier.clickable { change(!checked) }.height(22.dp), verticalAlignment = Alignment.CenterVertically) {
        Box(Modifier.size(11.dp).background(if (checked) MaterialTheme.colorScheme.onSurface else Color.White)
            .border(1.dp, MaterialTheme.colorScheme.outline), contentAlignment = Alignment.Center) {
            if (checked) UiGlyph(Glyph.Close, Modifier.size(11.dp), MaterialTheme.colorScheme.background)
        }
        Spacer(Modifier.width(4.dp)); Text(text)
    }
}

@Composable fun hintColor(): Color = if (MaterialTheme.colorScheme.background.luminance() < .5f) Color(0xFF89DCEB) else Color(0xFF006570)
@Composable fun warningColor(): Color = if (MaterialTheme.colorScheme.background.luminance() < .5f) Color(0xFFF9E2AF) else Color(0xFF805000)
fun contrastRatio(a: Color, b: Color): Float = (maxOf(a.luminance(), b.luminance()) + .05f) / (minOf(a.luminance(), b.luminance()) + .05f)
fun readableForeground(background: Color): Color {
    val dark = Color(0xFF172033)
    return if (contrastRatio(dark, background) >= contrastRatio(Color.White, background)) dark else Color.White
}
