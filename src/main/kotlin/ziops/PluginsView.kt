package ziops

import androidx.compose.foundation.*
import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.*
import androidx.compose.ui.unit.*
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.semantics.*
import androidx.compose.ui.draw.clip
import androidx.compose.foundation.shape.RoundedCornerShape
import kotlinx.serialization.json.*
import java.nio.file.Files

@Composable fun PluginsView(m: DesktopModel) {
    var sources by remember(m.revision) { mutableStateOf(m.settings.array("plugins")) }
    var sortColumn by remember { mutableIntStateOf(0) }
    var reverse by remember { mutableStateOf(false) }
    fun replace(value: JsonArray) { sources = value; m.settings.set("plugins", value) }
    Column(Modifier.fillMaxSize(), verticalArrangement = Arrangement.spacedBy(10.dp)) {
        Section("⌕ Установленные плагины на сервере", Modifier.weight(1.126f)) {
            Spacer(Modifier.height(3.dp))
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.CenterVertically) {
                Text("Путь на сервер"); Input(m, "plugins_server_path", Modifier.width(250.dp))
                AccentButton("⌕ Проверить версии", !m.busy) { m.work { scanPlugins(m, sources) } }
                Text("(скачивает .cs файлы, читает версию)", color = hintColor(), style = MaterialTheme.typography.bodySmall)
            }
            Spacer(Modifier.height(4.dp))
            val headers = listOf("Файл", "Название", "Автор", "Текущая", "Последняя", "Кастомный", "Статус")
            Column(Modifier.weight(1f).fillMaxWidth().border(1.dp, MaterialTheme.colorScheme.onSurfaceVariant).background(MaterialTheme.colorScheme.surfaceVariant)) {
                Row(Modifier.fillMaxWidth().height(27.dp).background(MaterialTheme.colorScheme.surfaceVariant)) {
                    headers.forEachIndexed { index, name -> Box(Modifier.weight(1f).fillMaxHeight().clickable {
                        if (sortColumn == index) reverse = !reverse else { sortColumn = index; reverse = false }
                    }, contentAlignment = Alignment.Center) { Text(name + if (sortColumn == index) (if (reverse) " ▼" else " ▲") else "", fontWeight = FontWeight.Bold) } }
                }
                val scroll = rememberScrollState()
                Box(Modifier.weight(1f)) {
                    Column(Modifier.fillMaxSize().padding(end = 12.dp).verticalScroll(scroll)) {
                        val sorted = m.pluginRows.sortedBy { it.getOrElse(sortColumn) { "" }.lowercase() }.let { if (reverse) it.reversed() else it }
                        sorted.forEach { row -> Row(Modifier.fillMaxWidth().heightIn(min = 30.dp)) {
                            row.forEachIndexed { index, text ->
                                Box(Modifier.weight(1f).height(30.dp).padding(horizontal = 4.dp), contentAlignment = if (index == 5) Alignment.Center else Alignment.CenterStart) {
                                    if (index == 5) {
                                        val key = row[0].removeSuffix(".cs").lowercase()
                                        val custom = m.settings.array("custom_plugins").map { it.jsonPrimitive.content }.toSet()
                                        Box(Modifier.size(20.dp).clip(RoundedCornerShape(4.dp)).background(MaterialTheme.colorScheme.surface)
                                            .border(2.dp, MaterialTheme.colorScheme.onSurfaceVariant, RoundedCornerShape(4.dp))
                                            .semantics { role = Role.Checkbox; stateDescription = if (key in custom) "Кастомный" else "Обычный"; contentDescription = "Кастомный плагин ${row[0]}" }
                                            .clickable {
                                                val next = if (key in custom) custom - key else custom + key
                                                m.settings.set("custom_plugins", JsonArray(next.map(::JsonPrimitive))); m.revision++
                                            }, contentAlignment = Alignment.Center) {
                                            if (key in custom) UiGlyph(Glyph.Close, Modifier.size(12.dp), MaterialTheme.colorScheme.onSurface)
                                        }
                                    } else Text(text, maxLines = 1, style = MaterialTheme.typography.bodySmall)
                                }
                            }
                        } }
                    }
                    VerticalScrollbar(rememberScrollbarAdapter(scroll), Modifier.align(Alignment.CenterEnd).fillMaxHeight())
                }
            }
        }
        Section("▣ Автообновление плагинов по URL", Modifier.weight(1f)) {
            Text("Обновляются только устаревшие плагины. Новые версии кастомных сохраняются в Custom на ПК.", color = hintColor())
            Row(Modifier.fillMaxWidth()) {
                listOf("Название", "URL скачивания (.cs)", "Страница версии", "Путь на сервере").forEachIndexed { i, title -> Text(title, Modifier.weight(sourceWeights[i]), style = MaterialTheme.typography.bodySmall) }
                Spacer(Modifier.width(36.dp))
            }
            val scroll = rememberScrollState()
            Box(Modifier.weight(1f).fillMaxWidth()) {
                Column(Modifier.fillMaxSize().padding(end = 14.dp).verticalScroll(scroll), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    sources.forEachIndexed { index, element -> Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(5.dp), verticalAlignment = Alignment.CenterVertically) {
                        listOf("name", "url", "page", "remote").forEachIndexed { i, key ->
                            SmallInput(element.jsonObject[key]?.jsonPrimitive?.content.orEmpty(), { value ->
                                replace(JsonArray(sources.mapIndexed { n, row -> if (n == index) JsonObject(row.jsonObject + (key to JsonPrimitive(value))) else row }))
                            }, Modifier.weight(sourceWeights[i]).height(27.dp))
                        }
                        SquareButton(Glyph.Close, "Убрать источник обновления") { replace(JsonArray(sources.filterIndexed { n, _ -> n != index })) }
                    } }
                }
                VerticalScrollbar(rememberScrollbarAdapter(scroll), Modifier.align(Alignment.CenterEnd).fillMaxHeight())
            }
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Button(onClick = { replace(JsonArray(sources + buildJsonObject { put("name", ""); put("url", ""); put("page", ""); put("remote", "oxide/plugins/") })) }) { Text("+ Добавить") }
                Button(onClick = { choose(true)?.let { Files.writeString(it, sources.toString()) } }) { Text("▣ Сохранить список") }
                Button(onClick = { choose()?.let { path -> runCatching { json.parseToJsonElement(Files.readString(path)).jsonArray }.onSuccess(::replace).onFailure { m.log("Ошибка списка: ${it.message}") } } }) { Text("▱ Загрузить список") }
                Button(onClick = { replace(JsonArray(emptyList())) }) { Text("▤ Очистить") }
                Spacer(Modifier.weight(1f))
                AccentButton("▣ Обновить все", !m.busy) {
                    m.pluginOperation = "Обработано"; m.pluginsChecked = 0; m.pluginsTotal = sources.size
                    m.work { processPlugins(m.settings, sources, true, m::pluginLog) { done, total -> m.publish { m.pluginsChecked = done; m.pluginsTotal = total } } }
                }
            }
        }
        Box(Modifier.fillMaxWidth().height(18.dp).border(1.dp, MaterialTheme.colorScheme.outline).background(MaterialTheme.colorScheme.surfaceVariant)) {
            if (m.pluginsTotal > 0) LinearProgressIndicator(progress = { m.pluginsChecked.toFloat() / m.pluginsTotal }, modifier = Modifier.fillMaxSize())
        }
        Text("${m.pluginOperation}: ${m.pluginsChecked}/${m.pluginsTotal}", Modifier.align(Alignment.End), style = MaterialTheme.typography.bodySmall)
        ResizableLogPanel(m, 3, 180f)
    }
}
private val sourceWeights = listOf(1.1f, 5.2f, 1.6f, 1.4f)

private fun scanPlugins(m: DesktopModel, sources: JsonArray) {
    m.publish { m.pluginsChecked = 0; m.pluginsTotal = 0; m.pluginOperation = "Проверено"; m.pluginRows = emptyList() }
    ServerFiles(m.settings).use { server ->
        val folder = remotePath(server.base, m.settings["plugins_server_path"].ifBlank { "oxide/plugins/" })
        val entries = server.ftp.listFiles(folder)
        check(server.ftp.replyCode in 200..299) { "Не удалось прочитать папку плагинов" }
        val files = entries.filter { it.isFile && it.name.endsWith(".cs", true) }
        m.publish { m.pluginsTotal = files.size }
        val completion = java.util.concurrent.ExecutorCompletionService<List<String>>(m.networkExecutor)
        val jobs = mutableListOf<java.util.concurrent.Future<List<String>>>()
        val rows = mutableListOf<List<String>>()
        fun collect(future: java.util.concurrent.Future<List<String>>) {
            rows.add(future.get())
            val snapshot = rows.toList(); val done = rows.size
            m.publish { m.pluginRows = snapshot; m.pluginsChecked = done }
        }
        try {
            for (file in files) {
                check(!Thread.currentThread().isInterrupted)
                val installed = runCatching { pluginInfo(server.read("$folder/${file.name}").decodeToString()) ?: error("Не найдена Info") }
                val source = sources.firstOrNull { it.jsonObject["name"]?.jsonPrimitive?.content?.removeSuffix(".cs").equals(file.name.removeSuffix(".cs"), true) }?.jsonObject
                jobs.add(completion.submit(java.util.concurrent.Callable {
                    val info = installed.getOrNull()
                    if (info == null) {
                        m.pluginLog("${file.name}: ${installed.exceptionOrNull()?.message}")
                        listOf(file.name, "?", "?", "?", "—", "", "Неизвестно")
                    } else {
                        var latest = "—"; var status = "Неизвестно"
                        if (source != null) runCatching {
                            val url = source["url"]?.jsonPrimitive?.content.orEmpty()
                            val fetched = pluginInfo(versionDownload(url, m::pluginLog).decodeToString()) ?: error("Версия не найдена")
                            require(fetched.name.equals(info.name, true)) { "По ссылке другой плагин" }
                            latest = fetched.version; status = pluginVersionStatus(latest, info.version)
                        }.onFailure { if (it is InterruptedException) throw it; status = "Неизвестно"; m.pluginLog("${file.name}: ${it.message}") }
                        listOf(file.name, info.name, info.author, info.version, latest, "", status)
                    }
                }))
                while (true) collect(completion.poll() ?: break)
            }
            while (rows.size < files.size) collect(completion.take())
        } finally { jobs.forEach { if (!it.isDone) it.cancel(true) } }
    }
}

fun pluginVersionStatus(latest: String, installed: String): String = when {
    compareVersions(latest, installed) > 0 -> "Обновление"
    compareVersions(latest, installed) < 0 -> "Сверх последнего"
    else -> "Актуален"
}

private class SiteGate {
    val permit = java.util.concurrent.Semaphore(1)
    var nextRequest = 0L
    var interval = 3000L
}
private val siteGates = java.util.concurrent.ConcurrentHashMap<String, SiteGate>()
fun retryDelayMillis(value: String?, attempt: Int): Long {
    val seconds = value?.toLongOrNull()?.coerceAtLeast(0)?.coerceAtMost(86400)?.times(1000)
    val date = runCatching { java.time.ZonedDateTime.parse(value, java.time.format.DateTimeFormatter.RFC_1123_DATE_TIME).toInstant().toEpochMilli() - System.currentTimeMillis() }.getOrNull()
    return maxOf(30000L * (1L shl attempt.coerceIn(0, 3)), seconds ?: date ?: 0L)
}
fun versionDownload(url: String, log: (String) -> Unit = {}): ByteArray {
    val host = java.net.URI(url).host ?: error("Некорректная ссылка")
    val gate = siteGates.computeIfAbsent(host.lowercase()) { SiteGate() }
    gate.permit.acquire()
    try {
        for (attempt in 0..3) {
            while (true) {
                val wait = gate.nextRequest - System.currentTimeMillis()
                if (wait <= 0) break
                Thread.sleep(minOf(wait, 1000L))
            }
            gate.nextRequest = System.currentTimeMillis() + gate.interval
            try { return download(url) }
            catch (error: HttpFailure) {
                if (error.status != 429) throw error
                gate.interval = maxOf(gate.interval, 10000L)
                val delay = retryDelayMillis(error.retryAfter, attempt)
                gate.nextRequest = System.currentTimeMillis() + delay
                if (attempt == 3) throw error
                log("$host: ограничение HTTP 429. Повтор ${attempt + 1}/3 через ${delay / 1000} сек.")
            }
        }
        error("Проверка не завершена")
    } finally { gate.permit.release() }
}
