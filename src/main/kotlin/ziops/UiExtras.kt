package ziops

import androidx.compose.foundation.*
import androidx.compose.foundation.gestures.detectDragGestures
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.text.selection.SelectionContainer
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.*
import androidx.compose.ui.geometry.*
import androidx.compose.ui.graphics.*
import androidx.compose.ui.graphics.drawscope.*
import androidx.compose.ui.input.pointer.*
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.platform.LocalWindowInfo
import androidx.compose.ui.semantics.*
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.*
import java.awt.Cursor

enum class Glyph { Wipe, Moon, Terminal, Package, Settings, Heart, Server, Close, Eye }
val TabGlyphs = listOf(Glyph.Wipe, Glyph.Moon, Glyph.Terminal, Glyph.Package, Glyph.Settings, Glyph.Heart, Glyph.Server)

@Composable fun UiGlyph(glyph: Glyph, modifier: Modifier = Modifier, color: Color = MaterialTheme.colorScheme.onSurface) {
    Canvas(modifier) {
        withTransform({ scale(size.width / 24f, size.height / 24f, Offset.Zero) }) {
            fun line(x1: Float, y1: Float, x2: Float, y2: Float) = drawLine(color, Offset(x1, y1), Offset(x2, y2), 2f, StrokeCap.Round)
            when (glyph) {
                Glyph.Close -> { line(7f, 7f, 17f, 17f); line(17f, 7f, 7f, 17f) }
                Glyph.Terminal -> { drawRoundRect(color, Offset(2f, 4f), Size(20f, 16f), CornerRadius(2f), style = Stroke(1.8f)); line(6f, 8f, 10f, 12f); line(10f, 12f, 6f, 16f); line(13f, 16f, 18f, 16f) }
                Glyph.Server -> { for (y in listOf(3f, 10f, 17f)) { drawRoundRect(color, Offset(3f, y), Size(18f, 5f), CornerRadius(1f), style = Stroke(1.5f)); drawCircle(color, 1f, Offset(6f, y + 2.5f)); line(11f, y + 2.5f, 18f, y + 2.5f) } }
                Glyph.Package -> { val p = Path().apply { moveTo(3f, 7f); lineTo(12f, 2f); lineTo(21f, 7f); lineTo(21f, 18f); lineTo(12f, 23f); lineTo(3f, 18f); close() }; drawPath(p, color, style = Stroke(1.8f)); line(3f, 7f, 12f, 12f); line(12f, 12f, 21f, 7f); line(12f, 12f, 12f, 23f); line(7f, 4.5f, 17f, 9.5f) }
                Glyph.Wipe -> { line(15f, 3f, 7f, 14f); val p = Path().apply { moveTo(5f, 11f); lineTo(12f, 16f); lineTo(8f, 22f); lineTo(1f, 17f); close() }; drawPath(p, color, style = Stroke(1.8f)); line(4f, 17f, 7f, 19f) }
                Glyph.Moon -> { val p = Path().apply { moveTo(15f, 2f); cubicTo(2f, 1f, -1f, 18f, 11f, 22f); cubicTo(16f, 24f, 21f, 21f, 23f, 17f); cubicTo(12f, 20f, 7f, 8f, 15f, 2f); close() }; drawPath(p, color, style = Stroke(1.8f)) }
                Glyph.Heart -> { val p = Path().apply { moveTo(12f, 21f); cubicTo(9f, 18f, 1f, 13f, 2f, 7f); cubicTo(3f, 1f, 10f, 1f, 12f, 6f); cubicTo(15f, 1f, 22f, 1f, 22f, 7f); cubicTo(23f, 13f, 15f, 18f, 12f, 21f); close() }; drawPath(p, color, style = Stroke(1.8f)) }
                Glyph.Settings -> { drawCircle(color, 7f, Offset(12f, 12f), style = Stroke(2f)); drawCircle(color, 3f, Offset(12f, 12f), style = Stroke(2f)); repeat(8) { rotate(it * 45f, Offset(12f, 12f)) { line(12f, 1f, 12f, 4f) } } }
                Glyph.Eye -> { val p = Path().apply { moveTo(1f, 12f); cubicTo(6f, 3f, 18f, 3f, 23f, 12f); cubicTo(18f, 21f, 6f, 21f, 1f, 12f); close() }; drawPath(p, color, style = Stroke(1.8f)); drawCircle(color, 3f, Offset(12f, 12f), style = Stroke(1.8f)) }
            }
        }
    }
}

@Composable fun SquareButton(glyph: Glyph, label: String, onClick: () -> Unit) {
    Box(Modifier.size(32.dp).background(MaterialTheme.colorScheme.surfaceVariant).clickable(onClick = onClick)
        .semantics { contentDescription = label }, contentAlignment = Alignment.Center) { UiGlyph(glyph, Modifier.size(17.dp)) }
}

@Composable fun ResizeHandle(m: DesktopModel, index: Int, current: Float, maxHeight: Float, change: (Float) -> Unit) {
    val density = LocalDensity.current.density
    val latest by rememberUpdatedState(current)
    Box(Modifier.fillMaxWidth().height(9.dp).pointerHoverIcon(PointerIcon(Cursor.getPredefinedCursor(Cursor.N_RESIZE_CURSOR)))
        .semantics { contentDescription = "Изменить высоту лога перетаскиванием" }
        .pointerInput(index, maxHeight, density) {
            detectDragGestures(onDragEnd = { m.settings.set("log_height_$index", latest.toString()); m.saveQuietly() }) { event, delta ->
                event.consume(); change((latest - delta.y / density).coerceIn(75f, maxHeight))
            }
        }, contentAlignment = Alignment.Center) {
        Box(Modifier.width(52.dp).height(3.dp).background(MaterialTheme.colorScheme.outline))
    }
}

@Composable fun ResizableLogPanel(m: DesktopModel, index: Int, initial: Float = 170f, title: String = "Лог") {
    val density = LocalDensity.current.density
    val windowHeight = LocalWindowInfo.current.containerSize.height / density
    val reserve = when (index) { 0 -> 720f; 3 -> 620f; else -> 400f }
    val maxHeight = (windowHeight - reserve).coerceAtLeast(100f)
    var height by remember(index) { mutableFloatStateOf(m.settings["log_height_$index"].toFloatOrNull() ?: initial) }
    val actual = height.coerceIn(75f, maxHeight)
    Column {
        ResizeHandle(m, index, actual, maxHeight) { height = it }
        LogPanel(m, index, Modifier.height(actual.dp), title)
    }
}

@Composable fun NoticeView(close: () -> Unit) {
    Surface(Modifier.fillMaxSize().padding(8.dp).border(2.dp, MaterialTheme.colorScheme.outline), color = MaterialTheme.colorScheme.background) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) { Text("Важное: карты и безопасность настроек", Modifier.weight(1f), fontSize = 17.sp, fontWeight = FontWeight.Bold); Button(onClick = close) { Text("Закрыть") } }
            Box(Modifier.weight(1f).background(MaterialTheme.colorScheme.surfaceVariant).padding(12.dp)) {
                ScrollColumn {
                    for ((title, body) in noticeSections) Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
                        Text(title, color = if (title.startsWith("Не передавайте")) warningColor() else hintColor(), fontWeight = FontWeight.Bold, fontSize = 16.sp)
                        SelectionContainer { Text(body, fontSize = 15.sp, lineHeight = 21.sp) }
                    }
                }
            }
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) { Button(onClick = { open("https://rustmaps.com") }) { Text("Открыть RustMaps") }; Button(onClick = { open("https://rustmaps.com/dashboard") }) { Text("Открыть Dashboard") } }
        }
    }
}

private val noticeSections = listOf(
    "Seed и Map Size" to "Некоторые серверы не используют параметры Seed и Map Size из server.cfg: они могут задаваться в панели хостинга или параметрах запуска. В таком случае программу можно использовать для генерации карты на RustMaps, а Seed и размер карты перенести в настройки сервера вручную.",
    "Как получить RustMaps API Key" to "Генерация карты на RustMaps доступна после добавления API-ключа во вкладке «Настройки».\n\n1. Откройте https://rustmaps.com и нажмите Sign in.\n2. После входа откройте https://rustmaps.com/dashboard.\n3. Скопируйте API key в поле «API Key» в разделе «RustMaps API». Сохраните настройки.",
    "Время генерации и лимиты" to "Генерация карты может занимать несколько минут, а при высокой нагрузке — дольше. Программа показывает ответ API о принятии запроса. Ход генерации смотрите в Dashboard RustMaps.\nЧисло одновременных генераций и месячные ограничения зависят от вашего аккаунта и подписки. Актуальные лимиты смотрите в своём аккаунте RustMaps.",
    "Ограничения RCON" to "Не все серверы и хостинги разрешают выполнять любые команды через RCON. Некоторые команды могут быть недоступны даже при успешном подключении. Если команда не выполняется, проверьте права и ограничения сервера или уточните их у хостинга.\nОтветы на отправленные команды находятся во вкладке RCON. Постоянный поток сообщений и ошибок сервера находится во вкладке «Консоль сервера».",
    "Доступ к настройкам приложения" to "Настройки сохраняются в папке данных приложения. На Windows это %LOCALAPPDATA%/ZI-Ops/config.json. Они могут содержать адрес сервера, логины и пароли FTP/RCON, а также RustMaps API Key, если вы их ввели.\n\nПередавая копию настроек другому человеку, вы предоставляете ему данные для доступа к серверу.",
    "Перед вайпом" to "Проверьте базовую папку FTP и точные пути удаления. Сделайте резервную копию нужных данных. Вайп удаляет выбранные файлы и содержимое выбранных папок. RCON-смена seed и рестарт сами по себе не удаляют файлы мира."
)

@Composable fun ServerConsoleView(m: DesktopModel) {
    Column(Modifier.fillMaxSize(), verticalArrangement = Arrangement.spacedBy(10.dp)) {
        Section("Консоль сервера • поток WebRCON") {
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.CenterVertically) {
                Text(if (m.connected) "Подключено" else "Не подключено", Modifier.weight(1f))
                Button(enabled = !m.busy, onClick = { m.work { m.rcon.connect(m.settings) } }) { Text("Подключиться") }
                Button(onClick = { m.rcon.close() }) { Text("Отключиться") }
                Button(onClick = { m.logs[6].clear() }) { Text("Очистить") }
            }
            Text("Здесь отображаются события, сохранения и ошибки плагинов, которые сервер передаёт через WebRCON.")
        }
        LogPanel(m, 6, Modifier.weight(1f).fillMaxWidth(), "Сообщения сервера")
    }
}
