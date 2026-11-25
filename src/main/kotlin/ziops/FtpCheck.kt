package ziops

import androidx.compose.foundation.*
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.text.selection.SelectionContainer
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.ui.*
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.unit.dp
import androidx.compose.ui.window.*
import java.util.Locale

data class FtpEntry(val name: String, val directory: Boolean, val size: Long)
fun readableSize(bytes: Long): String {
    if (bytes < 1024) return "$bytes Б"
    var amount = bytes.toDouble()
    val units = listOf("Б", "КБ", "МБ", "ГБ", "ТБ")
    var index = 0
    while (amount >= 1024 && index < units.lastIndex) { amount /= 1024; index++ }
    return String.format(Locale.ROOT, "%.1f %s", amount, units[index])
}
fun ftpListing(path: String, entries: List<FtpEntry>): String = buildString {
    appendLine("Открытая папка: $path")
    appendLine("Найдено: папок — ${entries.count { it.directory }}, файлов — ${entries.count { !it.directory }}.")
    if (entries.isEmpty()) appendLine("Папка пуста.") else {
        appendLine("Содержимое папки:")
        entries.sortedWith(compareBy<FtpEntry> { !it.directory }.thenBy { it.name.lowercase() }).forEach {
            appendLine(if (it.directory) "  [Папка] ${it.name}/" else "  [Файл] ${it.name} — ${readableSize(it.size)}")
        }
    }
    append("Подключение работает. Указанная папка доступна для чтения.")
}
fun checkFtp(m: DesktopModel) {
    if (m.busy) return
    m.ftpResult = "Подключение к FTP…"
    m.work {
        try {
            val result = ServerFiles(m.settings).use { server ->
                val current = server.ftp.printWorkingDirectory() ?: error("FTP не вернул текущую папку")
                val entries = server.ftp.listFiles()
                check(server.ftp.replyCode in 200..299) { "Список папки недоступен: ${server.ftp.replyString.trim()}" }
                ftpListing(current, entries.filter { it.name !in listOf(".", "..") }.map { FtpEntry(it.name, it.isDirectory, it.size) })
            }
            m.publish { if (m.ftpResult != null) m.ftpResult = result; m.append(4, result) }
        } catch (error: Exception) {
            m.publish { if (m.ftpResult != null) m.ftpResult = "Ошибка проверки FTP: ${error.message}" }
            throw error
        }
    }
}
@Composable fun FtpResultWindow(m: DesktopModel) {
    DialogWindow(onCloseRequest = { m.ftpResult = null }, title = "Проверка FTP и базовой папки", state = rememberDialogState(width = 760.dp, height = 540.dp)) {
        Surface(Modifier.fillMaxSize(), color = MaterialTheme.colorScheme.background) {
            Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                if (m.busy) LinearProgressIndicator(Modifier.fillMaxWidth())
                val scroll = rememberScrollState()
                Box(Modifier.weight(1f).fillMaxWidth().border(1.dp, MaterialTheme.colorScheme.outline).padding(10.dp)) {
                    SelectionContainer { Text(m.ftpResult.orEmpty(), Modifier.fillMaxSize().padding(end = 12.dp).verticalScroll(scroll), style = MaterialTheme.typography.bodyMedium.copy(fontFamily = FontFamily.Monospace)) }
                    VerticalScrollbar(rememberScrollbarAdapter(scroll), Modifier.align(Alignment.CenterEnd).fillMaxHeight())
                }
                Button(onClick = { m.ftpResult = null }) { Text("Закрыть") }
            }
        }
    }
}
