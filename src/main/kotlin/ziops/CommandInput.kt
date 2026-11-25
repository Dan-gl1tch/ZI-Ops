package ziops

import androidx.compose.foundation.*
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.*
import androidx.compose.foundation.text.BasicTextField
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.*
import androidx.compose.ui.focus.*
import androidx.compose.ui.graphics.SolidColor
import androidx.compose.ui.input.key.*
import androidx.compose.ui.text.TextRange
import androidx.compose.ui.text.input.TextFieldValue
import androidx.compose.ui.unit.*
import androidx.compose.ui.window.*

val commandHints = listOf(
    "status" to "Статус сервера и список игроков", "server.seed" to "Seed текущей карты",
    "server.worldsize" to "Размер карты", "server.save" to "Сохранить мир", "server.hostname" to "Название сервера",
    "server.description" to "Описание сервера", "server.maxplayers" to "Лимит игроков", "server.level" to "Тип карты",
    "server.tags" to "Теги сервера", "server.port" to "Игровой порт", "server.queryport" to "Порт Query",
    "server.identity" to "Папка сервера", "server.fps" to "Ограничение FPS", "server.tickrate" to "Частота обновления",
    "server.saveinterval" to "Интервал автосохранения", "say" to "Объявление: say \"текст\"",
    "restart" to "Перезапуск: restart 60 \"причина\"", "quit" to "Остановить сервер",
    "find" to "Поиск команд: find seed", "kick" to "Исключить игрока: kick SteamID \"причина\"",
    "ban" to "Заблокировать: ban SteamID \"причина\"", "unban" to "Снять блокировку: unban SteamID",
    "banlist" to "Список блокировок", "users" to "Подключённые игроки", "ownerid" to "Назначить владельца",
    "moderatorid" to "Назначить модератора", "removeowner" to "Снять права владельца",
    "removemoderator" to "Снять права модератора", "writecfg" to "Сохранить конфигурацию", "env.time" to "Время суток",
    "oxide.plugins" to "Список плагинов", "oxide.reload" to "Перезагрузить: oxide.reload ИмяПлагина",
    "oxide.load" to "Загрузить: oxide.load ИмяПлагина", "oxide.unload" to "Выгрузить: oxide.unload ИмяПлагина",
    "oxide.version" to "Версия Oxide", "oxide.show" to "Группы и права: oxide.show group vip",
    "oxide.grant" to "Выдать право: oxide.grant group vip permission.name",
    "oxide.revoke" to "Снять право: oxide.revoke user SteamID permission.name",
    "oxide.group" to "Управление группами: oxide.group add vip",
    "oxide.usergroup" to "Добавить в группу: oxide.usergroup add SteamID vip",
    "c.plugins" to "Список плагинов Carbon", "c.version" to "Версии Carbon и Rust",
    "c.help" to "Справка Carbon", "c.find" to "Поиск команд Carbon",
    "c.load" to "Загрузить: c.load ИмяПлагина", "c.unload" to "Выгрузить: c.unload ИмяПлагина",
    "c.reload" to "Перезагрузить: c.reload ИмяПлагина",
    "c.plugininfo" to "Подробная информация о плагине", "c.plugincmds" to "Команды выбранного плагина",
    "c.grant" to "Выдать права пользователю или группе", "c.revoke" to "Отозвать права пользователя или группы",
    "c.group" to "Управление группами Carbon", "c.usergroup" to "Добавить или удалить игрока из группы",
    "c.show" to "Информация о пользователе или группе",
    "c.loadconfig" to "Загрузить конфигурацию Carbon", "c.saveconfig" to "Сохранить конфигурацию Carbon",
    "c.reloadmodule" to "Перезагрузить модуль Carbon", "c.loadmodule" to "Загрузить настройки и данные модуля",
    "c.savemodule" to "Сохранить настройки и данные модуля"
)
enum class CommandGroup(val title: String) {
    Rust("Rust — основные команды"), Oxide("Oxide / uMod"), Carbon("Carbon")
}
fun commandGroup(command: String): CommandGroup = when {
    command.startsWith("oxide.") -> CommandGroup.Oxide
    command.startsWith("c.") -> CommandGroup.Carbon
    else -> CommandGroup.Rust
}
data class CommandToken(val start: Int, val end: Int, val prefix: String)
fun commandToken(text: String, cursor: Int): CommandToken? {
    val end = cursor.coerceIn(0, text.length)
    var start = 0
    var quoted = false
    var index = 0
    while (index < end) {
        if (quoted && text[index] == '\\' && index + 1 < end && text[index + 1] in "\"\\") { index += 2; continue }
        if (text[index] == '"') quoted = !quoted
        if (!quoted && index + 1 < end && text.startsWith(";;", index)) { start = index + 2; index++ }
        index++
    }
    while (start < end && text[start].isWhitespace()) start++
    val prefix = text.substring(start, end)
    if (prefix.any { it.isWhitespace() || it == '"' || it == ';' }) return null
    var tokenEnd = end
    while (tokenEnd < text.length && !text[tokenEnd].isWhitespace() && text[tokenEnd] != ';') tokenEnd++
    return CommandToken(start, tokenEnd, prefix)
}
fun hintMatches(prefix: String) = commandHints.filter { it.first.contains(prefix, ignoreCase = true) }
    .sortedWith(compareBy<Pair<String, String>> { commandGroup(it.first).ordinal }.thenBy { if (it.first.startsWith(prefix, true)) 0 else 1 })

@Composable fun CommandInput(value: String, change: (String) -> Unit, send: () -> Unit, modifier: Modifier = Modifier) {
    var edit by remember { mutableStateOf(TextFieldValue(value, TextRange(value.length))) }
    var focused by remember { mutableStateOf(false) }
    var dismissed by remember { mutableStateOf(false) }
    var selected by remember { mutableIntStateOf(0) }
    val requester = remember { FocusRequester() }
    val listState = rememberLazyListState()
    LaunchedEffect(value) { if (value != edit.text) { edit = TextFieldValue(value, TextRange(value.length)); dismissed = false } }
    val token = commandToken(edit.text, edit.selection.start)
    val matches = if (token != null && focused && !dismissed) hintMatches(token.prefix) else emptyList()
    LaunchedEffect(selected, matches) {
        if (matches.isNotEmpty()) listState.animateScrollToItem(selected.coerceIn(0, matches.lastIndex))
    }
    fun accept(index: Int) {
        val context = token ?: return
        val hint = matches.getOrNull(index) ?: return
        val next = edit.text.replaceRange(context.start, context.end, hint.first)
        edit = TextFieldValue(next, TextRange(context.start + hint.first.length)); change(next); dismissed = true
        requester.requestFocus()
    }
    Box(modifier) {
        BasicTextField(edit, {
            edit = it; change(it.text); dismissed = false; selected = 0
        }, Modifier.fillMaxWidth().height(27.dp).background(MaterialTheme.colorScheme.surfaceVariant)
            .border(2.dp, MaterialTheme.colorScheme.onSurfaceVariant).padding(horizontal = 5.dp, vertical = 4.dp)
            .focusRequester(requester).onFocusChanged { focused = it.isFocused }
            .onPreviewKeyEvent {
                if (it.type != KeyEventType.KeyDown) false else when {
                    it.key == Key.Tab && matches.isNotEmpty() -> { accept(selected.coerceIn(0, matches.lastIndex)); true }
                    it.key == Key.DirectionDown && matches.isNotEmpty() -> { selected = (selected + 1) % matches.size; true }
                    it.key == Key.DirectionUp && matches.isNotEmpty() -> { selected = (selected - 1 + matches.size) % matches.size; true }
                    it.key == Key.Escape -> { dismissed = true; true }
                    it.key == Key.Enter -> { dismissed = true; send(); true }
                    else -> false
                }
            }, textStyle = MaterialTheme.typography.bodyMedium.copy(color = MaterialTheme.colorScheme.onSurface, fontFamily = WindowsFont),
            cursorBrush = SolidColor(MaterialTheme.colorScheme.primary), singleLine = true)
        if (matches.isNotEmpty()) Popup(alignment = Alignment.TopStart, offset = IntOffset(0, 30), onDismissRequest = { dismissed = true }, properties = PopupProperties(focusable = false)) {
            Column(Modifier.width(590.dp).border(1.dp, MaterialTheme.colorScheme.outline).background(MaterialTheme.colorScheme.surface)) {
                Text("Команда — Tab для выбора     ↑↓ — выбор     Enter — отправить", Modifier.padding(7.dp), color = MaterialTheme.colorScheme.primary)
                val groupCount = matches.map { commandGroup(it.first) }.distinct().size
                Box(Modifier.fillMaxWidth().height((matches.size * 32 + groupCount * 24).coerceAtMost(320).dp)) {
                    LazyColumn(Modifier.fillMaxSize().padding(end = 12.dp), state = listState) {
                        itemsIndexed(matches, key = { _, item -> item.first }) { index, item ->
                            Column {
                                val group = commandGroup(item.first)
                                if (index == 0 || group != commandGroup(matches[index - 1].first)) {
                                    Text(group.title, Modifier.fillMaxWidth().height(24.dp).padding(horizontal = 7.dp, vertical = 3.dp), color = MaterialTheme.colorScheme.primary, style = MaterialTheme.typography.labelLarge)
                                }
                                Row(Modifier.fillMaxWidth().height(32.dp).background(if (index == selected) MaterialTheme.colorScheme.surfaceVariant else MaterialTheme.colorScheme.surface)
                                    .clickable { accept(index) }.padding(7.dp), horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                                    Text(item.first, Modifier.width(170.dp)); Text(item.second, Modifier.weight(1f))
                                }
                            }
                        }
                    }
                    VerticalScrollbar(rememberScrollbarAdapter(listState), Modifier.align(Alignment.CenterEnd).fillMaxHeight())
                }
            }
        }
    }
}
