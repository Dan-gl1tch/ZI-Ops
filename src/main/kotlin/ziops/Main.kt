package ziops

import androidx.compose.foundation.*
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.selection.SelectionContainer
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.*
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.input.key.*
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.*
import androidx.compose.ui.window.*
import androidx.compose.ui.res.painterResource
import kotlinx.coroutines.*
import kotlinx.serialization.json.*
import java.nio.file.*
import java.net.URI
import javax.swing.JFileChooser
import java.util.concurrent.Executors
import java.util.concurrent.Future
import java.awt.Desktop

val green = Color(0xFFA6E3A1)
val yellow = Color(0xFFF9E2AF)
val purple = Color(0xFFCBA6F7)
private val labels = listOf("Вайп", "Судная ночь", "RCON", "Плагины", "Настройки", "Поддержать автора", "Консоль сервера")

fun main(args: Array<String>) {
    if (args.contains("--self-test")) { selfTest(); return }
    application {
        val scope = rememberCoroutineScope()
        val m = remember { DesktopModel { action -> scope.launch { action() } } }
        DisposableEffect(Unit) { onDispose { m.close() } }
        Window(onCloseRequest = { if (m.saveBeforeExit()) { m.close(); exitApplication() } }, title = "ZI-Ops", icon = painterResource("zi-ops.png"), state = rememberWindowState(width = 1066.dp, height = 940.dp)) {
            MaterialTheme(colorScheme = if (m.dark) OriginalDark else OriginalLight, typography = OriginalTypography) {
                if (m.ftpResult != null) FtpResultWindow(m)
                Surface(Modifier.fillMaxSize(), color = MaterialTheme.colorScheme.background) {
                    Column(Modifier.padding(horizontal = 29.dp)) {
                        Box(Modifier.fillMaxWidth().height(72.dp)) {
                            Row(Modifier.align(Alignment.CenterStart).padding(end = if (m.tab == 0) 98.dp else 0.dp).horizontalScroll(rememberScrollState()), horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                                listOf(0, 1, 2, 6, 3, 5, 4).forEach { index ->
                                    val title = labels[index]
                                    Box(Modifier.width(listOf(77, 118, 80, 100, 114, 161, 147)[index].dp).height(44.dp).border(if (m.tab == index) 2.dp else 1.dp,
                                        if (m.tab == index) MaterialTheme.colorScheme.onSurface else MaterialTheme.colorScheme.outline, RoundedCornerShape(3.dp))
                                        .background(if (m.tab == index) MaterialTheme.colorScheme.background else MaterialTheme.colorScheme.surfaceVariant)
                                        .clickable { m.tab = index }, contentAlignment = Alignment.Center) {
                                        val foreground = if (m.tab == index) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.onSurface
                                        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(5.dp)) {
                                            UiGlyph(TabGlyphs[index], Modifier.size(15.dp), if (m.dark) Color.White else Color.Black)
                                            Text(title, style = MaterialTheme.typography.labelLarge.copy(fontSize = 12.sp), color = foreground)
                                        }
                                    }
                                }
                            }
                            if (m.tab == 0) Box(Modifier.align(Alignment.CenterEnd).offset(x = 5.dp).width(89.dp).height(32.dp)
                                .background(MaterialTheme.colorScheme.surfaceVariant).clickable { m.notice = true }, contentAlignment = Alignment.Center) {
                                Text("⚠ Важное", Modifier.monochrome(MaterialTheme.colorScheme.onSurface), style = MaterialTheme.typography.labelLarge.copy(fontSize = 12.sp))
                            }
                        }
                        Box(Modifier.weight(1f).fillMaxWidth()) {
                            when (m.tab) { 0 -> WipeView(m); 1 -> JudgmentView(m); 2 -> RconView(m); 3 -> PluginsView(m); 4 -> SettingsView(m); 5 -> SupportView(); 6 -> ServerConsoleView(m) }
                            if (m.notice) NoticeView { m.notice = false }
                        }
                        Box(Modifier.fillMaxWidth().height(55.dp), contentAlignment = Alignment.BottomCenter) {
                            Text("Версия $APP_VERSION  •  Автор: danilmine_D47", Modifier.padding(bottom = 10.dp), style = MaterialTheme.typography.bodySmall)
                        }
                    }
                    m.confirm?.let { pending -> AlertDialog(onDismissRequest = { m.confirm = null }, title = { Text("Проверка действий") },
                        text = { Text(pending.first, Modifier.heightIn(max = 500.dp).verticalScroll(rememberScrollState())) },
                        confirmButton = { Button(onClick = { m.confirm = null; m.work(pending.second) }) { Text("Выполнить") } },
                        dismissButton = { Button(onClick = { m.confirm = null }) { Text("Отмена") } }) }
                }
            }
        }
    }
}

class DesktopModel(private val ui: (() -> Unit) -> Unit) : AutoCloseable {
    val settings = openApplicationSettings()
    init {
        for ((key, value) in mapOf("ftp_port" to "21", "ftp_base" to "/", "rcon_port" to "28016", "wipe_worldsize" to "4250",
            "wipe_restart_sec" to "60", "wipe_restart_msg" to "Вайп сервера! Рестарт через 60 секунд...", "plugins_server_path" to "oxide/plugins/")) {
            if (settings[key].isBlank()) settings.set(key, value)
        }
        if (settings["wipe_seed"].isBlank()) settings.set("wipe_seed", kotlin.random.Random.nextInt(1, Int.MAX_VALUE).toString())
        if (settings["wipe_random_seed"].isBlank()) settings.set("wipe_random_seed", true)
        if (settings["rcon_random_seed"].isBlank()) settings.set("rcon_random_seed", true)
    }
    var tab by mutableIntStateOf(0)
    var revision by mutableIntStateOf(0)
    var dark by mutableStateOf(settings["theme"] != "light")
    var busy by mutableStateOf(false)
    var notice by mutableStateOf(false)
    var confirm by mutableStateOf<Pair<String, () -> Unit>?>(null)
    val logs = List(7) { mutableStateListOf<String>() }
    val availableCpus = Runtime.getRuntime().availableProcessors().coerceAtLeast(1)
    val backgroundWorkers = ((availableCpus + 2) / 3).coerceIn(1, 4)
    val networkExecutor = Executors.newFixedThreadPool(backgroundWorkers)
    val executor = Executors.newSingleThreadExecutor()
    var task: Future<*>? = null
    var connected by mutableStateOf(false)
    var query by mutableStateOf<Map<String, String>>(emptyMap())
    var queryStatus by mutableStateOf("Нет данных")
    var pluginRows by mutableStateOf<List<List<String>>>(emptyList())
    var pluginsChecked by mutableIntStateOf(0)
    var pluginsTotal by mutableIntStateOf(0)
    var pluginOperation by mutableStateOf("Проверено")
    var ftpResult by mutableStateOf<String?>(null)
    val rcon = Rcon({ text -> ui { append(2, text) } }, { text -> ui { append(6, text) } }, { value -> ui { connected = value } })
    fun append(index: Int, message: String) { logs[index].add(message); while (logs[index].size > 1000) logs[index].removeAt(0) }
    fun work(block: () -> Unit) {
        if (busy) return
        busy = true
        val index = tab
        task = executor.submit {
            try { block(); if (index != 2 && index != 6) ui { append(index, "Операция завершена") } }
            catch (error: Exception) { ui { append(index, "Ошибка: ${error.cause?.message ?: error.message}") } }
            finally { ui { busy = false; connected = rcon.connected } }
        }
    }
    fun publish(action: () -> Unit) = ui(action)
    fun log(message: String) { val index = tab; ui { append(index, message) } }
    fun pluginLog(message: String) { ui { append(3, message) } }
    fun save() { runCatching { settings.save() }.onSuccess { append(tab, "Настройки сохранены") }.onFailure { append(tab, "Ошибка сохранения: ${it.message}") } }
    fun saveQuietly() { runCatching { settings.save() }.onFailure { append(tab, "Ошибка сохранения размера лога: ${it.message}") } }
    fun saveBeforeExit(): Boolean = runCatching { settings.save() }.fold({ true }, {
        javax.swing.JOptionPane.showMessageDialog(null, "Не удалось сохранить настройки приложения: ${it.message}", "ZI-Ops", javax.swing.JOptionPane.ERROR_MESSAGE)
        false
    })
    fun send(command: String) = work { for (item in splitCommands(command)) { check(!Thread.currentThread().isInterrupted); ui { append(2, "> $item") }; rcon.send(item) } }
    fun preview(action: () -> Pair<String, () -> Unit>) { runCatching(action).onSuccess { confirm = it }.onFailure { append(tab, "Ошибка: ${it.message}") } }
    override fun close() { task?.cancel(true); rcon.close(); executor.shutdownNow(); networkExecutor.shutdownNow() }
}

fun choose(save: Boolean = false): Path? {
    val dialog = JFileChooser()
    val result = if (save) dialog.showSaveDialog(null) else dialog.showOpenDialog(null)
    return if (result == JFileChooser.APPROVE_OPTION) dialog.selectedFile.toPath() else null
}
fun open(url: String) { Desktop.getDesktop().browse(URI(url)) }

@Composable fun Input(m: DesktopModel, key: String, modifier: Modifier = Modifier, secret: Boolean = false) {
    var text by remember(key, m.revision) { mutableStateOf(m.settings[key]) }
    SmallInput(text, { text = it; m.settings.set(key, it) }, modifier.height(27.dp), secret)
}
@Composable fun Check(m: DesktopModel, key: String, label: String, modifier: Modifier = Modifier) {
    var checked by remember(key, m.revision) { mutableStateOf(m.settings.flag(key)) }
    SmallCheck(checked, label, { checked = it; m.settings.set(key, it) }, modifier)
}
@Composable fun LogPanel(m: DesktopModel, index: Int, modifier: Modifier = Modifier, title: String = "Лог") {
    val scroll = rememberScrollState()
    val horizontal = rememberScrollState()
    LaunchedEffect(m.logs[index].size) { scroll.scrollTo(scroll.maxValue) }
    Section(title, modifier) {
        Box(Modifier.weight(1f).fillMaxWidth()) {
            SelectionContainer { Text(m.logs[index].joinToString("\n"), Modifier.fillMaxSize().padding(end = 12.dp, bottom = 12.dp).verticalScroll(scroll).horizontalScroll(horizontal),
                style = MaterialTheme.typography.bodySmall.copy(fontFamily = FontFamily.Monospace), softWrap = false) }
            VerticalScrollbar(rememberScrollbarAdapter(scroll), Modifier.align(Alignment.CenterEnd).fillMaxHeight().padding(bottom = 12.dp))
            HorizontalScrollbar(rememberScrollbarAdapter(horizontal), Modifier.align(Alignment.BottomStart).fillMaxWidth().padding(end = 12.dp))
        }
    }
}
@Composable fun Status(m: DesktopModel, modifier: Modifier = Modifier) {
    Row(modifier, horizontalArrangement = Arrangement.spacedBy(10.dp), verticalAlignment = Alignment.CenterVertically) {
        Text(if (m.busy) "Выполняется…" else "Готов", style = MaterialTheme.typography.bodySmall)
        Box(Modifier.width(200.dp).height(18.dp).border(1.dp, MaterialTheme.colorScheme.outline).background(MaterialTheme.colorScheme.surfaceVariant)) {
            if (m.busy) LinearProgressIndicator(Modifier.fillMaxSize())
        }
    }
}
@Composable fun ScrollColumn(modifier: Modifier = Modifier, content: @Composable ColumnScope.() -> Unit) {
    val state = rememberScrollState()
    Box(modifier.fillMaxSize()) {
        Column(Modifier.fillMaxSize().padding(end = 14.dp).verticalScroll(state), verticalArrangement = Arrangement.spacedBy(14.dp), content = content)
        VerticalScrollbar(rememberScrollbarAdapter(state), Modifier.align(Alignment.CenterEnd).fillMaxHeight())
    }
}
