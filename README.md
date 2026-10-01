# ZI-Ops
## ZombiIsland Operations

![ZI-Ops](https://previews.dropbox.com/p/thumb/ADLPa8W4ItrOJcaLJcn14YHaSLtDChNz8JfK3-jgiKDbYeMgHTc_xRONLNdcBvR3sIiEJJPsaZtwqmDrriViNjYxzw1oUqKxCTij-RS5Qrbo9AP4gf5OtK2J-RXmINQJW28FA2iP7PMQfu9NDAU2OfHJSVWEvMdATnWJ3uZAkZ0IG6IY14vTNmgLkpvw1FdsXSUczIi6HfUnvmbocB-cxQfqBNty4LxBOKGJnWHLs3QKxwuoBKP_ufYABdWSUbu9XwoT22VnBIAMF-CCkfujHk1oodP-_89I5UJQoUwTCxYlPfPbXjdfUJRcDEfQfTUVFDfPY5JMp3dRQxQN6pxGuYmI/p.png)

Программа для управления сервером Rust с рабочего стола Windows. Работает с файлами сервера через FTP/FTPS, отправляет команды через RCON и обращается к RustMaps для генерации карт по seed и размеру.

## Что умеет

- Выполнять вайп: удалять выбранные файлы и очищать указанные папки через FTP.
- Подготавливать server.cfg с новым seed и размером карты, загружать его на сервер и отправлять рестарт через RCON.
- Переключать «Судную ночь» заменой заданных плагинов и конфигураций.
- Отправлять готовые и вручную введённые RCON-команды, показывать ответы сервера.
- Проверять версии установленных .cs-плагинов и обновлять их по настроенным ссылкам.
- Исключать кастомные плагины из массового обновления и сортировать таблицу плагинов.
- Отправлять запросы на генерацию карт в RustMaps и проверять наличие карты.
- Сохранять параметры подключения и списки операций в config.json.

## Как начать

Запустите `ZI-Ops.exe`, откройте «Настройки» и укажите данные FTP и RCON из панели хостинга. RustMaps API Key нужен только для функций RustMaps. Сохраните настройки и проверьте подключение.

Перед первым вайпом проверьте базовый FTP-путь и списки удаления. Сделайте резервную копию файлов сервера, которые хотите сохранить.

[Документация: настройка и использование](DOCUMENTATION.md)

[История версий и изменений](BeforVersion/PATCH_NOTES.md)

## Запуск из исходников

Нужен Python с Tkinter. Для RCON используется пакет `websocket-client`:

```bash
python -m pip install websocket-client
python zi_ops.py
```

Для сборки Windows EXE в репозитории есть `build.bat`. Он использует PyInstaller, `ZI-Ops.ico` и `zi_ops_version.txt`:

```bash
python -m pip install pyinstaller websocket-client
build.bat
```

Результат сборки — `dist/ZI-Ops.exe`.

## Файл настроек

`config.json` содержит сохранённые параметры, включая пароли FTP/RCON и RustMaps API Key. Они записываются без шифрования. Не публикуйте этот файл в репозитории и не передавайте его вместе с программой.

## Автор и поддержка

Автор: **danilmine_D47**.

[Обновления — DanStudios47](https://t.me/DanStudios47)

[Поддержать разработку через DonationAlerts](https://www.donationalerts.com/r/danilmine_)

Пожертвования помогают продолжать разработку, исправлять ошибки и поддерживать программу. Все функции доступны бесплатно.
