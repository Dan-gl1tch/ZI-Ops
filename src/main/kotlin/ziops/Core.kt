package ziops

import kotlinx.serialization.json.*
import org.apache.commons.net.ftp.FTP
import org.apache.commons.net.ftp.FTPClient
import org.apache.commons.net.ftp.FTPSClient
import java.io.Closeable
import java.nio.file.Files
import java.nio.file.Path
import java.nio.file.StandardCopyOption
import java.net.URI
import java.net.http.HttpClient
import java.net.http.HttpRequest
import java.net.http.HttpResponse
import java.net.http.WebSocket
import java.time.Duration
import java.util.concurrent.*
import java.util.concurrent.atomic.AtomicInteger

val json = Json { prettyPrint = true; ignoreUnknownKeys = true }

class Settings(val file: Path) {
    private val values = linkedMapOf<String, JsonElement>()
    init { if (Files.exists(file)) load(file) }
    @Synchronized fun load(path: Path) {
        val loaded = json.parseToJsonElement(Files.readString(path)).jsonObject
        values.clear()
        values.putAll(loaded)
    }
    @Synchronized operator fun get(key: String): String = (values[key] as? JsonPrimitive)?.contentOrNull.orEmpty()
    @Synchronized fun flag(key: String) = (values[key] as? JsonPrimitive)?.booleanOrNull ?: false
    @Synchronized fun array(key: String) = values[key] as? JsonArray ?: JsonArray(emptyList())
    @Synchronized fun set(key: String, value: String) { values[key] = JsonPrimitive(value) }
    @Synchronized fun set(key: String, value: Boolean) { values[key] = JsonPrimitive(value) }
    @Synchronized fun set(key: String, value: JsonArray) { values[key] = value }
    @Synchronized fun export(path: Path) {
        require(path.toAbsolutePath().normalize() != file.toAbsolutePath().normalize()) { "Выберите другой файл для экспорта" }
        Files.writeString(path, json.encodeToString(JsonObject.serializer(), JsonObject(values)))
    }
    @Synchronized fun save() {
        val destination = file.toAbsolutePath().normalize()
        Files.createDirectories(destination.parent)
        val temp = Files.createTempFile(destination.parent, "zi-ops-config-", ".tmp")
        try {
            Files.writeString(temp, json.encodeToString(JsonObject.serializer(), JsonObject(values)))
            try { Files.move(temp, destination, StandardCopyOption.ATOMIC_MOVE, StandardCopyOption.REPLACE_EXISTING) }
            catch (_: java.nio.file.AtomicMoveNotSupportedException) {
                Files.move(temp, destination, StandardCopyOption.REPLACE_EXISTING)
            }
        } finally { Files.deleteIfExists(temp) }
    }
}

fun splitCommands(text: String): List<String> {
    val result = mutableListOf<String>()
    var quoted = false
    var start = 0
    var index = 0
    while (index < text.length) {
        if (quoted && text[index] == '\\' && index + 1 < text.length && text[index + 1] in "\"\\") {
            index += 2
            continue
        }
        if (text[index] == '"') quoted = !quoted
        if (!quoted && text.startsWith(";;", index)) {
            text.substring(start, index).trim().takeIf { it.isNotEmpty() }?.let(result::add)
            index += 2
            start = index
        } else index++
    }
    text.substring(start).trim().takeIf { it.isNotEmpty() }?.let(result::add)
    return result
}

class Rcon(private val log: (String) -> Unit, private val serverLog: (String) -> Unit = {}, private val state: (Boolean) -> Unit = {}) : Closeable {
    private val client = HttpClient.newBuilder().connectTimeout(Duration.ofSeconds(10)).build()
    private var socket: WebSocket? = null
    private val ids = AtomicInteger(1)
    private val replies = ConcurrentHashMap<Int, CompletableFuture<String>>()
    private val generation = AtomicInteger()
    @Volatile var connected = false
        private set

    @Synchronized fun connect(settings: Settings) {
        close()
        val session = generation.get()
        val scheme = if (settings.flag("rcon_ssl")) "wss" else "ws"
        val path = settings["rcon_path"].trim('/')
        val fullPath = "/" + listOf(path, settings["rcon_pass"]).filter { it.isNotEmpty() }.joinToString("/")
        val uri = URI(scheme, null, settings["rcon_host"], settings["rcon_port"].ifBlank { "28016" }.toInt(), fullPath, null, null)
        val listener = object : WebSocket.Listener {
            val buffer = StringBuilder()
            override fun onOpen(webSocket: WebSocket) {
                if (generation.get() == session) { connected = true; state(true) }
                webSocket.request(1)
            }
            override fun onText(webSocket: WebSocket, data: CharSequence, last: Boolean): CompletionStage<*>? {
                buffer.append(data)
                if (last) {
                    runCatching {
                        val message = json.parseToJsonElement(buffer.toString()).jsonObject
                        val id = message["Identifier"]?.jsonPrimitive?.intOrNull
                        val body = message["Message"]?.jsonPrimitive?.content.orEmpty()
                        if (generation.get() == session) routeRconMessage(id, body,
                            { key, text -> replies.remove(key)?.let { it.complete(text); true } ?: false }, log, serverLog)
                    }.onFailure { serverLog("Некорректное сообщение WebRCON") }
                    buffer.clear()
                }
                webSocket.request(1)
                return null
            }
            override fun onError(webSocket: WebSocket, error: Throwable) { if (generation.get() == session) lost(error) }
            override fun onClose(webSocket: WebSocket, statusCode: Int, reason: String): CompletionStage<*>? {
                if (generation.get() == session) lost(IllegalStateException("Соединение закрыто ($statusCode)"))
                return null
            }
        }
        socket = client.newWebSocketBuilder().connectTimeout(Duration.ofSeconds(10)).buildAsync(uri, listener).get(15, TimeUnit.SECONDS)
    }
    private fun lost(error: Throwable) {
        connected = false
        state(false)
        replies.values.forEach { it.completeExceptionally(error) }
        replies.clear()
    }
    fun send(command: String): String {
        check(connected) { "Сначала подключитесь к RCON" }
        val id = ids.getAndIncrement()
        val reply = CompletableFuture<String>()
        replies[id] = reply
        try {
            val payload = buildJsonObject {
                put("Identifier", id); put("Message", command); put("Name", "ZI-Ops")
            }
            socket!!.sendText(payload.toString(), true).get(10, TimeUnit.SECONDS)
            return reply.get(10, TimeUnit.SECONDS)
        } finally { replies.remove(id) }
    }
    @Synchronized override fun close() {
        generation.incrementAndGet()
        socket?.abort()
        socket = null
        lost(IllegalStateException("RCON отключён"))
    }
}

fun routeRconMessage(id: Int?, body: String, complete: (Int, String) -> Boolean, reply: (String) -> Unit, broadcast: (String) -> Unit) {
    if (id != null && id > 0 && complete(id, body)) reply(body) else broadcast(body)
}

fun remotePath(base: String, relative: String): String {
    require(relative.isNotBlank()) { "Пустой путь" }
    val clean = relative.replace('\\', '/')
    require(!clean.startsWith('/') && clean.split('/').none { it == ".." } && clean.none { it in "*?[]\r\n\u0000" }) { "Недопустимый путь $relative" }
    require(base.none { it in "*?[]\r\n\u0000" } && base.split('/').none { it == ".." }) { "Недопустимая базовая папка" }
    return "/" + (base.trim('/') + "/" + clean).split('/').filter { it.isNotEmpty() && it != "." }.joinToString("/")
}

class ServerFiles(settings: Settings) : Closeable {
    val ftp: FTPClient = if (settings.flag("ftps")) FTPSClient(false).apply { isEndpointCheckingEnabled = true } else FTPClient()
    val base = settings["ftp_base"].ifBlank { "/" }
    init {
        try {
            ftp.connectTimeout = 10000
            ftp.defaultTimeout = 15000
            ftp.dataTimeout = Duration.ofSeconds(15)
            ftp.controlEncoding = "UTF-8"
            ftp.connect(settings["ftp_host"], settings["ftp_port"].ifBlank { "21" }.toInt())
            check(ftp.login(settings["ftp_user"], settings["ftp_pass"])) { "FTP отклонил вход" }
            if (ftp is FTPSClient) { ftp.execPBSZ(0); ftp.execPROT("P") }
            ftp.enterLocalPassiveMode()
            ftp.setFileType(FTP.BINARY_FILE_TYPE)
            check(ftp.changeWorkingDirectory(base)) { "Базовая папка FTP не найдена" }
        } catch (error: Exception) { close(); throw error }
    }
    fun read(path: String): ByteArray = java.io.ByteArrayOutputStream().use {
        check(ftp.retrieveFile(path, it)) { "Не удалось скачать $path" }; it.toByteArray()
    }
    fun write(path: String, bytes: ByteArray) {
        check(!Thread.currentThread().isInterrupted) { "Операция остановлена" }
        check(ftp.storeFile(path, bytes.inputStream())) { "Не удалось записать $path" }
    }
    fun deleteTree(path: String) {
        check(!Thread.currentThread().isInterrupted) { "Операция остановлена" }
        require(path != "/" && path.trimEnd('/') != base.trimEnd('/')) { "Нельзя удалить базовую папку" }
        val files = ftp.listFiles(path)
        check(ftp.replyCode in 200..299) { "Не удалось прочитать $path" }
        for (file in files) {
            if (file.name in listOf(".", "..")) continue
            val child = "$path/${file.name}"
            check(!file.isSymbolicLink) { "Обнаружена символьная ссылка $child" }
            if (file.isDirectory) deleteTree(child) else check(ftp.deleteFile(child)) { "Не удалось удалить $child" }
        }
        check(ftp.removeDirectory(path)) { "Не удалось удалить папку $path" }
    }
    override fun close() { if (ftp.isConnected) runCatching { ftp.disconnect() } }
}

class HttpFailure(val status: Int, val retryAfter: String?) : java.io.IOException("HTTP $status")

val http: HttpClient = HttpClient.newBuilder().followRedirects(HttpClient.Redirect.NORMAL).connectTimeout(Duration.ofSeconds(15)).build()
fun download(url: String, apiKey: String = "", body: String? = null): ByteArray {
    val uri = URI(url)
    require(uri.scheme in listOf("http", "https") && !uri.host.isNullOrBlank()) { "Нужна HTTP/HTTPS ссылка" }
    val request = HttpRequest.newBuilder(uri).timeout(Duration.ofSeconds(45)).header("User-Agent", "ZI-Ops/$APP_VERSION")
    if (apiKey.isNotBlank()) request.header("X-API-Key", apiKey)
    if (body != null) request.header("Content-Type", "application/json").POST(HttpRequest.BodyPublishers.ofString(body))
    val response = http.send(request.build(), HttpResponse.BodyHandlers.ofByteArray())
    if (response.statusCode() !in 200..299) throw HttpFailure(response.statusCode(), response.headers().firstValue("Retry-After").orElse(null))
    return response.body()
}

data class PluginInfo(val name: String, val version: String, val author: String)
fun pluginInfo(source: String): PluginInfo? {
    val match = Regex("""\[Info\s*\(\s*"([^"]+)"\s*,\s*"([^"]+)"\s*,\s*"([^"]+)"""").find(source) ?: return null
    return PluginInfo(match.groupValues[1], match.groupValues[3], match.groupValues[2])
}
fun compareVersions(left: String, right: String): Int {
    fun parts(value: String): List<Int> {
        require(value.matches(Regex("[vV]?\\d+(\\.\\d+)*"))) { "Неизвестный формат версии $value" }
        return value.trimStart('v', 'V').split('.').map(String::toInt)
    }
    val a = parts(left); val b = parts(right)
    for (index in 0 until maxOf(a.size, b.size)) {
        val result = (a.getOrElse(index) { 0 }).compareTo(b.getOrElse(index) { 0 })
        if (result != 0) return result
    }
    return 0
}
