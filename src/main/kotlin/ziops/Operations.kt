package ziops

import kotlinx.serialization.json.*
import java.net.DatagramPacket
import java.net.DatagramSocket
import java.net.InetAddress
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.nio.file.*
import java.time.LocalDateTime
import java.time.format.DateTimeFormatter

private fun lines(text: String) = text.lineSequence().map(String::trim).filter { it.isNotEmpty() && !it.startsWith('#') }.toList()
private fun backupRoot(): Path = Path.of("backups", LocalDateTime.now().format(DateTimeFormatter.ofPattern("yyyyMMdd-HHmmss-SSS"))).also { Files.createDirectories(it) }
private fun backup(server: ServerFiles, target: String, root: Path) {
    val entries = server.ftp.listFiles(target)
    if (entries.isEmpty()) {
        check(server.ftp.replyCode in listOf(226, 250, 550)) { "Не удалось проверить $target" }
        return
    }
    check(entries.size == 1 && entries[0].isFile) { "Ожидался обычный файл $target" }
    val local = root.resolve(target.trimStart('/')).normalize()
    require(local.startsWith(root))
    Files.createDirectories(local.parent)
    Files.write(local, server.read(target))
}

fun wipePlan(s: Settings): Pair<String, () -> Unit> {
    val base = s["ftp_base"].ifBlank { "/" }
    val files = lines(s["wipe_files"]).map { remotePath(base, it) }.distinct()
    val folders = lines(s["wipe_folders"]).map { remotePath(base, it) }.distinct()
    require(files.isNotEmpty() || folders.isNotEmpty() || s.flag("wipe_change_seed")) { "Список вайпа пуст" }
    val copySeed = s.flag("wipe_change_seed") && s["wipe_cfg_template"].isBlank()
    val cfg = if (s.flag("wipe_change_seed") && !copySeed) {
        val seed = s["wipe_seed"].toInt(); val size = s["wipe_worldsize"].toInt()
        require(seed > 0 && size in 1000..10000) { "Неверный seed или размер карты" }
        val original = Files.readString(Path.of(s["wipe_cfg_template"]))
        fun replaceSetting(text: String, key: String, value: Int): String {
            val pattern = Regex("(?m)^\\s*${Regex.escape(key)}\\s+[^\\r\\n]*")
            return if (pattern.containsMatchIn(text)) text.replace(pattern, "$key $value") else text.trimEnd() + "\n$key $value\n"
        }
        replaceSetting(replaceSetting(original, "server.seed", seed), "server.worldsize", size).toByteArray()
    } else null
    val cfgPath = remotePath(base, "server.cfg")
    val preview = (listOf("Удаление файлов:") + files + "Очистка папок (содержимое будет удалено):" + folders +
        if (cfg != null) listOf("Запись $cfgPath", "Проверьте путь server.cfg перед выполнением.") else emptyList()).joinToString("\n")
    return preview to {
        ServerFiles(s).use { server ->
            for (path in files) {
                check(!Thread.currentThread().isInterrupted) { "Операция остановлена" }
                val matches = server.ftp.listFiles(path)
                if (matches.isNotEmpty()) { check(matches.all { it.isFile }); check(server.ftp.deleteFile(path)) { "Не удалось удалить $path" } }
            }
            for (path in folders) {
                check(!Thread.currentThread().isInterrupted) { "Операция остановлена" }
                val contents = server.ftp.listFiles(path)
                check(server.ftp.replyCode in 200..299) { "Не удалось прочитать $path" }
                for (entry in contents) {
                    if (entry.name in listOf(".", "..")) continue
                    check(!entry.isSymbolicLink) { "Символьная ссылка в $path" }
                    val child = "$path/${entry.name}"
                    if (entry.isDirectory) server.deleteTree(child) else check(server.ftp.deleteFile(child)) { "Не удалось удалить $child" }
                }
            }
            if (cfg != null) { backup(server, cfgPath, backupRoot()); server.write(cfgPath, cfg) }
            if (copySeed) java.awt.Toolkit.getDefaultToolkit().systemClipboard.setContents(java.awt.datatransfer.StringSelection(s["wipe_seed"]), null)
        }
    }
}

fun judgmentPlan(s: Settings, rows: JsonArray, start: Boolean, log: (String) -> Unit): Pair<String, () -> Unit> {
    data class Entry(val target: String, val content: ByteArray?)
    val base = s["ftp_base"].ifBlank { "/" }
    val entries = rows.mapNotNull { element ->
        val row = element.jsonObject
        val on = row["start"]?.jsonPrimitive?.booleanOrNull == true
        val off = row["end"]?.jsonPrimitive?.booleanOrNull == true
        if (!on && !off) return@mapNotNull null
        val local = Path.of(row.getValue("local").jsonPrimitive.content)
        val folder = row.getValue("folder").jsonPrimitive.content
        val target = remotePath(base, folder.trimEnd('/') + "/" + local.fileName)
        Entry(target, if (if (start) on else off) Files.readAllBytes(local) else null)
    }
    require(entries.isNotEmpty()) { "Нет отмеченных файлов" }
    require(entries.map { it.target.lowercase() }.distinct().size == entries.size) { "Повторяются пути файлов" }
    return entries.joinToString("\n") { "${if (it.content == null) "Удалить" else "Загрузить"} ${it.target}" } to {
        ServerFiles(s).use { server ->
            val root = backupRoot()
            entries.forEach { backup(server, it.target, root) }
            for (entry in entries) {
                if (entry.content != null) server.write(entry.target, entry.content)
                else if (server.ftp.listFiles(entry.target).isNotEmpty()) check(server.ftp.deleteFile(entry.target)) { "Не удалось удалить ${entry.target}" }
                log(entry.target)
            }
            log("Завершено. Резервные копии: ${root.toAbsolutePath()}")
        }
    }
}

fun processPlugins(s: Settings, rows: JsonArray, update: Boolean, log: (String) -> Unit, progress: (Int, Int) -> Unit = { _, _ -> }) {
    val custom = (s.array("custom_plugins").map { it.jsonPrimitive.content } + lines(s["custom_plugins_text"]))
        .map { it.removeSuffix(".cs").lowercase().replace(" ", "") }.toSet()
    ServerFiles(s).use { server ->
        for ((index, element) in rows.withIndex()) {
            val row = element.jsonObject
            val filename = row["name"]?.jsonPrimitive?.content.orEmpty().let { if (it.endsWith(".cs")) it else "$it.cs" }
            try {
                require(filename != ".cs" && '/' !in filename && '\\' !in filename) { "Неверное имя плагина" }
                val folder = row["remote"]?.jsonPrimitive?.content.orEmpty().ifBlank { s["plugins_server_path"].ifBlank { "oxide/plugins" } }
                val target = remotePath(server.base, if (folder.endsWith(".cs", true)) folder else folder.trimEnd('/') + "/$filename")
                val installed = pluginInfo(server.read(target).decodeToString()) ?: error("Не найдена Info в установленном файле")
                val url = row["url"]?.jsonPrimitive?.content.orEmpty()
                require(url.isNotBlank()) { "Не задана прямая ссылка на .cs" }
                val downloaded = versionDownload(url, log)
                val latest = pluginInfo(downloaded.decodeToString()) ?: error("Ссылка вернула файл без Info")
                require(installed.name.equals(latest.name, true)) { "По ссылке другой плагин: ${latest.name}" }
                val newer = compareVersions(latest.version, installed.version) > 0
                log("$filename: ${installed.version} → ${latest.version}${if (newer) " • есть обновление" else " • актуален"}")
                if (update && newer) {
                    val key = filename.removeSuffix(".cs").lowercase().replace(" ", "")
                    if (key in custom || installed.name.lowercase().replace(" ", "") in custom) {
                        val path = Path.of("Custom", latest.version, filename)
                        Files.createDirectories(path.parent); Files.write(path, downloaded)
                        log("Кастомная версия сохранена: ${path.toAbsolutePath()}")
                    } else {
                        backup(server, target, backupRoot())
                        server.write(target, downloaded)
                        log("Обновлён $filename")
                    }
                }
            } catch (error: Exception) { if (error is InterruptedException) throw error; log("$filename: ${error.message}") }
            finally { progress(index + 1, rows.size) }
        }
    }
}

fun queryServer(s: Settings): String {
    val details = queryDetails(s)
    return "${details["Название"]} • ${details["Карта"]} • ${details["Игроки"]}"
}

fun queryDetails(s: Settings): Map<String, String> {
    val host = s["query_host"].ifBlank { s["rcon_host"] }
    val port = s["query_port"].toInt()
    val request = byteArrayOf(-1, -1, -1, -1, 0x54) + "Source Engine Query\u0000".toByteArray(Charsets.US_ASCII)
    DatagramSocket().use { socket ->
        val started = System.nanoTime()
        socket.soTimeout = 4000
        socket.connect(InetAddress.getByName(host), port)
        fun exchange(bytes: ByteArray): ByteArray {
            socket.send(DatagramPacket(bytes, bytes.size))
            val packet = DatagramPacket(ByteArray(65507), 65507)
            socket.receive(packet)
            return packet.data.copyOf(packet.length)
        }
        var data = exchange(request)
        require(data.size >= 5) { "Короткий ответ Query" }
        if (data[4] == 0x41.toByte()) {
            require(data.size >= 9)
            data = exchange(request + data.copyOfRange(5, 9))
        }
        require(data.size >= 6 && data[4] == 0x49.toByte()) { "Формат Query пока не поддерживается (возможно, составной ответ)" }
        val buffer = ByteBuffer.wrap(data).order(ByteOrder.LITTLE_ENDIAN)
        buffer.position(6)
        fun text(): String {
            val bytes = mutableListOf<Byte>()
            while (buffer.hasRemaining()) { val value = buffer.get(); if (value == 0.toByte()) return bytes.toByteArray().decodeToString(); bytes.add(value) }
            error("Неполный ответ Query")
        }
        val name = text(); val map = text(); text(); val game = text()
        buffer.short
        val players = buffer.get().toInt() and 255; val max = buffer.get().toInt() and 255
        repeat(5) { buffer.get() }
        val version = text()
        return linkedMapOf("Название" to name, "Карта" to map, "Игроки" to "$players / $max",
            "Время ответа" to "${(System.nanoTime() - started) / 1000000} мс", "Версия сервера" to version,
            "Последний ответ" to java.time.LocalTime.now().format(DateTimeFormatter.ofPattern("HH:mm:ss")))
    }
}

fun selfTest() {
    check(APP_VERSION.matches(Regex("\\d+(\\.\\d+){3}")))
    check(pluginVersionStatus("2.0", "1.0") == "Обновление")
    check(pluginVersionStatus("1.0", "2.0") == "Сверх последнего")
    check(pluginVersionStatus("1.0", "1.0.0") == "Актуален")
    check(retryDelayMillis("90", 0) == 90000L)
    check(retryDelayMillis(null, 1) == 60000L)
    val exportDir = Files.createTempDirectory("zi-export-test")
    try {
        val settings = Settings(exportDir.resolve("internal.json"))
        settings.set("theme", "light")
        settings.export(exportDir.resolve("export.json"))
        check(Settings(exportDir.resolve("export.json"))["theme"] == "light")
        check(!Files.exists(settings.file))
    } finally { Files.list(exportDir).use { it.forEach(Files::delete) }; Files.delete(exportDir) }

    val answers = mutableListOf<String>()
    val broadcasts = mutableListOf<String>()
    val pending = mutableSetOf(7)
    routeRconMessage(0, "conflict between plugins", { id, _ -> pending.remove(id) }, answers::add, broadcasts::add)
    check(pending.contains(7) && answers.isEmpty() && broadcasts == listOf("conflict between plugins"))
    routeRconMessage(7, "hostname: test", { id, _ -> pending.remove(id) }, answers::add, broadcasts::add)
    check(answers == listOf("hostname: test") && !pending.contains(7))
    routeRconMessage(null, "Saving complete", { _, _ -> false }, answers::add, broadcasts::add)
    check(answers.size == 1 && broadcasts.last() == "Saving complete")
    check(commandToken("status;; ser", 12)?.prefix == "ser")
    check(commandToken("say \"a;;b\"", 10) == null)
    check(commandToken("server.seed 123", 14) == null)
    check(commandToken("server.seed", 3) == CommandToken(0, 11, "ser"))
    check(hintMatches("server.s").any { it.first == "server.seed" })
    check(commandToken("", 0) == CommandToken(0, 0, ""))
    check(commandToken("status;; ", 9) == CommandToken(9, 9, ""))
    val allHints = hintMatches("")
    check(allHints.map { commandGroup(it.first) }.distinct() == listOf(CommandGroup.Rust, CommandGroup.Oxide, CommandGroup.Carbon))
    check(allHints.map { commandGroup(it.first).ordinal } == allHints.map { commandGroup(it.first).ordinal }.sorted())
    check(hintMatches("reload").map { it.first } == listOf("oxide.reload", "c.reload", "c.reloadmodule"))
    check(hintMatches("oxide.").all { commandGroup(it.first) == CommandGroup.Oxide })
    check(hintMatches("c.").any { it.first == "c.plugins" })
    check(allHints.map { it.first }.distinct().size == allHints.size)
    val listing = ftpListing("/server", listOf(FtpEntry("oxide", true, 0), FtpEntry("server.cfg", false, 2048)))
    check("папок — 1, файлов — 1" in listing && "2.0 КБ" in listing)
    check("Папка пуста" in ftpListing("/", emptyList()))
    for (scheme in listOf(OriginalLight, OriginalDark)) {
        check(contrastRatio(scheme.onSurface, scheme.surfaceVariant) >= 4.5f)
        check(contrastRatio(scheme.onSurface, scheme.surface) >= 4.5f)
        check(contrastRatio(scheme.primary, scheme.surface) >= 4.5f)
        for (fill in listOf(scheme.primary, green, yellow, purple, scheme.error)) check(contrastRatio(readableForeground(fill), fill) >= 4.5f)
    }
    check(splitCommands("status;;say \"a;;b\";; save") == listOf("status", "say \"a;;b\"", "save"))
    check(splitCommands(";; ;; ").isEmpty())
    check(remotePath("/server", "oxide/plugins/A.cs") == "/server/oxide/plugins/A.cs")
    check(runCatching { remotePath("/server", "../bad") }.isFailure)
    check(runCatching { remotePath("/server", "*") }.isFailure)
    check(compareVersions("1.10.0", "1.9.9") > 0)
    check(compareVersions("1.0", "1.0.0") == 0)
    check(pluginInfo("[Info(\"Test\", \"Author\", \"1.2.3\")]") == PluginInfo("Test", "1.2.3", "Author"))
    val dir = Files.createTempDirectory("zi-ops-check")
    val path = dir.resolve("config.json")
    val settings = Settings(path)
    settings.set("ftp_host", "localhost"); settings.set("ftps", true); settings.save()
    check(Settings(path)["ftp_host"] == "localhost" && Settings(path).flag("ftps"))
    val oldContent = Files.readString(path)
    val privateDirectory = dir.resolve("app-data")
    val migrated = openApplicationSettings(privateDirectory, listOf(path))
    check(migrated["ftp_host"] == "localhost" && migrated.flag("ftps"))
    check(Files.readString(path) == oldContent)
    migrated.set("ftp_host", "saved-in-app"); migrated.set("custom-option", "preserved"); migrated.save()
    val reopened = openApplicationSettings(privateDirectory, listOf(path))
    check(reopened["ftp_host"] == "saved-in-app" && reopened["custom-option"] == "preserved")
    reopened.load(path); reopened.save()
    check(Settings(privateDirectory.resolve("config.json"))["ftp_host"] == "localhost")
    val broken = dir.resolve("broken.json")
    Files.writeString(broken, "{ invalid json")
    val failedDirectory = dir.resolve("failed-migration")
    check(runCatching { openApplicationSettings(failedDirectory, listOf(broken)) }.isFailure)
    check(!Files.exists(failedDirectory.resolve("config.json")))
    check(Files.readString(broken) == "{ invalid json")
    Files.delete(broken)
    Files.delete(privateDirectory.resolve("config.json")); Files.delete(privateDirectory)
    Files.delete(path); Files.delete(dir)
    println("ZI-Ops self-test passed")
}
