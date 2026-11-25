package ziops

import androidx.compose.foundation.*
import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.*
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.input.key.*
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.*
import kotlinx.serialization.json.*
import kotlinx.coroutines.*
import java.nio.file.*

@Composable fun WipeView(m: DesktopModel) {
    Column(Modifier.fillMaxSize(), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        Section("🗺 Авто-вайп: Seed + Restart") {
            Check(m, "wipe_change_seed", "Сгенерировать новый seed и записать в server.cfg")
            Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(5.dp)) {
                Text("Шаблон server.cfg (локальный файл):", Modifier.width(235.dp))
                Input(m, "wipe_cfg_template", Modifier.weight(1f))
                Button(onClick = { choose()?.let { m.settings.set("wipe_cfg_template", it.toString()); m.revision++ } }) { Text("Обзор…") }
                Button(onClick = { runCatching { Files.readString(Path.of(m.settings["wipe_cfg_template"])) }.onSuccess { m.append(0, it) }.onFailure { m.append(0, "Ошибка: ${it.message}") } }) { Text("🧪 Проверить") }
            }
            Text("📥 Скачай server.cfg с сервера через FTP → укажи путь здесь  |  ☑ Оригинал на ПК НЕ изменится", color = hintColor())
            Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Check(m, "wipe_random_seed", "Случайный seed", Modifier.width(235.dp))
                Text("Seed:", Modifier.width(70.dp)); Input(m, "wipe_seed", Modifier.width(132.dp))
                Button(onClick = { randomSeed(m) }) { Text("1 Сгенерировать seed") }
                Button(onClick = { generateMap(m) }) { Text("2 Генерировать на RustMaps") }
            }
            Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                Text("Размер карты:", Modifier.width(225.dp)); Input(m, "wipe_worldsize", Modifier.width(72.dp))
                Text("(например: 3000, 3500, 4250, 5000 — как на rustmaps.com)", color = hintColor())
            }
            Text("▤ Если шаблон не указан — seed скопируется в буфер обмена", color = hintColor())
            Check(m, "wipe_restart", "Отправить рестарт через RCON после очистки")
            Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                Text("Таймер (сек):", Modifier.width(225.dp)); Input(m, "wipe_restart_sec", Modifier.width(72.dp))
            }
            Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                Text("Сообщение:", Modifier.width(225.dp)); Input(m, "wipe_restart_msg", Modifier.weight(1f))
            }
        }
        FileList(m, "wipe_files", "Файлы для удаления", Modifier.weight(1.45f))
        FileList(m, "wipe_folders", "Папки для очистки", Modifier.weight(1f))
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.CenterVertically) {
            AccentButton("▶ Запустить вайп", !m.busy) {
                m.preview {
                    if (m.settings.flag("wipe_random_seed")) randomSeed(m)
                    val plan = wipePlan(m.settings)
                    plan.first to {
                        plan.second()
                        if (m.settings.flag("wipe_restart")) {
                            m.rcon.send("say " + JsonPrimitive(m.settings["wipe_restart_msg"]))
                            m.rcon.send("restart ${m.settings["wipe_restart_sec"].toInt()}")
                        }
                    }
                }
            }
            AccentButton("▣ Остановить", m.busy, MaterialTheme.colorScheme.error) { m.task?.cancel(true) }
            Spacer(Modifier.weight(1f)); Status(m)
        }
        ResizableLogPanel(m, 0)
    }
}
private fun randomSeed(m: DesktopModel) { m.settings.set("wipe_seed", kotlin.random.Random.nextInt(1, Int.MAX_VALUE).toString()); m.revision++ }
private fun generateMap(m: DesktopModel) = m.work {
    val seed = m.settings["wipe_seed"].toInt(); val size = m.settings["wipe_worldsize"].toInt()
    require(seed > 0 && size in 1000..10000)
    m.log(download("https://api.rustmaps.com/v4/maps", m.settings["api_key"], buildJsonObject { put("seed", seed); put("size", size) }.toString()).decodeToString())
}

@Composable private fun FileList(m: DesktopModel, key: String, label: String, modifier: Modifier) {
    var text by remember(key, m.revision) { mutableStateOf(m.settings[key]) }
    val initial = remember(key) { text }
    Section(label, modifier) {
        val scroll = rememberScrollState()
        Box(Modifier.weight(1f).fillMaxWidth().background(MaterialTheme.colorScheme.surfaceVariant)) {
            SmallInput(text, { text = it; m.settings.set(key, it) }, Modifier.fillMaxSize().padding(end = 12.dp).verticalScroll(scroll), multiline = true)
            VerticalScrollbar(rememberScrollbarAdapter(scroll), Modifier.align(Alignment.CenterEnd).fillMaxHeight())
        }
        Row(horizontalArrangement = Arrangement.spacedBy(4.dp)) {
            Button(onClick = { choose()?.let { path -> runCatching { Files.readString(path) }.onSuccess { text = it; m.settings.set(key, it) }.onFailure { m.log("Ошибка: ${it.message}") } } }) { Text("Загрузить") }
            Button(onClick = { choose(true)?.let { path -> runCatching { Files.writeString(path, text) }.onFailure { m.log("Ошибка: ${it.message}") } } }) { Text("Сохранить") }
            Button(onClick = { text = initial; m.settings.set(key, initial) }) { Text("Сбросить") }
        }
    }
}

@Composable fun JudgmentView(m: DesktopModel) {
    var rows by remember(m.revision) { mutableStateOf(m.settings.array("judgment_files")) }
    fun replace(value: JsonArray) { rows = value; m.settings.set("judgment_files", value) }
    Column(Modifier.fillMaxSize(), verticalArrangement = Arrangement.spacedBy(14.dp)) {
        Section("Файлы судной ночи", Modifier.weight(2f)) {
            Text("Начало: установить при включении. Конец: установить при выключении.\nНа противоположном этапе файл удаляется. Обе галочки — установить на обоих этапах; без галочек — не трогать.")
            ScrollColumn(Modifier.weight(1f).background(MaterialTheme.colorScheme.background)) {
                rows.forEachIndexed { index, element ->
                    val row = element.jsonObject
                    fun edit(key: String, value: JsonElement) = replace(JsonArray(rows.mapIndexed { i, item -> if (i == index) JsonObject(item.jsonObject + (key to value)) else item }))
                    Column(verticalArrangement = Arrangement.spacedBy(5.dp)) {
                        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                            Button(onClick = { choose()?.let { edit("local", JsonPrimitive(it.toString())) } }) { Text("Обзор…") }
                            Text(runCatching { Path.of(row["local"]?.jsonPrimitive?.content.orEmpty()).fileName?.toString() }.getOrNull().orEmpty(), Modifier.weight(1f))
                            SmallCheck(row["start"]?.jsonPrimitive?.booleanOrNull == true, "Начало ночи", { edit("start", JsonPrimitive(it)) })
                            SmallCheck(row["end"]?.jsonPrimitive?.booleanOrNull == true, "Конец ночи", { edit("end", JsonPrimitive(it)) })
                            SquareButton(Glyph.Close, "Убрать файл") { replace(JsonArray(rows.filterIndexed { i, _ -> i != index })) }
                        }
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Text("Куда/откуда:", Modifier.width(100.dp))
                            SmallInput(row["folder"]?.jsonPrimitive?.content.orEmpty(), { edit("folder", JsonPrimitive(it)) }, Modifier.weight(1f).height(27.dp))
                        }
                    }
                }
            }
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Button(onClick = { replace(JsonArray(rows + buildJsonObject { put("local", ""); put("folder", "oxide/plugins/"); put("start", false); put("end", false) })) }) { Text("+ Добавить файл") }
                Button(onClick = { m.save() }) { Text("Сохранить список") }
            }
            Text("Меняются только точные файлы из списка. Остальные файлы и папки не удаляются.", color = hintColor())
        }
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.CenterVertically) {
            AccentButton("Включить судную ночь", !m.busy, yellow) { m.preview { judgmentPlan(m.settings, rows, true, m::log) } }
            AccentButton("Выключить судную ночь", !m.busy, green) { m.preview { judgmentPlan(m.settings, rows, false, m::log) } }
            Spacer(Modifier.weight(1f)); Status(m)
        }
        ResizableLogPanel(m, 1, 230f)
    }
}

@Composable fun RconView(m: DesktopModel) {
    var command by remember { mutableStateOf("") }
    fun send() { if (!m.busy && command.isNotBlank()) { val value = command; command = ""; m.send(value) } }
    LaunchedEffect(Unit) {
        while (true) {
            if (m.settings["query_port"].isNotBlank()) {
                runCatching { withContext(Dispatchers.IO) { queryDetails(m.settings) } }
                    .onSuccess { m.query = it; m.queryStatus = "Сервер отвечает" }.onFailure { m.queryStatus = "Сервер не ответил" }
            }
            delay(10000)
        }
    }
    Column(Modifier.fillMaxSize(), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        Section("Подключение") {
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.CenterVertically) {
                Text(if (m.connected) "Подключено" else "Не подключено", fontWeight = FontWeight.Bold, modifier = Modifier.width(112.dp))
                Button(enabled = !m.busy, onClick = { m.work { m.rcon.connect(m.settings) } }) { Text("◉ Подключиться") }
                Button(onClick = { m.rcon.close(); m.connected = false }) { Text("✖ Отключиться") }
                Button(enabled = !m.busy, onClick = { m.send("status") }) { Text("🧪 Проверить") }
            }
        }
        Section("Быстрые команды") {
            Row(Modifier.horizontalScroll(rememberScrollState()), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Button(onClick = { open("https://rustmaps.com") }) { Text("◉ RustMaps") }
                AccentButton("▣ Сохранить мир", !m.busy) { m.send("server.save") }
                AccentButton("▣ Рестарт 60с", !m.busy, yellow) { m.send("restart 60") }
                AccentButton("▣ Объявление", !m.busy, green) { command = "say \"Сообщение от администратора\"" }
                AccentButton("♟ Статус", !m.busy, purple) { m.send("status") }
                AccentButton("▧ Seed", !m.busy, purple) { m.send("server.seed") }
                AccentButton("⬟ Остановить", !m.busy, MaterialTheme.colorScheme.error) {
                    m.confirm = "Остановить сервер командой quit?" to { m.rcon.send("quit") }
                }
            }
        }
        Section("Ручной ввод") {
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.CenterVertically) {
                CommandInput(command, { command = it }, ::send, Modifier.weight(1f))
                AccentButton("Отправить", !m.busy) { send() }
            }
        }
        Section("Быстрый вайп через RCON") {
            Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Check(m, "rcon_random_seed", "Случайный", Modifier.width(88.dp)); Text("Seed:", Modifier.width(62.dp)); Input(m, "wipe_seed", Modifier.width(132.dp))
                Button(onClick = { randomSeed(m) }) { Text("1") }
                Spacer(Modifier.width(30.dp)); Button(onClick = { generateMap(m) }) { Text("2 RustMaps") }
            }
            Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Text("Размер:", Modifier.width(84.dp)); Input(m, "wipe_worldsize", Modifier.width(72.dp))
                Text("Таймер:", Modifier.width(132.dp)); Input(m, "wipe_restart_sec", Modifier.width(72.dp)); Spacer(Modifier.weight(1f))
                AccentButton("▧ Сменить seed/worldsize + Restart", !m.busy) {
                    m.preview {
                        if (m.settings.flag("rcon_random_seed")) randomSeed(m)
                        val seed = m.settings["wipe_seed"].toInt(); val size = m.settings["wipe_worldsize"].toInt(); val time = m.settings["wipe_restart_sec"].toInt()
                        require(seed > 0 && size in 1000..10000 && time >= 0)
                        "Seed $seed, размер $size, рестарт через $time сек." to {
                            for (cmd in listOf("server.save", "server.seed $seed", "server.worldsize $size", "restart $time")) m.rcon.send(cmd)
                        }
                    }
                }
            }
        }
        Row(Modifier.weight(1f).fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(6.dp)) {
            LogPanel(m, 2, Modifier.weight(2f).fillMaxHeight(), "Консоль RCON")
            Section("Query — статус сервера", Modifier.weight(1f).fillMaxHeight()) {
                Column(Modifier.weight(1f).verticalScroll(rememberScrollState())) {
                Text(m.queryStatus, fontWeight = FontWeight.Bold)
                Spacer(Modifier.height(10.dp))
                for (key in listOf("Название", "Карта", "Игроки", "Время ответа", "Версия сервера", "Последний ответ")) {
                    Row(Modifier.padding(vertical = 6.dp)) { Text(key, Modifier.width(112.dp)); Text(m.query[key] ?: "—", fontWeight = FontWeight.Bold) }
                }
                Spacer(Modifier.height(18.dp)); Text("Обновление каждые 10 секунд,\nпока открыта вкладка RCON.")
                }
            }
        }
    }
}
