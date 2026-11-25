package ziops

import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.Alignment
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.*
import java.nio.file.Files

@Composable fun SettingsView(m: DesktopModel) {
    ScrollColumn {
        Section("Оформление") {
            Row(horizontalArrangement = Arrangement.spacedBy(12.dp), verticalAlignment = Alignment.CenterVertically) {
                Button(onClick = { m.dark = !m.dark; m.settings.set("theme", if (m.dark) "dark" else "light") }) { Text(if (m.dark) "Тема: тёмная" else "Тема: светлая") }
                Text("Нажми, чтобы переключить светлую и тёмную тему.")
            }
        }
        Section("Производительность — автоматический режим") {
            Text("Доступно логических процессоров: ${m.availableCpus}  •  Исполнителей проверки сайтов: ${m.backgroundWorkers}")
            Spacer(Modifier.height(3.dp))
            Text("Число исполнителей подбирается автоматически: от 1 до 4. Проверки разных сайтов выполняются параллельно.\nЗапросы к одному сайту, FTP и изменения файлов выполняются последовательно. RCON и Query работают отдельно.")
            Spacer(Modifier.height(3.dp)); Text("Распределением потоков по ядрам управляет операционная система.")
        }
        Section("FTP Настройки") {
            SettingsField(m, "ftp_host", "Хост:")
            SettingsField(m, "ftp_port", "Порт:")
            SettingsField(m, "ftp_user", "Пользователь:")
            SettingsField(m, "ftp_pass", "Пароль:", true)
            SettingsField(m, "ftp_base", "Базовый путь:")
            Check(m, "ftps", "Использовать FTPS (TLS/SSL)")
            Spacer(Modifier.height(4.dp))
            Button(enabled = !m.busy, onClick = { checkFtp(m) }) { Text("Проверить FTP и базовую папку") }
        }
        Section("RCON Настройки") {
            SettingsField(m, "rcon_host", "Хост:"); SettingsField(m, "rcon_port", "Порт:")
            SettingsField(m, "rcon_pass", "Пароль:", true); SettingsField(m, "rcon_path", "Путь (опц.):")
            Check(m, "rcon_ssl", "Использовать SSL/TLS (wss://)")
        }
        Section("Query — публичный статус сервера") {
            SettingsField(m, "query_host", "Адрес:"); SettingsField(m, "query_port", "Query-порт:")
            Text("Обновление во вкладке RCON каждые 10 секунд. Укажите порт из панели хостинга.")
        }
        Section("RustMaps API") { SettingsField(m, "api_key", "API Key:", true) }
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Button(onClick = { m.save() }) { Text("▣ Сохранить настройки") }
            Button(enabled = !m.busy, onClick = { choose()?.let { path ->
                runCatching { m.settings.load(path); m.dark = m.settings["theme"] != "light"; m.revision++ }.onFailure { m.log("Ошибка: ${it.message}") }
            } }) { Text("▱ Импорт настроек") }
            Button(onClick = { choose(true)?.let { path ->
                runCatching { m.settings.export(path) }.onSuccess { m.log("Настройки экспортированы") }.onFailure { m.log("Ошибка экспорта: ${it.message}") }
            } }) { Text("Экспорт настроек") }
        }
        Text("Настройки хранятся в данных приложения и автоматически сохраняются при закрытии. Загрузить прежний config.json можно кнопкой «Импорт настроек».", style = MaterialTheme.typography.bodySmall)
        if (m.logs[4].isNotEmpty()) Text(m.logs[4].last().lineSequence().first(), style = MaterialTheme.typography.bodySmall)
    }
}

@Composable private fun SettingsField(m: DesktopModel, key: String, title: String, password: Boolean = false) {
    var reveal by remember { mutableStateOf(false) }
    Row(Modifier.fillMaxWidth().height(30.dp).padding(start = 4.dp), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(4.dp)) {
        Text(title, Modifier.width(if (key.startsWith("rcon")) 74.dp else 95.dp)); Input(m, key, Modifier.weight(1f), password && !reveal)
        if (password) SquareButton(Glyph.Eye, "Показать или скрыть пароль") { reveal = !reveal }
        else Spacer(Modifier.width(32.dp))
    }
}

@Composable fun SupportView() {
    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(16.dp)) {
        Section("♡ Поддержка ZI-Ops", Modifier.weight(1f).height(258.dp)) {
            Column(Modifier.padding(horizontal = 10.dp), verticalArrangement = Arrangement.spacedBy(18.dp)) {
                Text("Поддержать разработку", fontSize = 24.sp, fontWeight = FontWeight.Bold, modifier = Modifier.padding(top = 8.dp))
                Text("Ваша поддержка помогает развивать ZI-Ops,\nдобавлять возможности и исправлять ошибки.")
                AccentButton("♡ Поддержать через DonationAlerts") { open("https://www.donationalerts.com/r/danilmine_") }
                Text("Поддержка добровольная.\nВсе функции доступны бесплатно.")
            }
        }
        Section("Новости и сайт", Modifier.weight(1f).height(258.dp)) {
            Column(Modifier.padding(horizontal = 10.dp), verticalArrangement = Arrangement.spacedBy(14.dp)) {
                Text("Следите за ZI-Ops", fontSize = 24.sp, fontWeight = FontWeight.Bold, modifier = Modifier.padding(top = 8.dp))
                Text("Новости и обновления — в канале DanStudios47.")
                Button(onClick = { open("https://t.me/DanStudios47") }) { Text("Открыть Telegram-канал") }
                Text("На сайте — загрузка программы и предыдущие версии.")
                AccentButton("Сайт ZI-Ops ↗") { open("https://dan-gl1tch.github.io/ZI-Ops/") }
            }
        }
    }
}
