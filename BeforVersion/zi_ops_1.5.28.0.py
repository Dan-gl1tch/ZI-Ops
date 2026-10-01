#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ZI-Ops — GUI Application for Rust Server Management"""

# Настройки сборки Nuitka: python -m nuitka zi_ops.py
# nuitka-project: --mode=onefile
# nuitka-project: --enable-plugin=tk-inter
# nuitka-project: --include-package=websocket
# nuitka-project: --output-dir=dist_nuitka
# nuitka-project-if: {OS} == "Windows":
#    nuitka-project: --windows-console-mode=disable
#    nuitka-project: --output-filename=ZI-Ops.exe
#    nuitka-project: --windows-icon-from-ico={MAIN_DIRECTORY}/ZI-Ops.ico
#    nuitka-project: --company-name=ZI & DanStudio47
#    nuitka-project: --product-name=ZI-Ops
#    nuitka-project: --file-version=1.5.28.0
#    nuitka-project: --product-version=1.5.28.0
#    nuitka-project: --file-description=ZI-Ops - Rust Server Management
#    nuitka-project: --copyright=2026 - danilmine_D47

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import ftplib
import random
import urllib.request
import urllib.error
import urllib.parse
import threading
import json
import os
import sys
import re
import socket
import posixpath
import tempfile
import time
import webbrowser
import select
import ctypes

APP_NAME = "ZI-Ops"
APP_AUTHOR = "danilmine_D47"
APP_VERSION = "1.5.28.0"
# Встроенная публичная ссылка автора; настройки пользователя её не изменяют.
DONATION_URL = "https://www.donationalerts.com/r/danilmine_"
UPDATES_URL = "https://t.me/DanStudios47"


if __name__ == "__main__":
    # Код для отображения правильной иконки в панели задач Windows
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("mycompany.ziops.1.0")
    except Exception:
        pass

try:
    import websocket
    WEBSOCKET_OK = True
except ImportError:
    WEBSOCKET_OK = False


class Tooltip:
    """Кастомный тултип с задержкой 0.5 сек для tkinter"""
    def __init__(self, widget, text, delay=500):
        self.widget = widget
        self.text = text
        self.delay = delay
        self.tipwindow = None
        self.id = None
        self.widget.bind("<Enter>", self.on_enter)
        self.widget.bind("<Leave>", self.on_leave)
        self.widget.bind("<ButtonPress>", self.on_leave)

    def on_enter(self, event=None):
        self.schedule()

    def on_leave(self, event=None):
        self.unschedule()
        self.hide()

    def schedule(self):
        self.unschedule()
        self.id = self.widget.after(self.delay, self.show)

    def unschedule(self):
        if self.id:
            self.widget.after_cancel(self.id)
            self.id = None

    def show(self):
        if self.tipwindow or not self.text:
            return
        x = self.widget.winfo_rootx() + 20
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 5
        self.tipwindow = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        tw.configure(bg="#313244")
        label = tk.Label(tw, text=self.text, justify="left",
                         background="#313244", foreground="#cdd6f4",
                         relief="solid", borderwidth=1,
                         font=("Segoe UI", 9), padx=8, pady=4,
                         wraplength=350)
        label.pack()

    def hide(self):
        if self.tipwindow:
            self.tipwindow.destroy()
            self.tipwindow = None


class RustMapsAPI:
    """Клиент RustMaps API v4.

    Важно: API не предоставляет процент выполнения генерации карты.
    Поэтому приложение не рисует фиктивный progress bar для RustMaps.
    """
    BASE_URL = "https://api.rustmaps.com"
    MAX_SEED = 2147483647

    def __init__(self, api_key):
        self.api_key = api_key.strip()

    def _headers(self, content_type=False):
        headers = {
            "X-API-Key": self.api_key,
            "User-Agent": "ZI-Ops/1.0",
            "Accept": "application/json",
        }
        if content_type:
            headers["Content-Type"] = "application/json"
        return headers

    @staticmethod
    def validate_size(size):
        size = int(size)
        if size < 1000 or size > 10000:
            raise ValueError("Размер карты должен быть от 1000 до 10000.")
        return size

    @classmethod
    def validate_seed(cls, seed):
        seed = int(seed)
        if not 1 <= seed <= cls.MAX_SEED:
            raise ValueError(f"Seed должен быть от 1 до {cls.MAX_SEED}.")
        return seed

    def generate(self, size=4250, seed=None):
        if not self.api_key:
            raise ValueError("API ключ не указан. Получи его на https://rustmaps.com/dashboard")
        size = self.validate_size(size)
        seed = self.validate_seed(seed) if seed is not None else random.randint(1, self.MAX_SEED)
        url = f"{self.BASE_URL}/v4/maps"
        payload = json.dumps({"size": size, "seed": seed}).encode("utf-8")
        req = urllib.request.Request(url, data=payload, headers=self._headers(True), method="POST")
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
                try:
                    data = json.loads(raw)
                except json.JSONDecodeError:
                    raise RuntimeError(f"RustMaps вернул не-JSON ответ (HTTP {resp.status}).")
                return resp.status, data, seed
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
            if e.code == 409:
                raise RuntimeError(
                    "RustMaps вернул 409 Conflict: сейчас запрос нельзя принять "
                    "(обычно достигнут лимит одновременных генераций). "
                    "Запрос НЕ считаем успешно созданным и автоматически повторно не отправляем."
                )
            if e.code in (401, 403):
                raise RuntimeError(f"RustMaps API: HTTP {e.code}. Проверь API-ключ и его права.")
            raise RuntimeError(f"RustMaps API: HTTP {e.code}: {body[:500]}")
        except urllib.error.URLError as e:
            raise RuntimeError(f"Ошибка сети RustMaps: {e.reason}")

    def get_map(self, map_id):
        if not self.api_key:
            raise ValueError("API ключ не указан.")
        map_id = str(map_id).strip()
        if not map_id:
            raise ValueError("ID карты пуст.")
        url = f"{self.BASE_URL}/v4/maps/{urllib.parse.quote(map_id, safe='')}"
        req = urllib.request.Request(url, headers=self._headers())
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode("utf-8", errors="replace"))
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"RustMaps API: HTTP {e.code}: {body[:500]}")

    def get_map_by_seed(self, size, seed):
        size = self.validate_size(size)
        seed = self.validate_seed(seed)
        url = f"{self.BASE_URL}/v4/maps/{size}/{seed}"
        req = urllib.request.Request(url, headers=self._headers())
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode("utf-8", errors="replace"))
        except urllib.error.HTTPError as e:
            raise e
        except urllib.error.URLError as e:
            raise RuntimeError(f"Ошибка сети RustMaps: {e.reason}")


class RustRCON:
    def __init__(self, host, port, password, timeout=10, path="", ssl=False):
        self.host = host
        self.port = port
        self.password = password
        self.timeout = timeout
        self.path = path.strip()
        self.ssl = ssl
        self.ws = None
        self.connected = False
        self._msg_id = 0
        self._lock = threading.Lock()

    def connect(self):
        if not WEBSOCKET_OK:
            raise RuntimeError("pip install websocket-client")
        if self.path and not self.path.startswith("/"):
            self.path = "/" + self.path
        scheme = "wss" if self.ssl else "ws"
        url = f"{scheme}://{self.host}:{self.port}{self.path}/{self.password}" if self.path else f"{scheme}://{self.host}:{self.port}/{self.password}"
        self.ws = websocket.create_connection(url, timeout=self.timeout, enable_multithread=True)
        self.ws.settimeout(self.timeout)
        self.connected = True
        return True

    def disconnect(self):
        if self.ws:
            try:
                self.ws.close()
            except Exception:
                pass
        self.connected = False

    def send(self, command, wait=False, timeout=5):
        with self._lock:
            if not self.connected or not self.ws:
                raise RuntimeError("Нет подключения")
            self._msg_id += 1
            payload = {"Identifier": self._msg_id, "Message": command, "Name": "RustManager"}
            self.ws.settimeout(self.timeout)
            self.ws.send(json.dumps(payload))
            if not wait:
                return "Команда отправлена"
            deadline = time.monotonic() + max(0.1, timeout)
            try:
                while True:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        return "[Таймаут: сервер не ответил вовремя]"
                    self.ws.settimeout(remaining)
                    resp = self.ws.recv()
                    if not resp:
                        return "[Пустой ответ]"
                    try:
                        data = json.loads(resp)
                    except json.JSONDecodeError:
                        return f"[Raw: {str(resp)[:200]}]"
                    # Rust RCON can send messages unrelated to our request.
                    if data.get("Identifier") == self._msg_id:
                        return str(data.get("Message", ""))
            except websocket.WebSocketTimeoutException:
                return "[Таймаут: сервер не ответил вовремя]"
            except Exception as e:
                self.connected = False
                raise RuntimeError(f"RCON соединение потеряно: {e}")


class ZI_Ops:
    # Встроенная иконка 64x64 GIF (base64) — буквы "ZI"
    ICON_B64 = (
        "R0lGODdhQABAAIUAAPoBAf36+v3p6dAUFdgLDf3HyelnZvzX1P62tP6op//k2ucSEv2al+xWVf3Eu8sbIv6Ih7oYF/mimtZGRtdpZ/J1c64lKOpjW/jb4thYVe9GStE2OdfHyu03NP99gP+8wrcbItUmKr96d99mXMytrMy2tv+Ef782NtQ9RsBAPc5/ed+YntO4wt/a3+ElKPBBPutfYP+YoAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAACwAAAAAQABAAEAI/wABCBxIsKDBgwgTKlzIsKHDhxAFPiggIIDFixgzarwoAMKACAU2WiwwICJEAgxEXnTwYOCABBwDHNDwAAECAiYXGjiQUQBFngca4DT4UiXJnAU7hFSpwCPDoiKP5iRgoKLKqxkT4BywdKNUpAUJiEUolsCAs2PBql3L9ikCrHAtdjyLwKrGAkNzDkCgQIGAv4ADy7WrMahZBwhKeC3ZtuCGrgEE8OTolOCAD4QP9A3ggPHaBQNiXMTAQSODlgn3GvWccyfWFRQoVBhxwYDt2wZeCFQdlTXEBQYUxIWbYADoBIQxfm3MvLnz59CjHyTQoUFtAxksZLidwnaG77htX/830MGsBgMMJEhgkJ4BhAsLwE6UO1ykgApnYfYGu1cBieT1yeXRAA6splZ8OJU1FGggqPBXaV5NsJV+dkkgwgF4RVdTT1mxthdhBVhgAQKdPafBZIMBFpkBebkEmQAYXLTcWgN4YBeABWiQ2lv7sVUTgBgx4BtR+i22VgMobnRfi6kh12NOSA73l0oMxMeVgUhVFSCVJT3wgUZTzggRkoH9hUGZaE4JmAImxLcAAwUcICcGGMh5QALS5annnnz26eefgAa6Z15lAUAAggDEN9ChhoY1gFlnncXWS36laamlB+D3oUglIsXblmB6kF9GLciIml5LAVmfAKJCtdEBTEL/9GkAFIEamagRFPikSQQq4ICukYE6VwR1RRXrQwt0UNsIFYRnQGwixAnhRkICQGxygB0wZHOPYVWZqxYpwAACB3T6HAFRMoXfokVahMADBCRgbnNUqWqRYZbxeK8CCSSggLbPDQABYWpa5MAGRH3J0ZQybavWAClh9BcJJVRU3EGzZpQhcyHoaxcLZwpQLcb63uVwTih0laRMAphw7G4la3zySQ0QbBGEQS2UsXIzO0RABfbSOsFT7cpM48BXFRBCQ+AazZ8EWCFgAVqJJkhUsUYi5ULMSqqJZl8Q7AasyWC5ZmtGDGwFmdMmAXdj0FdJUNJlYFYkps9ano2RBAkWQc0zUgRcIJySAfJtKHIA+vQy0xpM0MAEIJzQwAYTwPC4BRFYMAFusVFgWwOemfXARyGAEMEDEfQs6Oqst+56dAEBADs="
    )

    DEFAULT_WIPE_FILES = [
        "oxide/data/ImageLibrary/image_data.json",
        "oxide/data/ImageLibrary/image_urls.json",
        "oxide/data/ImageLibrary/skin_data.json",
        "oxide/data/IQSystem/IQCases/DataPlayer.json",
        "oxide/data/IQSystem/IQCases/DataPlayerTakeGiftCase.json",
        "oxide/data/Kits/player_data.json",
        "oxide/data/MiningFarm/FarmList.json",
        "oxide/data/XDQuest/PlayerInfo.json",
        "oxide/data/Backpack_Data.json",
        "oxide/data/BackPumpJack.json",
        "oxide/data/CapsulesData.json",
        "oxide/data/Convoy.json",
        "oxide/data/Economics.json",
        "oxide/data/ExcavatorLock.json",
        "oxide/data/Friends.json",
        "oxide/data/NTeleportationHome.json",
        "oxide/data/Remove_NewEntity.json",
        "oxide/data/SpawnHeli.json",
        "oxide/data/StarterMoney.json",
    ]
    DEFAULT_WIPE_FOLDERS = [
        "oxide/data/Skills/Players",
        "oxide/data/XDStatistics/Players",
    ]
    DEFAULT_JUDGMENT_ON_DELETE = ["oxide/data/SomePlugin1.json", "oxide/data/SomePlugin2.json"]
    DEFAULT_JUDGMENT_ON_REMOTE = "oxide/data/JudgmentMode.json"
    DEFAULT_JUDGMENT_OFF_DELETE = ["oxide/data/SomePlugin3.json"]
    DEFAULT_JUDGMENT_OFF_UPLOADS = ["", ""]
    DEFAULT_JUDGMENT_OFF_REMOTES = ["oxide/data/JudgmentRestore1.json", "oxide/data/JudgmentRestore2.json"]
    AUTO_CONFIG = "config.json"

    def __init__(self, root):
        self.root = root
        self.root.title(APP_NAME)
        self.root.geometry("1050x900")
        self.root.minsize(950, 750)
        self.root.configure(bg="#1e1e2e")
        self.style = ttk.Style()
        self.style.theme_use("clam")
        self.configure_styles()
        self.running_lock = threading.Lock()
        self._running = False
        self.stop_requested = False
        self.stop_event = threading.Event()
        self._rcon_connecting = False
        self.rcon_lock = threading.Lock()
        self.rcon_client = None
        if "__compiled__" in globals():
            # Nuitka onefile: конфиг хранится у исходного EXE, не во временной папке.
            self.script_dir = os.path.abspath(__compiled__.containing_dir)
        elif getattr(sys, 'frozen', False):
            self.script_dir = os.path.dirname(sys.executable)
        else:
            self.script_dir = os.path.dirname(os.path.abspath(__file__))
        self.auto_config_path = os.path.join(self.script_dir, self.AUTO_CONFIG)
        self._set_icon()
        self.build_ui()
        self.load_config(self.auto_config_path, silent=True)
        if not WEBSOCKET_OK:
            self.root.after(1000, lambda: messagebox.showwarning("RCON недоступен",
                "Библиотека websocket-client не установлена.\nRCON-функции недоступны.\n\nУстанови: pip install websocket-client"))

    def configure_styles(self):
        bg, fg, accent, surface = "#1e1e2e", "#cdd6f4", "#89b4fa", "#313244"
        red, green, yellow, mauve = "#f38ba8", "#a6e3a1", "#f9e2af", "#cba6f7"
        self.style.configure("TFrame", background=bg)
        self.style.configure("TLabel", background=bg, foreground=fg, font=("Segoe UI", 10))
        self.style.configure("TButton", background=surface, foreground=fg, font=("Segoe UI", 10, "bold"), padding=6)
        self.style.configure("Accent.TButton", background=accent, foreground="#1e1e2e", font=("Segoe UI", 10, "bold"), padding=6)
        self.style.configure("Danger.TButton", background=red, foreground="#1e1e2e", font=("Segoe UI", 10, "bold"), padding=6)
        self.style.configure("Success.TButton", background=green, foreground="#1e1e2e", font=("Segoe UI", 10, "bold"), padding=6)
        self.style.configure("Warn.TButton", background=yellow, foreground="#1e1e2e", font=("Segoe UI", 10, "bold"), padding=6)
        self.style.configure("Purple.TButton", background=mauve, foreground="#1e1e2e", font=("Segoe UI", 10, "bold"), padding=6)
        self.style.configure("TEntry", fieldbackground=surface, foreground=fg, insertcolor=fg)
        self.style.configure("TCheckbutton", background=bg, foreground=fg)
        self.style.configure("Horizontal.TProgressbar", background=accent, troughcolor=surface)
        self.style.configure("TLabelframe", background=bg, foreground=fg)
        self.style.configure("TLabelframe.Label", background=bg, foreground=accent, font=("Segoe UI", 10, "bold"))
        # Treeview dark theme
        self.style.configure("Treeview",
                             background="#313244",
                             foreground="#cdd6f4",
                             fieldbackground="#313244",
                             font=("Segoe UI", 9),
                             rowheight=22)
        self.style.configure("Treeview.Heading",
                             background="#45475a",
                             foreground="#cdd6f4",
                             font=("Segoe UI", 10, "bold"),
                             relief="flat")
        self.style.map("Treeview",
                       background=[("selected", "#585b70"), ("!selected", "#313244")],
                       foreground=[("selected", "#cdd6f4"), ("!selected", "#cdd6f4")])
        self.style.map("Treeview.Heading",
                       background=[("active", "#585b70"), ("pressed", "#585b70")])

    def _set_icon(self):
        """Устанавливает иконку окна из встроенного base64 GIF (буквы ZI)."""
        try:
            import base64
            icon_data = base64.b64decode(self.ICON_B64)
            icon_img = tk.PhotoImage(data=icon_data)
            self.root.iconphoto(True, icon_img)
            self._icon_ref = icon_img  # держим ссылку, чтобы GC не съел
        except Exception:
            pass  # если не получилось — иконка по умолчанию

    # ===== ОБЩИЕ УТИЛИТЫ =====
    @staticmethod
    def _clean_lines(text):
        """Возвращает непустые строки без комментариев и лишних пробелов."""
        result = []
        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            result.append(line)
        return result

    def _remote_path(self, base, path):
        """Безопасно собирает POSIX-путь FTP и запрещает выход выше base."""
        base = (base or "").replace("\\", "/").strip()
        path = (path or "").replace("\\", "/").strip()
        if any(c in base + path for c in "\r\n\x00"):
            raise ValueError("Недопустимые символы в FTP-пути.")
        if not path or ".." in path.split("/") or ".." in base.split("/"):
            raise ValueError("Удалённый путь пуст или содержит '..'.")
        base = posixpath.normpath(base) if base else ""
        norm = posixpath.normpath(path)
        if norm in ("", ".", "/"):
            raise ValueError("Нельзя использовать корень вместо файла или папки.")
        if posixpath.isabs(norm):
            if base not in ("", ".", "/"):
                boundary = "/" + base.strip("/")
                if not norm.startswith(boundary + "/"):
                    raise ValueError("Абсолютный путь выходит за пределы базовой папки.")
            return norm
        return posixpath.join(base, norm) if base else norm

    @staticmethod
    def _remote_basename(path):
        return posixpath.basename((path or "").replace("\\", "/").rstrip("/"))

    def _snapshot(self, *vars_):
        """Читает Tk variables в главном потоке перед передачей данных worker-потоку."""
        return [v.get() for v in vars_]

    def _set_progress(self, widget, status_var, value, text=None):
        self.root.after(0, lambda v=max(0, min(100, int(value))): widget.configure(value=v))
        if text is not None:
            self.root.after(0, lambda t=text: status_var.set(t))

    def build_ui(self):
        ttk.Label(
            self.root,
            text=f"Версия {APP_VERSION}  •  Автор: {APP_AUTHOR}",
            anchor="center",
        ).pack(side="bottom", fill="x", padx=10, pady=(0, 8))
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill="both", expand=True, padx=10, pady=10)
        self.tab_wipe = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_wipe, text="  🧹 Вайп  ")
        self.build_wipe_tab()
        self.tab_judgment = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_judgment, text="  🌑 Судная ночь  ")
        self.build_judgment_tab()
        self.tab_rcon = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_rcon, text="  🎮 RCON  ")
        self.build_rcon_tab()
        self.tab_plugins = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_plugins, text="  📦 Плагины  ")
        self.build_plugins_tab()
        self.tab_settings = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_settings, text="  ⚙️ Настройки  ")
        self.build_settings_tab()
        self.tab_support = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_support, text="  ❤ Поддержать автора  ")
        self.build_support_tab()
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def build_support_tab(self):
        panel = ttk.Frame(self.tab_support, padding=24)
        panel.pack(fill="both", expand=True)
        ttk.Label(panel, text="Поддержать разработку ZI-Ops",
                  font=("Segoe UI", 18, "bold")).pack(anchor="w", pady=(0, 12))
        ttk.Label(panel, text="Если программа помогает тебе управлять сервером, можно поддержать её развитие.\n"
                  "Спасибо за поддержку! Донат добровольный — все функции доступны бесплатно.",
                  wraplength=720, justify="left").pack(anchor="w", pady=(0, 20))
        ttk.Button(panel, text="❤ Поддержать через DonationAlerts",
                   style="Accent.TButton", command=self.open_donation_page).pack(anchor="w", pady=(0, 8))
        ttk.Label(panel, text="Пожертвования помогают продолжать развитие и поддержку программы: "
                  "добавлять возможности, улучшать удобство и исправлять ошибки. "
                  "Даже когда программа уже работает хорошо, ваша поддержка помогает "
                  "не останавливаться на достигнутом.",
                  wraplength=720, justify="left").pack(anchor="w", pady=(0, 8))
        ttk.Label(panel, text="Страница пожертвования откроется в браузере.").pack(anchor="w")
        ttk.Button(panel, text="Источник обновлений",
                   command=self.open_updates_page).pack(anchor="w", pady=(20, 8))
        ttk.Label(panel, text="Официальный Telegram-канал DanStudios47.").pack(anchor="w")

    def open_donation_page(self):
        try:
            if webbrowser.open(DONATION_URL, new=2):
                return
        except Exception:
            pass
        messagebox.showwarning(
            "DonationAlerts",
            f"Не удалось открыть браузер. Открой эту ссылку вручную:\n{DONATION_URL}",
        )

    def open_updates_page(self):
        try:
            if webbrowser.open(UPDATES_URL, new=2):
                return
        except Exception:
            pass
        messagebox.showwarning(
            "Источник обновлений",
            f"Не удалось открыть браузер. Открой эту ссылку вручную:\n{UPDATES_URL}",
        )

    # ===== ВАЙП =====
    def show_wipe_notice(self):
        """Show the wipe guide inside the current tab, with no separate window."""
        if self.wipe_notice_panel is not None:
            self.wipe_notice_panel.lift()
            return
        panel = ttk.Frame(self.tab_wipe, padding=16, relief="solid", borderwidth=1)
        self.wipe_notice_panel = panel
        panel.place(relx=0.02, rely=0.02, relwidth=0.96, relheight=0.96)
        panel.lift()
        header = ttk.Frame(panel)
        header.pack(fill="x", pady=(0, 12))
        ttk.Label(header, text="Важное: карты и безопасность настроек",
                  font=("Segoe UI", 13, "bold")).pack(side="left")
        close_button = ttk.Button(header, text="Закрыть", command=self.hide_wipe_notice)
        close_button.pack(side="right", padx=(8, 0))
        body = ttk.Frame(panel)
        body.pack(fill="both", expand=True)
        text = tk.Text(body, wrap="word", bg="#313244", fg="#cdd6f4",
                       font=("Segoe UI", 11), relief="flat", padx=12, pady=12)
        text.pack(side="left", fill="both", expand=True)
        scrollbar = ttk.Scrollbar(body, orient="vertical", command=text.yview)
        scrollbar.pack(side="right", fill="y")
        text.configure(yscrollcommand=scrollbar.set)
        text.tag_configure("title", font=("Segoe UI", 12, "bold"), foreground="#89dceb")
        text.tag_configure("warning", font=("Segoe UI", 12, "bold"), foreground="#f9e2af")
        sections = (
            ("Seed и Map Size\n", "title",
             "Некоторые серверы не используют параметры Seed и Map Size из server.cfg: "
             "они могут задаваться в панели хостинга или параметрах запуска. В таком случае "
             "программу можно использовать для генерации карты на RustMaps, а Seed и размер "
             "карты перенести в настройки сервера вручную.\n\n"),
            ("Как получить RustMaps API Key\n", "title",
             "Генерация карты на RustMaps доступна только после добавления API-ключа "
             "во вкладке «Настройки».\n\n"
             "1. Откройте https://rustmaps.com и нажмите Sign in.\n"
             "2. После входа откройте https://rustmaps.com/dashboard.\n"
             "3. Скопируйте API key и вставьте его в поле «RustMaps API Key» "
             "во вкладке «Настройки». Сохраните настройки.\n\n"),
            ("Время генерации и лимиты\n", "title",
             "Генерация занимает время: это может быть как 3, так и 15 минут, "
             "а при высокой нагрузке — дольше.\n"
             "Точный процент выполнения можно посмотреть в Dashboard: нажмите значок "
             "загрузки в правом нижнем углу. Там отображаются карты, которые сейчас "
             "генерируются с вашим API-ключом.\n"
             "Ориентир по лимитам: 3 карты одновременно и 250 карт в месяц. "
             "Фактические лимиты зависят от подписки; проверьте доступные значения "
             "в своём аккаунте RustMaps.\n\n"),
            ("Ограничения RCON\n", "title",
             "Не все серверы и хостинги разрешают выполнять команды через RCON. "
             "Некоторые команды могут быть ограничены или недоступны даже при "
             "успешном подключении. Если команда не выполняется, проверьте права "
             "доступа и ограничения сервера или уточните их у хостинга.\n\n"),
            ("Не передавайте файл настроек посторонним\n", "warning",
             "Не отправляйте программу вместе с config.json. "
             "В этой версии автоматические настройки сохраняются в config.json. "
             "Файл настроек может содержать адрес сервера, логины и пароли FTP/RCON, "
             "а также RustMaps API Key, если вы их ввели и сохранили.\n\n"
             "Если передаёте такой файл другому человеку, вы доверяете ему доступ "
             "к серверу и принимаете связанные с этим риски."),
        )
        for title, tag, content in sections:
            text.insert("end", title, tag)
            text.insert("end", content)
        text.configure(state="disabled")
        links = ttk.Frame(panel)
        links.pack(fill="x", pady=(12, 0))
        ttk.Button(links, text="Открыть RustMaps",
                   command=lambda: webbrowser.open("https://rustmaps.com", new=2)).pack(side="left", padx=(0, 8))
        ttk.Button(links, text="Открыть Dashboard",
                   command=lambda: webbrowser.open("https://rustmaps.com/dashboard", new=2)).pack(side="left")
        close_button.focus_set()

    def hide_wipe_notice(self):
        if self.wipe_notice_panel is not None:
            self.wipe_notice_panel.destroy()
            self.wipe_notice_panel = None

    def build_wipe_tab(self):
        notice_bar = ttk.Frame(self.tab_wipe)
        notice_bar.pack(fill="x", padx=10, pady=(8, 0))
        ttk.Button(notice_bar, text="⚠ Важное", command=self.show_wipe_notice).pack(side="right")
        self.wipe_notice_panel = None
        seed_frame = ttk.LabelFrame(self.tab_wipe, text=" 🗺️ Авто-вайп: Seed + Restart ", padding=10)
        seed_frame.pack(fill="x", padx=10, pady=(10, 5))

        self.wipe_change_seed_var = tk.BooleanVar(value=False)
        cb_seed = ttk.Checkbutton(seed_frame, text="Сгенерировать новый seed и записать в server.cfg",
                        variable=self.wipe_change_seed_var)
        cb_seed.grid(row=0, column=0, columnspan=5, sticky="w", pady=(0, 6))
        Tooltip(cb_seed, "Если включено — при вайпе программа сгенерирует новый seed и запишет его в server.cfg на сервере")

        lbl_cfg = ttk.Label(seed_frame, text="Шаблон server.cfg (локальный файл):")
        lbl_cfg.grid(row=1, column=0, sticky="w", padx=4, pady=4)
        Tooltip(lbl_cfg, "Укажи локальный server.cfg — программа заменит в нём seed и worldsize, и загрузит на сервер")
        self.wipe_cfg_template_var = tk.StringVar()
        cfg_frame = ttk.Frame(seed_frame)
        cfg_frame.grid(row=1, column=1, columnspan=4, sticky="ew", padx=4, pady=4)
        ttk.Entry(cfg_frame, textvariable=self.wipe_cfg_template_var, width=45).pack(side="left", fill="x", expand=True, padx=(0, 4))
        btn_br = ttk.Button(cfg_frame, text="Обзор...", command=lambda: self.browse_file(self.wipe_cfg_template_var))
        btn_br.pack(side="left", padx=(0, 4))
        Tooltip(btn_br, "Выбрать локальный файл server.cfg с ПК")
        btn_pr = ttk.Button(cfg_frame, text="🧪 Проверить", command=self.preview_cfg_template)
        btn_pr.pack(side="left")
        Tooltip(btn_pr, "Предпросмотр содержимого server.cfg без изменений")

        ttk.Label(seed_frame, text="📥 Скачай server.cfg с сервера через FTP → укажи путь здесь  |  ✅ Оригинал на ПК НЕ изменится",
                  foreground="#89dceb").grid(row=2, column=0, columnspan=5, sticky="w", padx=4)

        self.wipe_random_seed_var = tk.BooleanVar(value=True)
        cb_rand = ttk.Checkbutton(seed_frame, text="Случайный seed", variable=self.wipe_random_seed_var,
                        command=self.toggle_seed_field)
        cb_rand.grid(row=3, column=0, sticky="w", padx=4, pady=4)
        Tooltip(cb_rand, "Если включено — seed генерируется случайно при каждом вайпе. Если выключено — используется указанный ниже seed")
        lbl_seed = ttk.Label(seed_frame, text="Seed:")
        lbl_seed.grid(row=3, column=1, sticky="w", padx=4)
        Tooltip(lbl_seed, "Seed карты — уникальное число от 1 до 2147483647. Определяет генерацию мира Rust")
        self.wipe_seed_var = tk.StringVar(value=str(random.randint(1000000, 2147483647)))
        self.wipe_seed_entry = ttk.Entry(seed_frame, textvariable=self.wipe_seed_var, width=20)
        self.wipe_seed_entry.grid(row=3, column=2, sticky="w", padx=4)
        Tooltip(self.wipe_seed_entry, "Введи seed вручную или сгенерируй случайный / через RustMaps API")
        btn_gen = ttk.Button(seed_frame, text="1 Сгенерировать seed", command=self.generate_random_seed)
        btn_gen.grid(row=3, column=3, sticky="w", padx=4)
        Tooltip(btn_gen, "Шаг 1: Сгенерировать случайный seed прямо в программе (без интернета)")
        btn_rust = ttk.Button(seed_frame, text="2 Генерировать на RustMaps",
                   command=lambda: self.generate_via_rustmaps(self.wipe_seed_var, self.wipe_worldsize_var, self.wipe_log))
        btn_rust.grid(row=3, column=4, sticky="w", padx=4)
        Tooltip(btn_rust, "Шаг 2: Сгенерировать карту на rustmaps.com по текущему seed. Может занять 3–15 минут или дольше. Прогресс смотри в Dashboard; не нажимай повторно!")

        lbl_ws = ttk.Label(seed_frame, text="Размер карты:")
        lbl_ws.grid(row=4, column=0, sticky="w", padx=4, pady=4)
        Tooltip(lbl_ws, "Размер игрового мира в метрах. Стандартные значения: 3000, 3500, 4250 (стандарт), 5000, 6000")
        self.wipe_worldsize_var = tk.StringVar(value="4250")
        ent_ws = ttk.Entry(seed_frame, textvariable=self.wipe_worldsize_var, width=10)
        ent_ws.grid(row=4, column=1, sticky="w", padx=4)
        Tooltip(ent_ws, "Размер карты в метрах. 4250 — стандарт для большинства серверов")
        ttk.Label(seed_frame, text="(например: 3000, 3500, 4250, 5000 — как на rustmaps.com)", foreground="#89dceb").grid(row=4, column=2, columnspan=3, sticky="w", padx=4)

        ttk.Label(seed_frame, text="📋 Если шаблон не указан — seed скопируется в буфер обмена", foreground="#89dceb").grid(row=5, column=0, columnspan=5, sticky="w", padx=4, pady=(4, 0))

        self.wipe_restart_var = tk.BooleanVar(value=False)
        cb_restart = ttk.Checkbutton(seed_frame, text="Отправить рестарт через RCON после очистки",
                        variable=self.wipe_restart_var)
        cb_restart.grid(row=6, column=0, columnspan=5, sticky="w", pady=(4, 0))
        Tooltip(cb_restart, "После удаления файлов отправит команду restart через RCON (требует подключения RCON)")

        lbl_timer = ttk.Label(seed_frame, text="Таймер (сек):")
        lbl_timer.grid(row=7, column=0, sticky="w", padx=4, pady=4)
        Tooltip(lbl_timer, "Через сколько секунд сервер перезапустится после отправки команды")
        self.wipe_restart_sec_var = tk.StringVar(value="60")
        ent_timer = ttk.Entry(seed_frame, textvariable=self.wipe_restart_sec_var, width=10)
        ent_timer.grid(row=7, column=1, sticky="w", padx=4)
        Tooltip(ent_timer, "Время до рестарта в секундах. 60 = 1 минута")

        lbl_msg = ttk.Label(seed_frame, text="Сообщение:")
        lbl_msg.grid(row=8, column=0, sticky="w", padx=4, pady=4)
        Tooltip(lbl_msg, "Сообщение, которое увидят игроки перед рестартом (отправляется через say)")
        self.wipe_restart_msg_var = tk.StringVar(value="Вайп сервера! Рестарт через 60 секунд...")
        ent_msg = ttk.Entry(seed_frame, textvariable=self.wipe_restart_msg_var, width=60)
        ent_msg.grid(row=8, column=1, columnspan=4, sticky="ew", padx=4)
        Tooltip(ent_msg, "Текст объявления для игроков перед рестартом")
        seed_frame.columnconfigure(4, weight=1)

        files_frame = ttk.LabelFrame(self.tab_wipe, text=" Файлы для удаления ", padding=6)
        files_frame.pack(fill="x", padx=10, pady=5)
        Tooltip(files_frame, "Список файлов, которые будут удалены с сервера через FTP при вайпе. Указывай пути относительно базового пути")
        files_frame.rowconfigure(0, weight=1); files_frame.columnconfigure(0, weight=1)
        self.wipe_files_text = tk.Text(files_frame, wrap="none", height=8, bg="#313244", fg="#cdd6f4",
                                       insertbackground="#cdd6f4", font=("Consolas", 9), relief="flat", bd=2)
        self.wipe_files_text.grid(row=0, column=0, sticky="nsew")
        for f in self.DEFAULT_WIPE_FILES: self.wipe_files_text.insert("end", f + "\n")
        fs = ttk.Scrollbar(files_frame, orient="vertical", command=self.wipe_files_text.yview)
        fs.grid(row=0, column=1, sticky="ns")
        self.wipe_files_text.config(yscrollcommand=fs.set)
        ff = ttk.Frame(files_frame); ff.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(4, 0))
        btn_lf = ttk.Button(ff, text="Загрузить", command=lambda: self.load_text(self.wipe_files_text))
        btn_lf.pack(side="left", padx=2)
        Tooltip(btn_lf, "Загрузить список файлов из .txt файла")
        btn_sf = ttk.Button(ff, text="Сохранить", command=lambda: self.save_text(self.wipe_files_text))
        btn_sf.pack(side="left", padx=2)
        Tooltip(btn_sf, "Сохранить список файлов в .txt файл")
        btn_rf = ttk.Button(ff, text="Сбросить", command=self.reset_wipe_files)
        btn_rf.pack(side="left", padx=2)
        Tooltip(btn_rf, "Вернуть стандартный список файлов для удаления")

        folders_frame = ttk.LabelFrame(self.tab_wipe, text=" Папки для очистки ", padding=6)
        folders_frame.pack(fill="x", padx=10, pady=5)
        Tooltip(folders_frame, "Список папок, содержимое которых будет полностью удалено с сервера (включая подпапки и файлы)")
        folders_frame.rowconfigure(0, weight=1); folders_frame.columnconfigure(0, weight=1)
        self.wipe_folders_text = tk.Text(folders_frame, wrap="none", height=4, bg="#313244", fg="#cdd6f4",
                                         insertbackground="#cdd6f4", font=("Consolas", 9), relief="flat", bd=2)
        self.wipe_folders_text.grid(row=0, column=0, sticky="nsew")
        for f in self.DEFAULT_WIPE_FOLDERS: self.wipe_folders_text.insert("end", f + "\n")
        fs2 = ttk.Scrollbar(folders_frame, orient="vertical", command=self.wipe_folders_text.yview)
        fs2.grid(row=0, column=1, sticky="ns")
        self.wipe_folders_text.config(yscrollcommand=fs2.set)
        ff2 = ttk.Frame(folders_frame); ff2.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(4, 0))
        btn_lfo = ttk.Button(ff2, text="Загрузить", command=lambda: self.load_text(self.wipe_folders_text))
        btn_lfo.pack(side="left", padx=2)
        Tooltip(btn_lfo, "Загрузить список папок из .txt файла")
        btn_sfo = ttk.Button(ff2, text="Сохранить", command=lambda: self.save_text(self.wipe_folders_text))
        btn_sfo.pack(side="left", padx=2)
        Tooltip(btn_sfo, "Сохранить список папок в .txt файл")
        btn_rfo = ttk.Button(ff2, text="Сбросить", command=self.reset_wipe_folders)
        btn_rfo.pack(side="left", padx=2)
        Tooltip(btn_rfo, "Вернуть стандартный список папок для очистки")

        ctrl = ttk.Frame(self.tab_wipe); ctrl.pack(fill="x", padx=10, pady=(5, 5))
        self.wipe_start_btn = ttk.Button(ctrl, text="▶ Запустить вайп", style="Accent.TButton", command=self.start_wipe)
        self.wipe_start_btn.pack(side="left", padx=(0, 8))
        Tooltip(self.wipe_start_btn, "Начинает вайп: удаляет файлы/папки → обновляет seed → отправляет рестарт (если включено)")
        self.wipe_stop_btn = ttk.Button(ctrl, text="⏹ Остановить", style="Danger.TButton", command=self.request_stop, state="disabled")
        self.wipe_stop_btn.pack(side="left", padx=(0, 8))
        Tooltip(self.wipe_stop_btn, "Остановить текущий процесс вайпа (после завершения текущей операции)")
        self.wipe_progress = ttk.Progressbar(ctrl, mode="determinate", length=200)
        self.wipe_progress.pack(side="right", padx=(8, 0))
        self.wipe_status_var = tk.StringVar(value="Готов")
        ttk.Label(ctrl, textvariable=self.wipe_status_var).pack(side="right", padx=8)

        log_frame = ttk.LabelFrame(self.tab_wipe, text=" Лог ", padding=6)
        log_frame.pack(fill="both", expand=True, padx=10, pady=(5, 10))
        log_frame.rowconfigure(0, weight=1); log_frame.columnconfigure(0, weight=1)
        self.wipe_log = tk.Text(log_frame, wrap="word", state="disabled", bg="#181825", fg="#cdd6f4",
                                font=("Consolas", 10), relief="flat", bd=2)
        self.wipe_log.grid(row=0, column=0, sticky="nsew")
        ls = ttk.Scrollbar(log_frame, orient="vertical", command=self.wipe_log.yview)
        ls.grid(row=0, column=1, sticky="ns")
        self.wipe_log.config(yscrollcommand=ls.set)
        self._config_log_tags(self.wipe_log)

    # ===== СУДНАЯ НОЧЬ =====
    def build_judgment_tab(self):
        on_frame = ttk.LabelFrame(self.tab_judgment, text=" 🔴 Включение судной ночи ", padding=10)
        on_frame.pack(fill="both", expand=True, padx=10, pady=(10, 5))
        Tooltip(on_frame, "Настройки для ВКЛЮЧЕНИЯ режима Судной ночи. Удаляет PVE-плагины и загружает PVP-конфиг")
        lbl_on_del = ttk.Label(on_frame, text="Файлы для УДАЛЕНИЯ:")
        lbl_on_del.pack(anchor="w")
        Tooltip(lbl_on_del, "Файлы, которые будут УДАЛЕНЫ при ВКЛЮЧЕНИИ судной ночи. Обычно это PVE-плагины (.cs) и их конфиги (.json)")
        self.judg_on_del_text = tk.Text(on_frame, wrap="none", height=4, bg="#313244", fg="#cdd6f4", insertbackground="#cdd6f4", font=("Consolas", 9), relief="flat", bd=2)
        self.judg_on_del_text.pack(fill="both", expand=True, pady=(2, 6))
        for f in self.DEFAULT_JUDGMENT_ON_DELETE: self.judg_on_del_text.insert("end", f + "\n")
        up_frame = ttk.Frame(on_frame); up_frame.pack(fill="x", pady=(0, 6))
        lbl_up = ttk.Label(up_frame, text="Локальный файл для ЗАГРУЗКИ:")
        lbl_up.pack(side="left")
        Tooltip(lbl_up, "Локальный файл на твоём ПК, который будет загружен на сервер при ВКЛЮЧЕНИИ. Обычно это PVP-конфиг или плагин судной ночи")
        self.judg_on_upload_var = tk.StringVar()
        ttk.Entry(up_frame, textvariable=self.judg_on_upload_var, width=50).pack(side="left", padx=(6, 4), fill="x", expand=True)
        ttk.Button(up_frame, text="Обзор...", command=lambda: self.browse_file(self.judg_on_upload_var)).pack(side="left")
        lbl_rem = ttk.Label(on_frame, text="Удалённый путь:")
        lbl_rem.pack(anchor="w")
        Tooltip(lbl_rem, "Путь на сервере, куда загрузить файл. Например: oxide/plugins/JudgmentNight.cs или oxide/data/JudgmentMode.json")
        self.judg_on_remote_var = tk.StringVar(value=self.DEFAULT_JUDGMENT_ON_REMOTE)
        ent_rem = ttk.Entry(on_frame, textvariable=self.judg_on_remote_var)
        ent_rem.pack(fill="x", pady=(2, 0))
        Tooltip(ent_rem, "Укажи куда на сервере загрузить файл. Путь относительно базового пути FTP")
        btn_on = ttk.Button(on_frame, text="🌑 Включить судную ночь", style="Warn.TButton", command=lambda: self.run_judgment(True))
        btn_on.pack(anchor="e", pady=(8, 0))
        Tooltip(btn_on, "Запускает процесс: удаляет указанные файлы → загружает PVP-файл на сервер. Всё через FTP.")

        off_frame = ttk.LabelFrame(self.tab_judgment, text=" 🟢 Выключение судной ночи ", padding=10)
        off_frame.pack(fill="both", expand=True, padx=10, pady=5)
        Tooltip(off_frame, "Настройки для ВЫКЛЮЧЕНИЯ режима Судной ночи. Удаляет PVP-плагин и возвращает PVE-файлы")
        lbl_off_del = ttk.Label(off_frame, text="Файлы для УДАЛЕНИЯ:")
        lbl_off_del.pack(anchor="w")
        Tooltip(lbl_off_del, "Файлы, которые будут УДАЛЕНЫ при ВЫКЛЮЧЕНИИ судной ночи. Обычно это PVP-плагин судной ночи (.cs)")
        self.judg_off_del_text = tk.Text(off_frame, wrap="none", height=3, bg="#313244", fg="#cdd6f4", insertbackground="#cdd6f4", font=("Consolas", 9), relief="flat", bd=2)
        self.judg_off_del_text.pack(fill="both", expand=True, pady=(2, 6))
        for f in self.DEFAULT_JUDGMENT_OFF_DELETE: self.judg_off_del_text.insert("end", f + "\n")
        lbl_off_up = ttk.Label(off_frame, text="Локальные файлы для ЗАГРУЗКИ (2 файла):")
        lbl_off_up.pack(anchor="w")
        Tooltip(lbl_off_up, "Файлы с твоего ПК, которые вернут сервер в обычный PVE-режим. Обычно TruePVE.cs и NoMLRSMount.cs")
        self.judg_off_upload_vars = []; self.judg_off_remote_vars = []
        for i in range(2):
            row = ttk.Frame(off_frame); row.pack(fill="x", pady=(2, 4))
            ttk.Label(row, text=f"Файл {i+1}:", width=8).pack(side="left")
            uv = tk.StringVar(value=self.DEFAULT_JUDGMENT_OFF_UPLOADS[i])
            self.judg_off_upload_vars.append(uv)
            ttk.Entry(row, textvariable=uv, width=40).pack(side="left", padx=(4, 4), fill="x", expand=True)
            ttk.Button(row, text="Обзор...", command=lambda v=uv: self.browse_file(v)).pack(side="left", padx=(0, 8))
            rv = tk.StringVar(value=self.DEFAULT_JUDGMENT_OFF_REMOTES[i])
            self.judg_off_remote_vars.append(rv)
            ttk.Entry(row, textvariable=rv, width=30).pack(side="left")
        btn_off = ttk.Button(off_frame, text="☀️ Выключить судную ночь", style="Success.TButton", command=lambda: self.run_judgment(False))
        btn_off.pack(anchor="e", pady=(8, 0))
        Tooltip(btn_off, "Запускает процесс: удаляет PVP-файл → загружает 2 PVE-файла на сервер. Возвращает обычный режим.")

        ctrl = ttk.Frame(self.tab_judgment); ctrl.pack(fill="x", padx=10, pady=(5, 5))
        self.judg_progress = ttk.Progressbar(ctrl, mode="determinate", length=200)
        self.judg_progress.pack(side="right")
        self.judg_status_var = tk.StringVar(value="Готов")
        ttk.Label(ctrl, textvariable=self.judg_status_var).pack(side="right", padx=8)

        log_frame = ttk.LabelFrame(self.tab_judgment, text=" Лог ", padding=6)
        log_frame.pack(fill="both", expand=True, padx=10, pady=(5, 10))
        log_frame.rowconfigure(0, weight=1); log_frame.columnconfigure(0, weight=1)
        self.judg_log = tk.Text(log_frame, wrap="word", state="disabled", bg="#181825", fg="#cdd6f4", font=("Consolas", 10), relief="flat", bd=2)
        self.judg_log.grid(row=0, column=0, sticky="nsew")
        ls = ttk.Scrollbar(log_frame, orient="vertical", command=self.judg_log.yview)
        ls.grid(row=0, column=1, sticky="ns")
        self.judg_log.config(yscrollcommand=ls.set)
        self._config_log_tags(self.judg_log)

    # ===== RCON =====
    def build_rcon_tab(self):
        warn_label = ttk.Label(self.tab_rcon, text="⚠️ Если используете SurvivalHost — эта панель может не работать", foreground="#f38ba8", font=("Segoe UI", 10, "bold"))
        warn_label.pack(fill="x", padx=10, pady=(10, 0))
        conn_frame = ttk.LabelFrame(self.tab_rcon, text=" Подключение ", padding=10)
        conn_frame.pack(fill="x", padx=10, pady=(10, 5))
        Tooltip(conn_frame, "Настройки подключения к RCON сервера Rust. RCON-порт обычно отличается от игрового порта!")
        self.rcon_conn_status = tk.StringVar(value="Не подключено")
        ttk.Label(conn_frame, textvariable=self.rcon_conn_status, font=("Segoe UI", 10, "bold")).pack(side="left", padx=4)
        ttk.Button(conn_frame, text="🔗 Подключиться", command=self.rcon_connect).pack(side="left", padx=8)
        ttk.Button(conn_frame, text="❌ Отключиться", command=self.rcon_disconnect).pack(side="left", padx=4)
        ttk.Button(conn_frame, text="🧪 Проверить", command=self.rcon_test).pack(side="left", padx=4)

        quick_frame = ttk.LabelFrame(self.tab_rcon, text=" Быстрые команды ", padding=10)
        quick_frame.pack(fill="x", padx=10, pady=5)
        Tooltip(quick_frame, "Готовые команды для быстрой отправки на сервер. Требует подключения RCON.")
        cmds = [
            ("💾 Сохранить мир", "server.save", "Accent.TButton"),
            ("🔄 Рестарт 60с", "restart 60 'Рестарт сервера через 60 секунд'", "Warn.TButton"),
            ("📢 Объявление", 'say "Сообщение от администратора"', "Success.TButton"),
            ("👥 Статус", "status", "Purple.TButton"),
            ("🗺️ Seed", "server.seed", "Purple.TButton"),
            ("🛑 Остановить", "quit", "Danger.TButton"),
        ]
        ttk.Button(quick_frame, text="🌐 RustMaps", command=self.open_rustmaps).pack(side="left", padx=4, pady=4)
        for text, cmd, style in cmds:
            ttk.Button(quick_frame, text=text, style=style, command=lambda c=cmd: self.rcon_send_command(c)).pack(side="left", padx=4, pady=4)

        manual_frame = ttk.LabelFrame(self.tab_rcon, text=" Ручной ввод ", padding=10)
        manual_frame.pack(fill="x", padx=10, pady=5)
        Tooltip(manual_frame, "Введи любую RCON-команду вручную и нажми Enter или кнопку Отправить")
        manual_frame.columnconfigure(0, weight=1)
        self.rcon_cmd_var = tk.StringVar()
        entry = ttk.Entry(manual_frame, textvariable=self.rcon_cmd_var)
        entry.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        entry.bind("<Return>", lambda e: self.rcon_send_command(self.rcon_cmd_var.get()))
        ttk.Button(manual_frame, text="Отправить", style="Accent.TButton",
                   command=lambda: self.rcon_send_command(self.rcon_cmd_var.get())).grid(row=0, column=1)

        seedr_frame = ttk.LabelFrame(self.tab_rcon, text=" Быстрый вайп через RCON ", padding=10)
        seedr_frame.pack(fill="x", padx=10, pady=5)
        Tooltip(seedr_frame, "Быстрая смена seed + рестарт без использования FTP. Команды отправляются напрямую через RCON.")

        self.rcon_random_seed_var = tk.BooleanVar(value=True)
        cb_rcon_rand = ttk.Checkbutton(seedr_frame, text="Случайный", variable=self.rcon_random_seed_var,
                        command=self.toggle_rcon_seed)
        cb_rcon_rand.grid(row=0, column=0, sticky="w", padx=4)
        Tooltip(cb_rcon_rand, "Генерировать случайный seed автоматически при каждом вайпе через RCON")
        lbl_rseed = ttk.Label(seedr_frame, text="Seed:")
        lbl_rseed.grid(row=0, column=1, sticky="w", padx=4)
        Tooltip(lbl_rseed, "Seed для генерации новой карты")
        self.rcon_seed_var = tk.StringVar(value=str(random.randint(1000000, 2147483647)))
        self.rcon_seed_entry = ttk.Entry(seedr_frame, textvariable=self.rcon_seed_var, width=20)
        self.rcon_seed_entry.grid(row=0, column=2, sticky="w", padx=4)
        Tooltip(self.rcon_seed_entry, "Введи seed вручную или сгенерируй случайный")
        ttk.Button(seedr_frame, text="1", command=self.generate_rcon_random_seed, width=3).grid(row=0, column=3, sticky="w", padx=4)
        ttk.Button(seedr_frame, text="2 RustMaps",
                   command=lambda: self.generate_via_rustmaps(self.rcon_seed_var, self.rcon_worldsize_var, self.rcon_log)).grid(row=0, column=4, sticky="w", padx=4)

        lbl_rws = ttk.Label(seedr_frame, text="Размер:")
        lbl_rws.grid(row=1, column=0, sticky="w", padx=4, pady=4)
        Tooltip(lbl_rws, "Размер карты в метрах (3000, 3500, 4250, 5000)")
        self.rcon_worldsize_var = tk.StringVar(value="4250")
        ent_rws = ttk.Entry(seedr_frame, textvariable=self.rcon_worldsize_var, width=10)
        ent_rws.grid(row=1, column=1, sticky="w", padx=4, pady=4)
        Tooltip(ent_rws, "Размер игрового мира. 4250 — стандартное значение")

        lbl_rt = ttk.Label(seedr_frame, text="Таймер:")
        lbl_rt.grid(row=1, column=2, sticky="w", padx=4, pady=4)
        Tooltip(lbl_rt, "Время до рестарта в секундах после отправки команды")
        self.rcon_restart_sec_var = tk.StringVar(value="60")
        ent_rt = ttk.Entry(seedr_frame, textvariable=self.rcon_restart_sec_var, width=10)
        ent_rt.grid(row=1, column=3, sticky="w", padx=4, pady=4)
        Tooltip(ent_rt, "Секунды до рестарта. 60 = 1 минута")

        btn_rw = ttk.Button(seedr_frame, text="🗺️ Сменить seed/worldsize + Restart",
                   style="Accent.TButton", command=self.rcon_full_wipe)
        btn_rw.grid(row=1, column=4, sticky="e", padx=4, pady=4)
        Tooltip(btn_rw, "Меняет seed/worldsize и отправляет save + restart. RCON сам по себе не удаляет файлы мира, поэтому это НЕ FTP-вайп.")
        seedr_frame.columnconfigure(4, weight=1)

        log_frame = ttk.LabelFrame(self.tab_rcon, text=" Консоль RCON ", padding=6)
        log_frame.pack(fill="both", expand=True, padx=10, pady=(5, 10))
        log_frame.rowconfigure(0, weight=1); log_frame.columnconfigure(0, weight=1)
        self.rcon_log = tk.Text(log_frame, wrap="word", state="disabled", bg="#181825", fg="#cdd6f4", font=("Consolas", 10), relief="flat", bd=2)
        self.rcon_log.grid(row=0, column=0, sticky="nsew")
        ls = ttk.Scrollbar(log_frame, orient="vertical", command=self.rcon_log.yview)
        ls.grid(row=0, column=1, sticky="ns")
        self.rcon_log.config(yscrollcommand=ls.set)
        self._config_log_tags(self.rcon_log)
        self.rcon_client = None

    # ===== ПЛАГИНЫ =====
    def build_plugins_tab(self):
        installed_frame = ttk.LabelFrame(self.tab_plugins, text=" 🔍 Установленные плагины на сервере ", padding=10)
        installed_frame.pack(fill="both", expand=True, padx=10, pady=(10, 5))
        Tooltip(installed_frame, "Сканирует .cs плагины на сервере, парсит их версии и сравнивает с актуальными (если указаны ссылки)")
        installed_frame.rowconfigure(1, weight=1); installed_frame.columnconfigure(0, weight=1)

        lbl_pp = ttk.Label(installed_frame, text="Путь на сервере:")
        lbl_pp.grid(row=0, column=0, sticky="w", padx=4, pady=4)
        Tooltip(lbl_pp, "Папка на сервере, где лежат .cs плагины. Обычно oxide/plugins/")
        self.plugins_server_path_var = tk.StringVar(value="oxide/plugins/")
        ent_pp = ttk.Entry(installed_frame, textvariable=self.plugins_server_path_var, width=40)
        ent_pp.grid(row=0, column=1, sticky="w", padx=4, pady=4)
        Tooltip(ent_pp, "FTP-путь к папке с плагинами. Не меняй, если не уверен.")
        btn_chk = ttk.Button(installed_frame, text="🔍 Проверить версии", style="Accent.TButton", command=self.check_plugins_versions)
        btn_chk.grid(row=0, column=2, sticky="w", padx=4, pady=4)
        Tooltip(btn_chk, "Скачивает .cs файлы с сервера, парсит версию из [Info(...)] и сравнивает с данными из списка обновлений")
        ttk.Label(installed_frame, text="(скачивает .cs файлы во временную папку, парсит версию, удаляет)", foreground="#89dceb").grid(row=0, column=3, sticky="w", padx=4, pady=4)

        # Плагины, отмеченные как кастомные, никогда не обновляются кнопкой «Обновить все».
        # Храним сразу нормализованные имена (без .cs), чтобы отметка переживала повторное сканирование.
        self.custom_plugins = set()
        self._installed_item_keys = {}

        self._installed_sort_column = None
        self._installed_sort_reverse = False
        cols = ("Файл", "Название", "Автор", "Текущая", "Последняя", "Кастомный", "Статус")
        self.installed_tree = ttk.Treeview(installed_frame, columns=cols, show="headings", height=8)
        for c in cols:
            self.installed_tree.heading(c, text=c)
            if c not in ("Текущая", "Последняя"):
                self.installed_tree.heading(c, command=lambda column=c: self._sort_installed_plugins(column))
            if c == "Кастомный":
                self.installed_tree.column(c, width=120, minwidth=120, anchor="center", stretch=False)
            else:
                self.installed_tree.column(c, width=90 if c in ("Текущая", "Последняя") else 70 if c=="Статус" else 140 if c=="Файл" else 110)
        self.installed_tree.grid(row=1, column=0, columnspan=4, sticky="nsew", pady=(4, 0))
        tis = ttk.Scrollbar(installed_frame, orient="vertical", command=self.installed_tree.yview)
        tis.grid(row=1, column=4, sticky="ns", pady=(4, 0))
        self.installed_tree.configure(yscrollcommand=tis.set)
        self.installed_tree.bind("<Button-1>", self._on_installed_tree_click, add="+")
        Tooltip(self.installed_tree, "В колонке «Кастомный» нажми на ☐/☑. ☑ = этот плагин будет пропущен при «Обновить все».")
        # Right-click disabled — now handled via scan dialog

        update_frame = ttk.LabelFrame(self.tab_plugins, text=" 🔄 Автообновление плагинов по URL ", padding=10)
        update_frame.pack(fill="x", padx=10, pady=5)
        Tooltip(update_frame, "Список плагинов для автоматического обновления. Программа скачает → загрузит на сервер → удалит с ПК")
        ttk.Label(update_frame, text="Добавь ссылки. Программа скачает → загрузит на сервер → удалит с ПК.", foreground="#89dceb").pack(anchor="w")

        # Header labels for columns
        hdr = ttk.Frame(update_frame)
        hdr.pack(fill="x", padx=2, pady=(2, 0))
        ttk.Label(hdr, text="Название", width=16, font=("Segoe UI", 8, "bold"), foreground="#89b4fa").pack(side="left", padx=2)
        ttk.Label(hdr, text="URL скачивания (.cs)", width=30, font=("Segoe UI", 8, "bold"), foreground="#89b4fa").pack(side="left", padx=2, fill="x", expand=True)
        ttk.Label(hdr, text="Страница версии", width=24, font=("Segoe UI", 8, "bold"), foreground="#89b4fa").pack(side="left", padx=2)
        ttk.Label(hdr, text="Путь на сервере", width=20, font=("Segoe UI", 8, "bold"), foreground="#89b4fa").pack(side="left", padx=2)
        ttk.Label(hdr, text="", width=4).pack(side="left", padx=2)

        url_frame = ttk.Frame(update_frame)
        url_frame.pack(fill="both", expand=True, pady=5)
        url_frame.rowconfigure(0, weight=1); url_frame.columnconfigure(0, weight=1)

        self.plugins_canvas = tk.Canvas(url_frame, bg="#1e1e2e", highlightthickness=0, height=150)
        self.plugins_canvas.grid(row=0, column=0, sticky="nsew")
        vsb = ttk.Scrollbar(url_frame, orient="vertical", command=self.plugins_canvas.yview)
        vsb.grid(row=0, column=1, sticky="ns")
        self.plugins_canvas.configure(yscrollcommand=vsb.set)

        self.plugins_container = ttk.Frame(self.plugins_canvas)
        self.plugins_canvas.create_window((0, 0), window=self.plugins_container, anchor="nw")
        self.plugins_container.bind("<Configure>", lambda e: self.plugins_canvas.configure(scrollregion=self.plugins_canvas.bbox("all")))

        self.plugin_rows = []

        btn_frame = ttk.Frame(update_frame)
        btn_frame.pack(fill="x", pady=5)
        ttk.Button(btn_frame, text="➕ Добавить", command=self.add_plugin_row).pack(side="left", padx=4)
        ttk.Button(btn_frame, text="💾 Сохранить список", command=self.save_plugins_list).pack(side="left", padx=4)
        ttk.Button(btn_frame, text="📂 Загрузить список", command=self.load_plugins_list).pack(side="left", padx=4)
        ttk.Button(btn_frame, text="🗑️ Очистить", command=self.clear_plugins).pack(side="left", padx=4)
        btn_upall = ttk.Button(btn_frame, text="🔄 Обновить все", style="Accent.TButton", command=self.update_all_plugins)
        btn_upall.pack(side="right", padx=4)
        Tooltip(btn_upall, "Скачивает все плагины по URL из списка и загружает их на сервер через FTP")

        self.plugins_progress = ttk.Progressbar(self.tab_plugins, mode="determinate", length=300)
        self.plugins_progress.pack(fill="x", padx=10, pady=(5, 0))
        self.plugins_status_var = tk.StringVar(value="Готов")
        ttk.Label(self.tab_plugins, textvariable=self.plugins_status_var).pack(anchor="e", padx=10)

        log_frame = ttk.LabelFrame(self.tab_plugins, text=" Лог ", padding=6)
        log_frame.pack(fill="both", expand=True, padx=10, pady=(5, 10))
        log_frame.rowconfigure(0, weight=1); log_frame.columnconfigure(0, weight=1)
        self.plugins_log = tk.Text(log_frame, wrap="word", state="disabled", bg="#181825", fg="#cdd6f4", font=("Consolas", 10), relief="flat", bd=2)
        self.plugins_log.grid(row=0, column=0, sticky="nsew")
        ls = ttk.Scrollbar(log_frame, orient="vertical", command=self.plugins_log.yview)
        ls.grid(row=0, column=1, sticky="ns")
        self.plugins_log.config(yscrollcommand=ls.set)
        self._config_log_tags(self.plugins_log)

    def validate_all_urls(self):
        """Проверяет все URL в списке и подсвечивает битые красным"""
        if not self.plugin_rows:
            self.log(self.plugins_log, "Список пуст.", "yellow")
            return
        self.log(self.plugins_log, "⏳ Проверка URL...", "cyan")
        for row in self.plugin_rows:
            url = row["url"].get().strip()
            name = row["name"].get().strip() or "plugin"
            if not url:
                self.log(self.plugins_log, f"⚠️ {name}: URL пустой", "yellow")
                continue
            ok, msg = self._validate_plugin_url(url)
            # Find URL entry and color it
            for child in row["frame"].winfo_children():
                if isinstance(child, ttk.Entry):
                    # Check if this entry is bound to url var
                    try:
                        if child.cget("textvariable") == str(row["url"]):
                            if ok:
                                child.configure(foreground="#cdd6f4")
                            else:
                                child.configure(foreground="#f38ba8")
                    except Exception:
                        pass
            if ok:
                self.log(self.plugins_log, f"✅ {name}: {msg}", "green")
            else:
                self.log(self.plugins_log, f"❌ {name}: {msg}", "red")
        self.log(self.plugins_log, "Готово! Красные = битые ссылки.", "cyan")

    def add_plugin_row(self, name="", url="", page="", remote="oxide/plugins/"):
        frame = ttk.Frame(self.plugins_container)
        frame.pack(fill="x", pady=2)
        nv = tk.StringVar(value=name)
        uv = tk.StringVar(value=url)
        pv = tk.StringVar(value=page)
        rv = tk.StringVar(value=remote)
        # Name
        ent_n = ttk.Entry(frame, textvariable=nv, width=16)
        ent_n.pack(side="left", padx=2)
        Tooltip(ent_n, "Название плагина (как в [Info(...)] в .cs файле). Например: TruePVE или Backpack")
        # URL
        ent_u = ttk.Entry(frame, textvariable=uv, width=30)
        ent_u.pack(side="left", padx=2, fill="x", expand=True)
        Tooltip(ent_u, "ПРЯМАЯ ссылка на скачивание .cs файла. Например: https://github.com/.../PluginName.cs или https://umod.org/.../download")
        # Page
        ent_p = ttk.Entry(frame, textvariable=pv, width=24)
        ent_p.pack(side="left", padx=2)
        Tooltip(ent_p, "Страница для проверки актуальной версии. Например: https://github.com/автор/репо/releases или https://umod.org/plugins/plugin-name")
        # Remote
        ent_r = ttk.Entry(frame, textvariable=rv, width=20)
        ent_r.pack(side="left", padx=2)
        Tooltip(ent_r, "Путь на сервере куда загрузить. Например: oxide/plugins/ или oxide/plugins/PluginName.cs")
        ttk.Button(frame, text="❌", width=3, command=lambda f=frame: self.remove_plugin_row(f)).pack(side="left", padx=2)
        self.plugin_rows.append({"name": nv, "url": uv, "page": pv, "remote": rv, "frame": frame})

    def remove_plugin_row(self, frame):
        for i, row in enumerate(self.plugin_rows):
            if row["frame"] == frame:
                self.plugin_rows.pop(i)
                break
        frame.destroy()

    def clear_plugins(self):
        for row in self.plugin_rows:
            row["frame"].destroy()
        self.plugin_rows.clear()

    def save_plugins_list(self):
        data = [{"name": r["name"].get(), "url": r["url"].get(), "page": r["page"].get(), "remote": r["remote"].get()} for r in self.plugin_rows]
        path = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON", "*.json")], initialfile="plugUpdater.json")
        if path:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            self.log(self.plugins_log, f"Список сохранён: {path}", "cyan")

    def load_plugins_list(self):
        path = filedialog.askopenfilename(filetypes=[("JSON", "*.json"), ("All", "*.*")])
        if path:
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self.clear_plugins()
                for item in data:
                    self.add_plugin_row(item.get("name", ""), item.get("url", ""), item.get("page", ""), item.get("remote", "oxide/plugins/"))
                self.log(self.plugins_log, f"Загружено плагинов: {len(data)}", "cyan")
            except Exception as e:
                self.log(self.plugins_log, f"Ошибка загрузки: {e}", "red")

    def check_plugins_versions(self):
        with self.running_lock:
            if self._running:
                return
            self._running = True

        self.stop_event.clear()
        # Все значения Tk читаем только в главном потоке.
        base = self.base_var.get().strip()
        remote_folder = self.plugins_server_path_var.get().strip()
        rows = [{
            "name": self._plugin_key(r["name"].get()),
            "remote": self._remote_basename(r["remote"].get()).lower(),
            "page": r["page"].get().strip()
        } for r in self.plugin_rows]
        # Снимок FTP-настроек делаем в UI-потоке: worker не должен читать Tkinter
        # StringVar/BooleanVar напрямую. Это также позволяет безопасно переподключаться
        # при ошибке FTP 425 из фонового потока.
        ftp_cfg = self._snapshot_ftp_config()

        self.plugins_status_var.set("Проверка...")
        self.plugins_progress["value"] = 0
        self.installed_tree.delete(*self.installed_tree.get_children())
        self._installed_item_keys.clear()
        self.plugins_log.config(state="normal")
        self.plugins_log.delete("1.0", "end")
        self.plugins_log.config(state="disabled")

        threading.Thread(
            target=self._check_plugins_worker,
            args=(base, remote_folder, rows, ftp_cfg),
            daemon=True
        ).start()

    def _validate_plugin_url(self, url):
        """Проверяет URL без предположения, что сервер поддерживает HEAD."""
        if not url:
            return False, "URL пустой"
        try:
            headers = {
                "User-Agent": "ZI-Ops/1.0",
                "Accept": "text/plain,application/octet-stream,*/*",
            }
            req = urllib.request.Request(url, headers=headers, method="HEAD")
            try:
                with urllib.request.urlopen(req, timeout=10) as resp:
                    ct = (resp.headers.get("Content-Type") or "").lower()
                    if "text/html" in ct:
                        return False, "Сервер отдаёт HTML вместо .cs"
                    return True, f"OK ({resp.status})"
            except urllib.error.HTTPError as e:
                if e.code not in (405, 501):
                    return False, f"HTTP {e.code}: {e.reason}"
            # GET fallback, only download a small prefix.
            req = urllib.request.Request(url, headers=headers, method="GET")
            with urllib.request.urlopen(req, timeout=15) as resp:
                prefix = resp.read(4096)
                ct = (resp.headers.get("Content-Type") or "").lower()
                if "text/html" in ct or re.search(br"<(?:!doctype\s+html|html|body)\b", prefix, re.I):
                    return False, "Сервер отдаёт HTML вместо .cs"
                if not prefix.strip():
                    return False, "Пустой ответ"
                return True, f"OK ({resp.status})"
        except urllib.error.HTTPError as e:
            return False, f"HTTP {e.code}: {e.reason}"
        except urllib.error.URLError as e:
            return False, f"Сеть: {e.reason}"
        except Exception as e:
            return False, str(e)

    def _show_add_plugin_dialog(self, name, filename, on_add_callback, on_skip_callback, on_skip_all_callback):
        """Диалог добавления плагина в список обновлений"""
        dlg = tk.Toplevel(self.root)
        dlg.title(f"Добавить плагин: {name}")
        dlg.geometry("550x320")
        dlg.configure(bg="#1e1e2e")
        dlg.transient(self.root)
        dlg.grab_set()
        dlg.resizable(False, False)

        ttk.Label(dlg, text=f"Плагин '{name}' ({filename}) не найден в списке автообновления.",
                  font=("Segoe UI", 10, "bold")).pack(anchor="w", padx=12, pady=(12, 4))
        ttk.Label(dlg, text="Заполни данные для автоматического обновления:", foreground="#89dceb").pack(anchor="w", padx=12, pady=(0, 8))

        # URL
        f1 = ttk.Frame(dlg); f1.pack(fill="x", padx=12, pady=4)
        ttk.Label(f1, text="URL скачивания (.cs):", width=18).pack(side="left")
        url_var = tk.StringVar()
        ent_url = ttk.Entry(f1, textvariable=url_var, width=50)
        ent_url.pack(side="left", padx=4, fill="x", expand=True)
        Tooltip(ent_url, "Прямая ссылка на .cs файл. Пример: https://github.com/.../Plugin.cs")

        # Test URL button
        f1b = ttk.Frame(dlg); f1b.pack(fill="x", padx=12, pady=(0, 4))
        lbl_test = ttk.Label(f1b, text="", foreground="#a6e3a1")
        lbl_test.pack(side="left", padx=(180, 0))
        def test_url():
            lbl_test.config(text="⏳ Проверка...", foreground="#89dceb")
            dlg.update()
            ok, msg = self._validate_plugin_url(url_var.get().strip())
            if ok:
                lbl_test.config(text=f"✅ {msg}", foreground="#a6e3a1")
            else:
                lbl_test.config(text=f"❌ {msg}", foreground="#f38ba8")
        ttk.Button(f1b, text="🧪 Проверить URL", command=test_url).pack(side="right")

        # Page
        f2 = ttk.Frame(dlg); f2.pack(fill="x", padx=12, pady=4)
        ttk.Label(f2, text="Страница версии:", width=18).pack(side="left")
        page_var = tk.StringVar()
        ent_page = ttk.Entry(f2, textvariable=page_var, width=50)
        ent_page.pack(side="left", padx=4, fill="x", expand=True)
        Tooltip(ent_page, "Страница для проверки версии. Пример: https://umod.org/plugins/plugin-name или GitHub releases")

        # Remote path
        f3 = ttk.Frame(dlg); f3.pack(fill="x", padx=12, pady=4)
        ttk.Label(f3, text="Путь на сервере:", width=18).pack(side="left")
        remote_var = tk.StringVar(value=f"oxide/plugins/{filename}")
        ttk.Entry(f3, textvariable=remote_var, width=50).pack(side="left", padx=4, fill="x", expand=True)

        # Buttons
        f4 = ttk.Frame(dlg); f4.pack(fill="x", padx=12, pady=(12, 8))
        skip_all_var = [False]
        def on_add():
            url = url_var.get().strip()
            page = page_var.get().strip()
            remote = remote_var.get().strip()
            if not url:
                messagebox.showwarning("URL", "Укажи URL скачивания", parent=dlg)
                return
            dlg.destroy()
            on_add_callback(name, url, page, remote)
        def on_skip():
            dlg.destroy()
            on_skip_callback()
        def on_skip_all():
            skip_all_var[0] = True
            dlg.destroy()
            on_skip_all_callback()

        ttk.Button(f4, text="➕ Добавить", style="Accent.TButton", command=on_add).pack(side="left", padx=4)
        ttk.Button(f4, text="⏭ Пропустить", command=on_skip).pack(side="left", padx=4)
        ttk.Button(f4, text="⏭ Пропустить все", command=on_skip_all).pack(side="left", padx=4)

        self.root.wait_window(dlg)
        return skip_all_var[0]

    def _highlight_invalid_urls(self):
        """Подсвечивает красным поля с битыми URL в списке автообновления"""
        for row in self.plugin_rows:
            url = row["url"].get().strip()
            if url:
                ok, _ = self._validate_plugin_url(url)
                # Find entry widget in frame
                for child in row["frame"].winfo_children():
                    if isinstance(child, ttk.Entry) and child.cget("textvariable") == str(row["url"]):
                        if not ok:
                            child.configure(foreground="#f38ba8")
                        else:
                            child.configure(foreground="#cdd6f4")
                        break

    def _check_plugins_worker(self, base, remote_folder, rows, ftp_cfg):
        ftp = None
        temp_dir = tempfile.mkdtemp(prefix="ziops_check_")
        try:
            ftp = self.ftp_connect(self.plugins_log, ftp_cfg)
            if not ftp:
                return
            self._check_worker_ftp = ftp

            folder = self._remote_path(base, remote_folder)
            ftp.cwd(folder)
            files = []
            ftp.retrlines("NLST", files.append)
            cs_files = sorted({self._remote_basename(f) for f in files if self._remote_basename(f).lower().endswith(".cs")})
            self.log(self.plugins_log, f"Найдено плагинов: {len(cs_files)}", "cyan")

            total = len(cs_files)
            latest_cache = {}
            for i, filename in enumerate(cs_files, 1):
                if self.stop_event.is_set():
                    self.log(self.plugins_log, "⏹ Проверка остановлена.", "yellow")
                    break
                local_path = os.path.join(temp_dir, f"{i}_{filename}")
                latest_version, status, status_tag = "?", "❓", "yellow"
                try:
                    download_ok = self._ftp_download_with_retry(
                        ftp, folder, filename, local_path, self.plugins_log, ftp_cfg
                    )
                    if not download_ok:
                        raise RuntimeError("FTP download failed after retrying 425/data connection")
                    with open(local_path, "r", encoding="utf-8", errors="ignore") as f:
                        content_file = f.read()

                    name, author, version = self._parse_plugin_info(content_file, filename)
                    version = self._normalize_version(version)
                    base_name = os.path.splitext(filename)[0].lower()

                    matched = next((r for r in rows if r["name"] == base_name or r["remote"] == filename.lower()), None)
                    if matched and matched["page"] and version != "?":
                        page_key = matched["page"].strip()
                        if page_key not in latest_cache:
                            latest_cache[page_key] = self._fetch_latest_version(page_key, self.plugins_log)
                        latest_version = self._normalize_version(latest_cache[page_key])
                        if latest_version != "?":
                            cmp = self._compare_versions(latest_version, version)
                            if cmp is not None and cmp > 0:
                                status, status_tag = "⚠️ Обновление", "red"
                            elif cmp == 0:
                                status, status_tag = "✅ Актуально", "green"
                            elif cmp is not None and cmp < 0:
                                status, status_tag = "ℹ️ На сервере новее", "yellow"

                    self.root.after(0, lambda fn=filename,n=name,a=author,v=version,lv=latest_version,st=status,tg=status_tag:
                        self._insert_plugin_row(fn,n,a,v,lv,st,tg))
                    self.log(self.plugins_log, f"{status} {name} | Установлено: {version} | Последняя: {latest_version}",
                             "green" if status=="✅ Актуально" else "red" if status=="⚠️ Обновление" else "yellow")
                except Exception as e:
                    self.log(self.plugins_log, f"❌ Ошибка {filename}: {e}", "red")
                finally:
                    ftp = getattr(self, "_check_worker_ftp", ftp)
                    try: os.remove(local_path)
                    except OSError: pass

                pct = i / max(total, 1) * 100
                self._set_progress(self.plugins_progress, self.plugins_status_var, pct, f"{int(pct)}%")

            self.log(self.plugins_log, "\n✅ Проверка завершена.", "green")
        except Exception as e:
            self.log(self.plugins_log, f"❌ Ошибка проверки плагинов: {e}", "red")
        finally:
            if ftp:
                try: ftp.quit()
                except Exception:
                    try: ftp.close()
                    except Exception: pass
            try: os.rmdir(temp_dir)
            except OSError: pass
            try:
                del self._check_worker_ftp
            except AttributeError:
                pass
            self.root.after(0, self._plugins_done)

    def _parse_plugin_info(self, text, filename):
        name = os.path.splitext(filename)[0]
        author = "?"
        version = "?"

        literal = r'"((?:\\.|[^"\\])*)"'
        match = re.search(r"\[\s*Info\s*\(\s*" + literal + r"\s*,\s*" + literal
                          + r"\s*,\s*" + literal + r"\s*\)\s*\]", text)
        if match:
            name, author, version = match.groups()
            name = name or os.path.splitext(filename)[0]
            author = author or "?"

        return name, author, self._normalize_version(version)

    @staticmethod
    def _plugin_key(value):
        """Нормализованное имя плагина для сопоставления списка, FTP и отметки «Кастомный»."""
        value = os.path.basename(str(value or "").replace("\\", "/")).strip()
        if value.lower().endswith(".cs"):
            value = value[:-3]
        return value.strip().lower()

    def _is_custom_plugin(self, *values):
        return any(self._plugin_key(v) in self.custom_plugins for v in values if v)

    @staticmethod
    def _plugin_text_sort_key(value):
        """Symbols, digits, Russian alphabet (including ё), Latin, other letters."""
        russian = "абвгдеёжзийклмнопрстуфхцчшщъыьэюя"
        key = []
        for char in str(value or "").casefold():
            if char in russian:
                key.append((2, russian.index(char)))
            elif "a" <= char <= "z":
                key.append((3, ord(char)))
            elif char.isdecimal():
                key.append((1, ord(char)))
            elif char.isalpha():
                key.append((4, ord(char)))
            else:
                key.append((0, ord(char)))
        return tuple(key)

    def _sort_installed_plugins(self, column):
        if column not in ("Файл", "Название", "Автор", "Кастомный", "Статус"):
            return
        if self._installed_sort_column == column:
            self._installed_sort_reverse = not self._installed_sort_reverse
        else:
            self._installed_sort_column = column
            self._installed_sort_reverse = False
        self._apply_installed_plugins_sort()

    def _apply_installed_plugins_sort(self):
        column = self._installed_sort_column
        if column is None:
            return

        def key(item):
            value = self.installed_tree.set(item, column)
            if column == "Кастомный":
                return 0 if value == "☑" else 1
            if column == "Статус":
                tags = self.installed_tree.item(item, "tags")
                if "red" in tags:
                    return 0
                if "green" in tags:
                    return 1
                return 3 if value.strip() == "?" else 2
            return self._plugin_text_sort_key(value)

        items = sorted(self.installed_tree.get_children(), key=key,
                       reverse=self._installed_sort_reverse)
        for index, item in enumerate(items):
            self.installed_tree.move(item, "", index)
        for name in ("Файл", "Название", "Автор", "Кастомный", "Статус"):
            arrow = (" ▼" if self._installed_sort_reverse else " ▲") if name == column else ""
            self.installed_tree.heading(name, text=name + arrow)

    def _on_installed_tree_click(self, event):
        """Переключает ☑ только при клике по колонке «Кастомный»."""
        region = self.installed_tree.identify_region(event.x, event.y)
        column = self.installed_tree.identify_column(event.x)
        item = self.installed_tree.identify_row(event.y)
        if region != "cell" or column != "#6" or not item:
            return

        keys = self._installed_item_keys.get(item, set())
        if not keys:
            values = self.installed_tree.item(item, "values")
            keys = {self._plugin_key(values[0]), self._plugin_key(values[1])}
            keys.discard("")

        currently_custom = any(k in self.custom_plugins for k in keys)
        if currently_custom:
            self.custom_plugins.difference_update(keys)
            mark = "☐"
        else:
            self.custom_plugins.update(keys)
            mark = "☑"

        self.installed_tree.set(item, "Кастомный", mark)
        self._apply_installed_plugins_sort()
        # Сохраняем сразу, чтобы отметка не потерялась при закрытии/повторном запуске.
        self.save_config(silent=True)

    def _insert_plugin_row(self, filename, name, author, version, latest, status, tag):
        keys = {self._plugin_key(filename), self._plugin_key(name)}
        keys.discard("")
        is_custom = any(k in self.custom_plugins for k in keys)
        if is_custom:
            # После перезапуска мог сохраниться только один вариант имени — синхронизируем оба.
            self.custom_plugins.update(keys)
        custom_mark = "☑" if is_custom else "☐"
        item = self.installed_tree.insert("", "end", values=(filename, name, author, version, latest, custom_mark, status))
        self._installed_item_keys[item] = keys
        self.installed_tree.item(item, tags=(tag,))
        self.installed_tree.tag_configure("green", foreground="#a6e3a1")
        self.installed_tree.tag_configure("red", foreground="#f38ba8")
        self.installed_tree.tag_configure("yellow", foreground="#f9e2af")
        self._apply_installed_plugins_sort()

    def _fetch_latest_version(self, page_url, log_widget=None):
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "identity",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        }
        req = urllib.request.Request(page_url, headers=headers)

        # GitHub API
        if "github.com" in page_url:
            parts = page_url.replace("https://", "").replace("http://", "").split("/")
            if len(parts) >= 3:
                owner, repo = parts[1], parts[2]
                api_url = f"https://api.github.com/repos/{owner}/{repo}/releases/latest"
                api_req = urllib.request.Request(api_url, headers={
                    "User-Agent": headers["User-Agent"],
                    "Accept": "application/vnd.github.v3+json"
                })
                try:
                    with urllib.request.urlopen(api_req, timeout=15) as resp:
                        data = json.loads(resp.read().decode("utf-8"))
                        tag = data.get("tag_name", "")
                        return tag.lstrip("v").strip()
                except Exception as e:
                    if log_widget:
                        self.log(log_widget, f"  ⚠️ GitHub API ошибка: {e}", "yellow")
                    return "?"

        # uMod: prefer the official latest.json endpoint.
        # It is much more reliable for version checking than scraping the main page,
        # and uMod documents this JSON-style plugin endpoint for update tooling.
        if "umod.org" in page_url and "/plugins/" in page_url:
            slug = page_url.split("/plugins/")[-1].split("/")[0].split("?")[0].strip()
            base_url = f"https://umod.org/plugins/{slug}"

            # 1) Official per-plugin latest.json.
            latest_json_url = f"{base_url}/latest.json"
            try:
                latest_req = urllib.request.Request(latest_json_url, headers={
                    "User-Agent": headers["User-Agent"],
                    "Accept": "application/json,text/plain,*/*",
                    "Referer": base_url,
                })
                with urllib.request.urlopen(latest_req, timeout=15) as resp:
                    data = json.loads(resp.read().decode("utf-8", errors="ignore"))
                    ver = data.get("version") or data.get("latest_release_version")
                    if ver:
                        return self._normalize_version(ver)
            except urllib.error.HTTPError as e:
                if log_widget:
                    self.log(log_widget, f"  ⚠️ uMod latest.json вернул {e.code} для {slug}, пробуем другие источники...", "yellow")
            except Exception as e:
                if log_widget:
                    self.log(log_widget, f"  ⚠️ uMod latest.json ошибка для {slug}: {e}", "yellow")

            # 2) Legacy API endpoint, kept as a fallback.
            try:
                api_url = f"https://umod.org/api/plugins/{slug}"
                api_req = urllib.request.Request(api_url, headers={
                    "User-Agent": headers["User-Agent"],
                    "Accept": "application/json",
                    "Referer": base_url,
                })
                with urllib.request.urlopen(api_req, timeout=15) as resp:
                    data = json.loads(resp.read().decode("utf-8", errors="ignore"))
                    ver = data.get("latest_release_version") or data.get("version") or data.get("latest_release", {}).get("version")
                    if ver:
                        return self._normalize_version(ver)
            except urllib.error.HTTPError as e:
                if log_widget:
                    self.log(log_widget, f"  ⚠️ uMod API вернул {e.code} для {slug}, пробуем страницу обновлений...", "yellow")
            except Exception as e:
                if log_widget:
                    self.log(log_widget, f"  ⚠️ uMod API ошибка для {slug}: {e}", "yellow")

            # 3) /updates is the correct HTML fallback. The newest release is the
            # first version entry on this page, so do not scrape arbitrary version
            # numbers from the plugin description.
            updates_url = f"{base_url}/updates"
            try:
                updates_req = urllib.request.Request(updates_url, headers=headers)
                with urllib.request.urlopen(updates_req, timeout=15) as resp:
                    html = resp.read().decode("utf-8", errors="ignore")

                # First release heading/version on uMod's updates page.
                patterns = [
                    r'>\s*v(\d+(?:\.\d+){1,3})\s*<',
                    r'\bv(\d+(?:\.\d+){1,3})\b',
                    r'Version\s*[:\s]+v?(\d+(?:\.\d+){1,3})',
                ]
                for pat in patterns:
                    m = re.search(pat, html, re.IGNORECASE)
                    if m:
                        return self._normalize_version(m.group(1))
            except urllib.error.HTTPError as e:
                if log_widget:
                    self.log(log_widget, f"  ⚠️ uMod /updates вернул {e.code} для {slug}.", "yellow")
            except Exception as e:
                if log_widget:
                    self.log(log_widget, f"  ⚠️ uMod /updates ошибка для {slug}: {e}", "yellow")

            # 4) Main plugin page as last resort.
            try:
                html_req = urllib.request.Request(base_url, headers=headers)
                with urllib.request.urlopen(html_req, timeout=15) as resp:
                    html = resp.read().decode("utf-8", errors="ignore")
                patterns = [
                    r'data-version="(\d+\.\d+(?:\.\d+)?)"',
                    r'class="[^"]*version[^"]*"[^>]*>(\d+\.\d+(?:\.\d+)?)<',
                    r'"version"\s*:\s*"(\d+\.\d+(?:\.\d+)?)"',
                ]
                for pat in patterns:
                    m = re.search(pat, html, re.IGNORECASE)
                    if m:
                        return self._normalize_version(m.group(1))
            except urllib.error.HTTPError as e:
                if log_widget:
                    self.log(log_widget, f"  ❌ uMod HTML тоже вернул {e.code} для {slug}. Версия неизвестна.", "red")
            except Exception as e:
                if log_widget:
                    self.log(log_widget, f"  ❌ uMod HTML ошибка для {slug}: {e}", "red")
            return "?"

        # Generic HTML parsing for other sites
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                html = resp.read().decode("utf-8", errors="ignore")
        except urllib.error.HTTPError as e:
            if log_widget:
                self.log(log_widget, f"  ❌ HTTP {e.code} при проверке {page_url}", "red")
            return "?"
        except Exception as e:
            if log_widget:
                self.log(log_widget, f"  ❌ Ошибка запроса: {e}", "red")
            return "?"

        patterns = [
            r"Version[:\s]+([0-9]+\.[0-9]+(?:\.[0-9]+)?)",
            r"v([0-9]+\.[0-9]+(?:\.[0-9]+)?)",
            r'"version"[:\s]+"([0-9]+\.[0-9]+(?:\.[0-9]+)?)"',
            r">([0-9]+\.[0-9]+(?:\.[0-9]+)?)</span>\s*<span[^>]*>Latest",
            r"Version\s*</\w+>\s*<[^>]*>([0-9]+\.[0-9]+(?:\.[0-9]+)?)",
        ]
        for pat in patterns:
            m = re.search(pat, html, re.IGNORECASE)
            if m:
                return m.group(1).strip()
        return "?"

    def _normalize_version(self, version):
        """Нормализует plugin-version в канонический вид.

        Сравнение всегда числовое по компонентам, поэтому:
          1.12.12 > 1.12.1
          1.2.10  > 1.2.9
          "1.5.1" == v1.5.1 == 1.5.1
          1.5 == 1.5.0
        """
        if version is None:
            return "?"
        raw = str(version).strip()
        if not raw or raw == "?":
            return "?"

        # Убираем внешние кавычки и распространённые префиксы.
        raw = raw.strip('"').strip("'").strip()
        raw = re.sub(r"^[vV]\s*", "", raw)

        # Берём именно версионное число, а не случайное число из текста.
        m = re.search(r"(?<!\d)(\d+(?:\.\d+){0,3})(?!\d)", raw)
        if not m:
            return "?"

        parts = [int(x) for x in m.group(1).split(".")]
        while len(parts) < 3:
            parts.append(0)

        # Не удаляем значимые компоненты: 1.12.12 остаётся 1.12.12.
        # Четвёртый компонент поддерживается, если он присутствует.
        return ".".join(str(x) for x in parts)

    def _version_tuple(self, version):
        normalized = self._normalize_version(version)
        if normalized == "?":
            return None
        return tuple(int(x) for x in normalized.split("."))

    def _compare_versions(self, v1, v2):
        """Числовое сравнение версий: -1, 0, 1."""
        p1 = self._version_tuple(v1)
        p2 = self._version_tuple(v2)
        if p1 is None or p2 is None:
            return None

        # Недостающие компоненты считаются нулями.
        n = max(len(p1), len(p2))
        p1 = p1 + (0,) * (n - len(p1))
        p2 = p2 + (0,) * (n - len(p2))

        if p1 < p2:
            return -1
        if p1 > p2:
            return 1
        return 0

    def _version_gte(self, v1, v2):
        """Совместимый helper: True означает v1 >= v2."""
        cmp = self._compare_versions(v1, v2)
        return False if cmp is None else cmp >= 0

    def update_all_plugins(self):
        self.log(self.plugins_log, "🖱️ Запущено обновление плагинов.", "cyan")
        with self.running_lock:
            if self._running:
                self.log(self.plugins_log, "⚠️ Другая операция уже выполняется.", "yellow")
                return
            self._running = True

        rows = []
        skipped_custom = []
        for row in self.plugin_rows:
            name = row["name"].get().strip() or "plugin"
            url = row["url"].get().strip()
            remote = row["remote"].get().strip()

            # Определяем реальное имя целевого .cs так же, как worker обновления.
            url_filename = os.path.basename(urllib.parse.urlparse(url).path) if url else ""
            if not url_filename.lower().endswith(".cs"):
                url_filename = f"{name}.cs"
            remote_name = self._remote_basename(remote) if remote and not remote.endswith("/") else url_filename

            if self._is_custom_plugin(name, remote_name, url_filename):
                skipped_custom.append(name)
                continue

            rows.append({
                "name": name,
                "url": url,
                "remote": remote,
            })
        rows = [r for r in rows if r["url"]]
        if not rows:
            if skipped_custom:
                self.log(self.plugins_log, "🛡️ Кастомные плагины пропущены: " + ", ".join(skipped_custom), "yellow")
            with self.running_lock: self._running = False
            self.log(self.plugins_log, "Список пуст или все URL пустые.", "yellow")
            return

        self.plugins_progress["value"] = 0
        self.plugins_status_var.set("0%")
        self.plugins_log.config(state="normal")
        self.plugins_log.delete("1.0", "end")
        self.plugins_log.config(state="disabled")
        if skipped_custom:
            self.log(self.plugins_log, "🛡️ Кастомные плагины пропущены: " + ", ".join(skipped_custom), "yellow")
        base = self.base_var.get().strip()
        ftp_cfg = self._snapshot_ftp_config()
        threading.Thread(target=self._update_plugins_worker, args=(rows, base, ftp_cfg), daemon=True, name="plugin-update-worker").start()

    def _update_plugins_worker(self, rows, base, ftp_cfg):
        ftp = None
        temp_dir = tempfile.mkdtemp(prefix="ziops_plugins_")
        try:
            ftp = self.ftp_connect(self.plugins_log, ftp_cfg)
            if not ftp:
                return
            total = len(rows)

            for i, row in enumerate(rows, 1):
                name, url, remote = row["name"], row["url"], row["remote"]
                # Имя временного файла может иметь служебный префикс, но он НИКОГДА
                # не должен попадать в имя плагина на Rust-сервере.
                url_filename = os.path.basename(urllib.parse.urlparse(url).path)
                if not url_filename.lower().endswith(".cs"):
                    url_filename = f"{name}.cs"
                plugin_filename = re.sub(r'[^A-Za-z0-9_.-]', '_', url_filename) or f"{name}.cs"
                local_path = os.path.join(temp_dir, f"{i}_{plugin_filename}")
                try:
                    self.log(self.plugins_log, f"[{i}/{total}] Скачивание {name}...", "cyan")
                    req = urllib.request.Request(url, headers={"User-Agent": "ZI-Ops/1.0", "Accept": "text/plain,application/octet-stream,*/*"})
                    with urllib.request.urlopen(req, timeout=45) as resp:
                        data = resp.read()
                    if not data:
                        raise ValueError("Пустой ответ.")
                    if re.search(br"<(?:!doctype\s+html|html|body)\b", data[:4096], re.I):
                        raise ValueError("Сервер вернул HTML вместо .cs файла.")
                    with open(local_path, "wb") as f:
                        f.write(data)
                    self.log(self.plugins_log, f"  ✅ Скачано: {len(data):,} bytes", "green")

                    if not remote:
                        remote = f"oxide/plugins/{plugin_filename}"
                    elif remote.endswith("/"):
                        remote = remote + plugin_filename
                    remote_path = self._remote_path(base, remote)
                    with open(local_path, "rb") as f:
                        ftp.storbinary(f"STOR {remote_path}", f)
                    self.log(self.plugins_log, f"  ✅ Загружено: {remote_path}", "green")

                except Exception as e:
                    self.log(self.plugins_log, f"  ❌ {name}: {e}", "red")
                finally:
                    try: os.remove(local_path)
                    except OSError: pass

                pct = i / total * 100
                self._set_progress(self.plugins_progress, self.plugins_status_var, pct, f"{int(pct)}%")

            self.log(self.plugins_log, "\n✅ Обновление завершено.", "green")
        except Exception as e:
            self.log(self.plugins_log, f"❌ Ошибка обновления: {e}", "red")
        finally:
            try: ftp.quit() if ftp else None
            except Exception:
                try: ftp.close()
                except Exception: pass
            try: os.rmdir(temp_dir)
            except OSError: pass
            self.root.after(0, self._plugins_done)

    def _plugins_done(self):
        with self.running_lock:
            self._running = False
        self.plugins_status_var.set("Готов")
        self.plugins_progress["value"] = 100

    def build_settings_tab(self):
        ftp_frame = ttk.LabelFrame(self.tab_settings, text=" FTP Настройки ", padding=10)
        ftp_frame.pack(fill="x", padx=10, pady=(10, 5))
        Tooltip(ftp_frame, "Настройки подключения к FTP-серверу хостинга. Данные берутся из панели управления хостингом.")
        self.host_var = tk.StringVar()
        self.port_var = tk.StringVar(value="21")
        self.user_var = tk.StringVar()
        self.pass_var = tk.StringVar()
        self.base_var = tk.StringVar(value="/")
        labels = [("Хост:", self.host_var, "IP-адрес FTP-сервера. Укажи адрес из панели хостинга"),
                  ("Порт:", self.port_var, "Порт FTP / явного FTPS. Обычно 21; неявный FTPS на 990 не поддерживается"),
                  ("Пользователь:", self.user_var, "Логин от FTP. Обычно email или логин от панели хостинга"),
                  ("Пароль:", self.pass_var, "Пароль от FTP. В FileZilla он хранится в base64 — расшифруй перед вводом"),
                  ("Базовый путь:", self.base_var, "Базовая папка на сервере. Например: /server/")]
        for i, (label, var, tip) in enumerate(labels):
            lbl = ttk.Label(ftp_frame, text=label)
            lbl.grid(row=i, column=0, sticky="w", padx=4, pady=4)
            Tooltip(lbl, tip)
            show = "*" if "Пароль" in label else None
            if "Пароль" in label:
                self.ftp_pass_entry = ttk.Entry(ftp_frame, textvariable=var, width=40, show="*")
                self.ftp_pass_entry.grid(row=i, column=1, sticky="ew", padx=4, pady=4)
                Tooltip(self.ftp_pass_entry, tip)
                self.ftp_pass_shown = [True]
                def toggle_ftp_pass(event=None, entry=self.ftp_pass_entry, flag=self.ftp_pass_shown):
                    flag[0] = not flag[0]
                    entry.config(show="" if not flag[0] else "*")
                btn_ftp = ttk.Button(ftp_frame, text="👁", width=3, command=toggle_ftp_pass)
                btn_ftp.grid(row=i, column=2, padx=2)
                Tooltip(btn_ftp, "Показать/скрыть пароль")
            else:
                ent = ttk.Entry(ftp_frame, textvariable=var, width=40, show=show)
                ent.grid(row=i, column=1, sticky="ew", padx=4, pady=4)
                Tooltip(ent, tip)
        self.ftps_var = tk.BooleanVar(value=False)
        cb_ftps = ttk.Checkbutton(ftp_frame, text="Использовать FTPS (TLS/SSL)", variable=self.ftps_var)
        cb_ftps.grid(row=5, column=0, columnspan=2, sticky="w", padx=4, pady=4)
        Tooltip(cb_ftps, "Включи, если хостинг требует шифрованное соединение FTPS. В FileZilla это Protocol=0 (обычный FTP), но некоторые хостинги требуют TLS.")
        ftp_frame.columnconfigure(1, weight=1)

        rcon_frame = ttk.LabelFrame(self.tab_settings, text=" RCON Настройки ", padding=10)
        rcon_frame.pack(fill="x", padx=10, pady=5)
        Tooltip(rcon_frame, "Настройки удалённого управления сервером через RCON. RCON-порт отличается от игрового!")
        self.rcon_host_var = tk.StringVar()
        self.rcon_port_var = tk.StringVar(value="28016")
        self.rcon_pass_var = tk.StringVar()
        self.rcon_path_var = tk.StringVar()
        self.rcon_ssl_var = tk.BooleanVar(value=False)
        rcon_labels = [("Хост:", self.rcon_host_var, "IP сервера. Обычно совпадает с FTP-хостом"),
                       ("Порт:", self.rcon_port_var, "RCON-порт. НЕ игровой порт! Смотри в панели хостинга (обычно 28016 или игровой+1)"),
                       ("Пароль:", self.rcon_pass_var, "Пароль RCON. Задаётся в server.cfg (rcon.password) или в панели хостинга"),
                       ("Путь (опц.):", self.rcon_path_var, "Нестандартный путь WebSocket. Оставь пустым, если не знаешь. Некоторые хостинги используют /rcon")]
        for i, (label, var, tip) in enumerate(rcon_labels):
            lbl = ttk.Label(rcon_frame, text=label)
            lbl.grid(row=i, column=0, sticky="w", padx=4, pady=4)
            Tooltip(lbl, tip)
            show = "*" if "Пароль" in label else None
            placeholder = "Напр: /rcon или оставь пустым"
            if "Пароль" in label:
                self.rcon_pass_entry = ttk.Entry(rcon_frame, textvariable=var, width=40, show="*")
                self.rcon_pass_entry.grid(row=i, column=1, sticky="ew", padx=4, pady=4)
                Tooltip(self.rcon_pass_entry, tip)
                self.rcon_pass_shown = [True]
                def toggle_rcon_pass(event=None, entry=self.rcon_pass_entry, flag=self.rcon_pass_shown):
                    flag[0] = not flag[0]
                    entry.config(show="" if not flag[0] else "*")
                btn_rcon = ttk.Button(rcon_frame, text="👁", width=3, command=toggle_rcon_pass)
                btn_rcon.grid(row=i, column=2, padx=2)
                Tooltip(btn_rcon, "Показать/скрыть пароль")
            else:
                ent = ttk.Entry(rcon_frame, textvariable=var, width=40, show=show)
                ent.grid(row=i, column=1, sticky="ew", padx=4, pady=4)
                Tooltip(ent, tip)
        cb_ssl = ttk.Checkbutton(rcon_frame, text="Использовать SSL/TLS (wss://)", variable=self.rcon_ssl_var)
        cb_ssl.grid(row=4, column=0, columnspan=2, sticky="w", padx=4, pady=4)
        Tooltip(cb_ssl, "Включи, если хостинг требует WSS (WebSocket Secure) вместо обычного WS. Попробуй сначала без галочки.")
        rcon_frame.columnconfigure(1, weight=1)

        api_frame = ttk.LabelFrame(self.tab_settings, text=" RustMaps API ", padding=10)
        api_frame.pack(fill="x", padx=10, pady=5)
        Tooltip(api_frame, "API ключ для rustmaps.com — позволяет генерировать seed через их сервис прямо из программы")
        self.api_key_var = tk.StringVar()
        lbl_api = ttk.Label(api_frame, text="API Key:")
        lbl_api.grid(row=0, column=0, sticky="w", padx=4, pady=4)
        Tooltip(lbl_api, "Получи ключ на https://rustmaps.com/dashboard → API Keys. Бесплатно.")
        self.api_key_entry = ttk.Entry(api_frame, textvariable=self.api_key_var, width=50, show="*")
        self.api_key_entry.grid(row=0, column=1, sticky="ew", padx=4, pady=4)
        Tooltip(self.api_key_entry, "Вставь API ключ с rustmaps.com. Он нужен только для генерации seed через API.")
        self.api_key_shown = [True]
        def toggle_api_key():
            self.api_key_shown[0] = not self.api_key_shown[0]
            self.api_key_entry.config(show="" if not self.api_key_shown[0] else "*")
        btn_api = ttk.Button(api_frame, text="👁 Показать", command=toggle_api_key)
        btn_api.grid(row=0, column=2, padx=4)
        Tooltip(btn_api, "Показать/скрыть API ключ")
        api_frame.columnconfigure(1, weight=1)

        btn_frame = ttk.Frame(self.tab_settings)
        btn_frame.pack(fill="x", padx=10, pady=5)
        btn_save = ttk.Button(btn_frame, text="💾 Сохранить настройки", command=self.save_config)
        btn_save.pack(side="left", padx=4)
        Tooltip(btn_save, "Сохраняет ВСЕ настройки (FTP, RCON, API, списки файлов судной ночи, вайп-списки) в файл rust_manager_config.json")
        btn_load = ttk.Button(btn_frame, text="📂 Загрузить настройки", command=lambda: self.load_config(filedialog.askopenfilename(filetypes=[("JSON", "*.json")])))
        btn_load.pack(side="left", padx=4)
        Tooltip(btn_load, "Загружает настройки из JSON-файла. Можно иметь несколько конфигов для разных серверов.")

    def toggle_seed_field(self):
        if self.wipe_random_seed_var.get():
            self.wipe_seed_entry.config(state="disabled")
        else:
            self.wipe_seed_entry.config(state="normal")

    def generate_random_seed(self):
        self.wipe_seed_var.set(str(random.randint(1000000, 2147483647)))

    def check_seed_on_rustmaps(self, seed_var, size_var, log_widget):
        api_key = self.api_key_var.get().strip()
        seed = seed_var.get().strip()
        size = size_var.get().strip()
        if not api_key:
            self.log(log_widget, "❌ API ключ не указан. Укажи его в настройках.", "red")
            return
        try:
            size = RustMapsAPI.validate_size(size)
            seed = RustMapsAPI.validate_seed(seed)
        except ValueError as e:
            self.log(log_widget, f"❌ Некорректные параметры: {e}", "red")
            return

        def worker():
            try:
                api = RustMapsAPI(api_key)
                self.root.after(0, lambda: self.log(log_widget, f"🌐 Проверка seed {seed} (размер {size}) на RustMaps...", "cyan"))
                result = api.get_map_by_seed(size, seed)
                data = result.get("data", {}) if isinstance(result, dict) else {}
                state = data.get("state", "Unknown")
                preview = data.get("previewBaseUrl", "")
                self.root.after(0, lambda st=state: self.log(log_widget, f"✅ Карта найдена. Статус: {st}", "green"))
                if preview:
                    self.root.after(0, lambda p=preview: self.log(log_widget, f"   Preview: {p}", "cyan"))
            except urllib.error.HTTPError as e:
                if e.code == 404:
                    self.root.after(0, lambda: self.log(log_widget, f"❌ Карты нет на RustMaps (seed={seed}, size={size})", "red"))
                else:
                    body = e.read().decode("utf-8", errors="ignore")
                    self.root.after(0, lambda c=e.code,b=body: self.log(log_widget, f"❌ API: HTTP {c} — {b[:200]}", "red"))
            except Exception as e:
                self.root.after(0, lambda err=e: self.log(log_widget, f"❌ Ошибка: {err}", "red"))
        threading.Thread(target=worker, daemon=True, name="rustmaps-check").start()

    def generate_via_rustmaps(self, seed_var, size_var, log_widget):
        api_key = self.api_key_var.get().strip()
        if not api_key:
            self.log(log_widget, "❌ API ключ не указан. Укажи его в настройках.", "red")
            return

        seed_text = seed_var.get().strip()
        size_text = size_var.get().strip()
        try:
            size = RustMapsAPI.validate_size(size_text)
            seed = RustMapsAPI.validate_seed(seed_text) if seed_text else None
        except ValueError as e:
            self.log(log_widget, f"❌ Некорректные параметры: {e}", "red")
            return

        self.log(log_widget, f"🌐 Запрос RustMaps API v4 (seed={seed or 'случайный'}, size={size})...", "cyan")

        def worker():
            try:
                api = RustMapsAPI(api_key)
                status_code, result, used_seed = api.generate(size=size, seed=seed)
                data = result.get("data", result) if isinstance(result, dict) else {}
                map_id = data.get("id") or data.get("mapId") or data.get("map_id") or ""
                state = data.get("state", "Unknown")
                self.root.after(0, lambda s=str(used_seed): seed_var.set(s))
                self.root.after(0, lambda sc=status_code, st=state:
                    self.log(log_widget, f"✅ RustMaps принял запрос (HTTP {sc}). Статус: {st}", "green"))
                if map_id:
                    self.root.after(0, lambda mid=map_id:
                        self.log(log_widget, f"🗺️ ID карты: {mid}", "cyan"))
                self.root.after(0, lambda:
                    self.log(log_widget, "ℹ️ API не предоставляет процент генерации — прогресс-бар здесь намеренно не используется.", "yellow"))
            except Exception as e:
                self.root.after(0, lambda err=e: self.log(log_widget, f"❌ RustMaps: {err}", "red"))

        threading.Thread(target=worker, daemon=True, name="rustmaps-generate").start()

    def preview_cfg_template(self):
        path = self.wipe_cfg_template_var.get().strip()
        if not path or not os.path.isfile(path):
            messagebox.showwarning("Шаблон", "Укажи корректный путь к файлу server.cfg")
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            top = tk.Toplevel(self.root)
            top.title("Предпросмотр server.cfg")
            top.geometry("600x400")
            top.configure(bg="#1e1e2e")
            txt = tk.Text(top, wrap="word", bg="#181825", fg="#cdd6f4", font=("Consolas", 10), relief="flat", bd=2)
            txt.pack(fill="both", expand=True, padx=10, pady=10)
            txt.insert("1.0", content)
            txt.config(state="disabled")
        except Exception as e:
            messagebox.showerror("Ошибка", str(e))

    def browse_file(self, var):
        path = filedialog.askopenfilename()
        if path:
            var.set(path)

    def load_text(self, widget):
        path = filedialog.askopenfilename(filetypes=[("Text", "*.txt"), ("All", "*.*")])
        if path:
            with open(path, "r", encoding="utf-8") as f:
                widget.delete("1.0", "end")
                widget.insert("1.0", f.read())

    def save_text(self, widget):
        path = filedialog.asksaveasfilename(defaultextension=".txt", filetypes=[("Text", "*.txt")])
        if path:
            with open(path, "w", encoding="utf-8") as f:
                f.write(widget.get("1.0", "end").strip())

    def reset_wipe_files(self):
        self.wipe_files_text.delete("1.0", "end")
        for f in self.DEFAULT_WIPE_FILES:
            self.wipe_files_text.insert("end", f + "\n")

    def reset_wipe_folders(self):
        self.wipe_folders_text.delete("1.0", "end")
        for f in self.DEFAULT_WIPE_FOLDERS:
            self.wipe_folders_text.insert("end", f + "\n")

    def start_wipe(self):
        with self.running_lock:
            if self._running:
                self.log(self.wipe_log, "⚠️ Другая операция уже выполняется.", "yellow")
                return
            self._running = True

        # Snapshot all Tk state in the UI thread.
        cfg = {
            "base": self.base_var.get().strip(),
            "ftp": self._snapshot_ftp_config(),
            "files": self._clean_lines(self.wipe_files_text.get("1.0", "end")),
            "folders": self._clean_lines(self.wipe_folders_text.get("1.0", "end")),
            "change_seed": bool(self.wipe_change_seed_var.get()),
            "random_seed": bool(self.wipe_random_seed_var.get()),
            "seed": self.wipe_seed_var.get().strip(),
            "worldsize": self.wipe_worldsize_var.get().strip(),
            "cfg_template": self.wipe_cfg_template_var.get().strip(),
            "restart": bool(self.wipe_restart_var.get()),
            "restart_sec": self.wipe_restart_sec_var.get().strip(),
            "restart_msg": self.wipe_restart_msg_var.get(),
        }
        try:
            RustMapsAPI.validate_size(cfg["worldsize"])
            if not cfg["random_seed"]:
                RustMapsAPI.validate_seed(cfg["seed"])
            sec = int(cfg["restart_sec"])
            if sec < 0 or sec > 86400:
                raise ValueError("Таймер рестарта должен быть от 0 до 86400 секунд.")
        except ValueError as e:
            with self.running_lock:
                self._running = False
            messagebox.showwarning("Параметры вайпа", str(e))
            return

        self.stop_event.clear()
        self.stop_requested = False
        self.wipe_start_btn.config(state="disabled")
        self.wipe_stop_btn.config(state="normal")
        self.wipe_progress["value"] = 0
        self.wipe_status_var.set("Подключение...")
        threading.Thread(target=self._wipe_worker, args=(cfg,), daemon=True, name="wipe-worker").start()

    def _wipe_worker(self, cfg):
        ftp = None
        try:
            ftp = self.ftp_connect(self.wipe_log, cfg["ftp"])
            if not ftp:
                return

            base = cfg["base"]
            operations = len(cfg["files"]) + len(cfg["folders"]) + (1 if cfg["change_seed"] else 0)
            done = 0

            for item in cfg["files"]:
                if self.stop_event.is_set():
                    self.log(self.wipe_log, "⏹ Остановлено пользователем.", "yellow")
                    return
                remote = self._remote_path(base, item)
                try:
                    ftp.delete(remote)
                    self.log(self.wipe_log, f"🗑️ Удалено: {remote}", "green")
                except ftplib.error_perm as e:
                    # 550 often means file does not exist; don't turn a normal wipe into a failure.
                    self.log(self.wipe_log, f"ℹ️ Не удалено/уже отсутствует: {remote} ({e})", "yellow")
                done += 1
                self._set_progress(self.wipe_progress, self.wipe_status_var, done/max(operations,1)*100, f"{int(done/max(operations,1)*100)}%")

            for item in cfg["folders"]:
                if self.stop_event.is_set():
                    self.log(self.wipe_log, "⏹ Остановлено пользователем.", "yellow")
                    return
                remote = self._remote_path(base, item)
                try:
                    self._rmdirs(ftp, remote)
                    self.log(self.wipe_log, f"🗑️ Очищена папка: {remote}", "green")
                except Exception as e:
                    self.log(self.wipe_log, f"⚠️ {remote}: {e}", "yellow")
                done += 1
                self._set_progress(self.wipe_progress, self.wipe_status_var, done/max(operations,1)*100, f"{int(done/max(operations,1)*100)}%")

            if cfg["change_seed"] and not self.stop_event.is_set():
                seed = cfg["seed"]
                if cfg["random_seed"]:
                    seed = str(random.randint(1, RustMapsAPI.MAX_SEED))
                    self.root.after(0, lambda s=seed: self.wipe_seed_var.set(s))

                cfg_path = cfg["cfg_template"]
                if cfg_path and os.path.isfile(cfg_path):
                    temp_cfg = None
                    try:
                        with open(cfg_path, "r", encoding="utf-8-sig", newline="") as f:
                            content = f.read()
                        worldsize = cfg["worldsize"]
                        seed_re = re.compile(r"(?im)^\s*server\.seed\s+\S+\s*$")
                        ws_re = re.compile(r"(?im)^\s*server\.worldsize\s+\S+\s*$")
                        if seed_re.search(content):
                            content = seed_re.sub(f"server.seed {seed}", content, count=1)
                        else:
                            content = content.rstrip() + f"\nserver.seed {seed}\n"
                        if ws_re.search(content):
                            content = ws_re.sub(f"server.worldsize {worldsize}", content, count=1)
                        else:
                            content = content.rstrip() + f"\nserver.worldsize {worldsize}\n"

                        fd, temp_cfg = tempfile.mkstemp(prefix="ziops_", suffix=".cfg", dir=self.script_dir)
                        with os.fdopen(fd, "w", encoding="utf-8", newline="") as f:
                            f.write(content)
                        remote_cfg = self._remote_path(base, "server.cfg")
                        with open(temp_cfg, "rb") as f:
                            ftp.storbinary(f"STOR {remote_cfg}", f)
                        self.log(self.wipe_log, f"✅ server.cfg обновлён (seed={seed}, worldsize={worldsize})", "green")
                    finally:
                        if temp_cfg:
                            try: os.remove(temp_cfg)
                            except OSError: pass
                else:
                    # Clipboard is a UI operation; perform it on main thread.
                    self.root.after(0, lambda s=seed: (self.root.clipboard_clear(), self.root.clipboard_append(s)))
                    self.log(self.wipe_log, f"📋 Seed скопирован в буфер: {seed}", "cyan")

                done += 1
                self._set_progress(self.wipe_progress, self.wipe_status_var, done/max(operations,1)*100, f"{int(done/max(operations,1)*100)}%")

            if cfg["restart"] and not self.stop_event.is_set():
                try:
                    with self.rcon_lock:
                        client = self.rcon_client
                    if not client or not client.connected:
                        raise RuntimeError("RCON не подключён.")
                    msg = cfg["restart_msg"].replace('"', '\"')
                    client.send(f'say "{msg}"', wait=False)
                    client.send(f"restart {int(cfg['restart_sec'])}", wait=False)
                    self.log(self.wipe_log, f"🔄 Рестарт отправлен ({cfg['restart_sec']} сек)", "green")
                except Exception as e:
                    self.log(self.wipe_log, f"❌ Рестарт не отправлен: {e}", "red")

            self.log(self.wipe_log, "\n✅ Вайп завершён.", "green")
        except Exception as e:
            self.log(self.wipe_log, f"❌ Ошибка вайпа: {e}", "red")
        finally:
            if ftp:
                try: ftp.quit()
                except Exception:
                    try: ftp.close()
                    except Exception: pass
            self.root.after(0, self._wipe_done)

    def _rmdirs(self, ftp, path):
        """Удаляет содержимое папки, сохраняя саму папку."""
        original = None
        try:
            original = ftp.pwd()
        except Exception:
            pass
        try:
            ftp.cwd(path)
            entries = []
            ftp.retrlines("NLST", entries.append)
            for raw in entries:
                name = self._remote_basename(raw)
                if not name or name in (".", ".."):
                    continue
                try:
                    ftp.delete(name)
                    continue
                except Exception:
                    pass
                try:
                    self._rmdirs(ftp, name)
                except Exception:
                    pass
            ftp.cwd("..")
        finally:
            if original:
                try:
                    ftp.cwd(original)
                except Exception:
                    pass

    def request_stop(self):
        with self.running_lock:
            running = self._running
        if running:
            self.stop_event.set()
            self.stop_requested = True
            self.wipe_status_var.set("Остановка...")
            self.log(self.wipe_log, "⏹ Запрошена остановка. Текущая FTP-операция будет завершена.", "yellow")

    def _wipe_done(self):
        with self.running_lock:
            self._running = False
        self.stop_requested = False
        self.wipe_start_btn.config(state="normal")
        self.wipe_stop_btn.config(state="disabled")
        self.wipe_status_var.set("Готов")
        self.wipe_progress["value"] = 100

    def run_judgment(self, on):
        with self.running_lock:
            if self._running:
                self.log(self.judg_log, "⚠️ Другая операция уже выполняется.", "yellow")
                return
            self._running = True

        cfg = {
            "base": self.base_var.get().strip(),
            "ftp": self._snapshot_ftp_config(),
            "on": bool(on),
            "delete": self._clean_lines((self.judg_on_del_text if on else self.judg_off_del_text).get("1.0", "end")),
            "uploads": [],
        }
        if on:
            cfg["uploads"].append((self.judg_on_upload_var.get().strip(), self.judg_on_remote_var.get().strip()))
        else:
            for uv, rv in zip(self.judg_off_upload_vars, self.judg_off_remote_vars):
                cfg["uploads"].append((uv.get().strip(), rv.get().strip()))

        self.judg_progress["value"] = 0
        self.judg_status_var.set("Подключение...")
        threading.Thread(target=self._judgment_worker, args=(cfg,), daemon=True, name="judgment-worker").start()

    def _judgment_worker(self, cfg):
        ftp = None
        try:
            ftp = self.ftp_connect(self.judg_log, cfg["ftp"])
            if not ftp:
                return
            base = cfg["base"]
            ops = len(cfg["delete"]) + len([x for x in cfg["uploads"] if x[0] and x[1]])
            done = 0

            for item in cfg["delete"]:
                remote = self._remote_path(base, item)
                try:
                    ftp.delete(remote)
                    self.log(self.judg_log, f"🗑️ Удалено: {remote}", "green")
                except ftplib.error_perm as e:
                    self.log(self.judg_log, f"ℹ️ Уже отсутствует/не удалено: {remote} ({e})", "yellow")
                done += 1
                self._set_progress(self.judg_progress, self.judg_status_var, done/max(ops,1)*100, f"{int(done/max(ops,1)*100)}%")

            for local, remote in cfg["uploads"]:
                if not local or not remote:
                    self.log(self.judg_log, "⚠️ Пропущена загрузка: не указан локальный или удалённый путь.", "yellow")
                    continue
                if not os.path.isfile(local):
                    self.log(self.judg_log, f"❌ Локальный файл не найден: {local}", "red")
                    continue
                if remote.endswith("/"):
                    remote = remote + os.path.basename(local)
                remote_path = self._remote_path(base, remote)
                with open(local, "rb") as f:
                    ftp.storbinary(f"STOR {remote_path}", f)
                self.log(self.judg_log, f"⬆️ Загружено: {remote_path}", "green")
                done += 1
                self._set_progress(self.judg_progress, self.judg_status_var, done/max(ops,1)*100, f"{int(done/max(ops,1)*100)}%")

            self.log(self.judg_log, "\n✅ Операция завершена.", "green")
        except Exception as e:
            self.log(self.judg_log, f"❌ Ошибка: {e}", "red")
        finally:
            if ftp:
                try: ftp.quit()
                except Exception:
                    try: ftp.close()
                    except Exception: pass
            self.root.after(0, self._judgment_done)

    def _judgment_done(self):
        with self.running_lock:
            self._running = False
        self.judg_status_var.set("Готов")
        self.judg_progress["value"] = 100

    def rcon_connect(self):
        if not WEBSOCKET_OK:
            self.log(self.rcon_log, "❌ Установи websocket-client: pip install websocket-client", "red")
            return
        if self._rcon_connecting:
            return
        if self.rcon_client and self.rcon_client.connected:
            self.log(self.rcon_log, "ℹ️ Уже подключено", "yellow")
            return
        host = self.rcon_host_var.get().strip()
        port = self.rcon_port_var.get().strip()
        password = self.rcon_pass_var.get()
        path = self.rcon_path_var.get().strip()
        if path in ("Напр: /rcon или оставь пустым", ""):
            path = ""
        if not all([host, port, password]):
            self.log(self.rcon_log, "❌ Заполни все поля RCON в настройках", "red")
            return
        try:
            port = int(port)
            if not 1 <= port <= 65535:
                raise ValueError
        except ValueError:
            self.log(self.rcon_log, "❌ RCON-порт должен быть от 1 до 65535.", "red")
            return
        use_ssl = bool(self.rcon_ssl_var.get())
        self._rcon_connecting = True
        self.rcon_conn_status.set("Проверка порта...")
        self.log(self.rcon_log, f"⏳ Проверка доступности {host}:{port}...", "cyan")

        def connect_thread():
            # Step 1: Check if port is reachable
            import socket
            try:
                sock = socket.create_connection((host, int(port)), timeout=5)
                sock.close()
            except socket.timeout:
                self.root.after(0, lambda: self.rcon_conn_status.set("❌ Порт недоступен"))
                self.root.after(0, lambda: self.log(self.rcon_log,
                    f"❌ Порт {port} не отвечает. Возможные причины:\n"
                    f"   • Указан игровой порт вместо RCON-порта\n"
                    f"   • RCON-порт закрыт файрволом хостинга\n"
                    f"   • Сервер выключен\n"
                    f"   Проверь порт RCON в панели хостинга (обычно отличается от игрового)", "red"))
                return
            except ConnectionRefusedError:
                self.root.after(0, lambda: self.rcon_conn_status.set("❌ Соединение отклонено"))
                self.root.after(0, lambda: self.log(self.rcon_log,
                    f"❌ Порт {port} отклонил соединение. Проверь, что сервер запущен и порт открыт.", "red"))
                return
            except Exception as e:
                self.root.after(0, lambda: self.rcon_conn_status.set("❌ Ошибка сети"))
                self.root.after(0, lambda e=e: self.log(self.rcon_log, f"❌ Ошибка сети: {e}", "red"))
                return

            # Step 2: Try WebSocket connect
            self.root.after(0, lambda: self.rcon_conn_status.set("WebSocket..."))
            scheme = "wss" if use_ssl else "ws"
            full_path = f"{path}/***" if path else "/***"
            self.root.after(0, lambda: self.log(self.rcon_log,
                f"⏳ WebSocket: {scheme}://{host}:{port}{full_path}", "cyan"))
            try:
                client = RustRCON(host, int(port), password, timeout=10, path=path, ssl=use_ssl)
                client.connect()
                with self.rcon_lock:
                    self.rcon_client = client
                self.root.after(0, lambda: self.rcon_conn_status.set("✅ Подключено"))
                self.root.after(0, lambda: self.log(self.rcon_log, "✅ Подключено к RCON", "green"))
            except websocket.WebSocketTimeoutException:
                self.root.after(0, lambda: self.rcon_conn_status.set("❌ Таймаут"))
                self.root.after(0, lambda: self.log(self.rcon_log,
                    "❌ WebSocket таймаут. Порт открыт, но не отвечает по WebSocket.\n"
                    "   Возможно, на этом порту не RCON, а другое приложение.", "red"))
            except websocket.WebSocketBadStatusException as e:
                self.root.after(0, lambda: self.rcon_conn_status.set("❌ HTTP ошибка"))
                self.root.after(0, lambda e=e: self.log(self.rcon_log,
                    f"❌ Сервер ответил HTTP ошибкой: {str(e).replace(password, '***')}\n"
                    "   Попробуй указать путь RCON (например /rcon) в настройках.", "red"))
            except Exception as e:
                self.root.after(0, lambda: self.rcon_conn_status.set("❌ Ошибка"))
                self.root.after(0, lambda e=e: self.log(self.rcon_log, f"❌ Ошибка подключения: {str(e).replace(password, '***')}", "red"))

        def guarded_connect():
            try:
                connect_thread()
            finally:
                self._rcon_connecting = False
        threading.Thread(target=guarded_connect, daemon=True).start()

    def rcon_disconnect(self):
        with self.rcon_lock:
            if self.rcon_client:
                self.rcon_client.disconnect()
                self.rcon_client = None
        self.rcon_conn_status.set("Не подключено")
        self.log(self.rcon_log, "🔌 Отключено", "yellow")

    def rcon_test(self):
        def worker():
            with self.rcon_lock:
                client = self.rcon_client
            if not client or not client.connected:
                self.root.after(0, lambda: self.log(self.rcon_log, "❌ Нет подключения", "red"))
                return
            self.root.after(0, lambda: self.log(self.rcon_log, "> status (ожидание ответа 5 сек)...", "cyan"))
            try:
                result = client.send("status", wait=True, timeout=5)
                self.root.after(0, lambda r=result: self.log(self.rcon_log, f"Ответ: {r[:500]}", "green"))
            except Exception as e:
                self.root.after(0, lambda e=e: self.log(self.rcon_log, f"❌ Ошибка: {e}", "red"))
        threading.Thread(target=worker, daemon=True).start()

    def rcon_send_command(self, cmd, log_widget=None):
        if log_widget is None:
            log_widget = self.rcon_log
        def worker():
            with self.rcon_lock:
                client = self.rcon_client
            if not client or not client.connected:
                self.root.after(0, lambda: self.log(log_widget, "❌ Нет подключения. Нажми \"Подключиться\" сначала.", "red"))
                return
            self.root.after(0, lambda: self.log(log_widget, f"> {cmd}", "cyan"))
            try:
                result = client.send(cmd, wait=False)
                self.root.after(0, lambda r=result: self.log(log_widget, r, "green"))
            except Exception as e:
                self.root.after(0, lambda e=e: self.log(log_widget, f"❌ Ошибка: {e}", "red"))
        threading.Thread(target=worker, daemon=True).start()

    def rcon_full_wipe(self):
        with self.rcon_lock:
            client = self.rcon_client
        if not client or not client.connected:
            self.log(self.rcon_log, "❌ Нет подключения.", "red")
            return
        seed = self.rcon_seed_var.get().strip()
        size = self.rcon_worldsize_var.get().strip()
        sec = self.rcon_restart_sec_var.get().strip()
        try:
            size = RustMapsAPI.validate_size(size)
            if self.rcon_random_seed_var.get():
                seed = str(random.randint(1, RustMapsAPI.MAX_SEED))
                self.rcon_seed_var.set(seed)
            else:
                seed = RustMapsAPI.validate_seed(seed)
            sec_i = int(sec)
            if not 0 <= sec_i <= 86400:
                raise ValueError("Таймер должен быть от 0 до 86400 секунд.")
        except ValueError as e:
            self.log(self.rcon_log, f"❌ {e}", "red")
            return

        self.log(self.rcon_log, f"🗺️ Смена параметров: seed={seed}, size={size}, restart={sec_i}s", "cyan")

        def worker():
            commands = [
                f"server.seed {seed}",
                f"server.worldsize {size}",
                "server.save",
                f"restart {sec_i} \"Рестарт сервера через {sec_i} секунд...\""
            ]
            try:
                with self.rcon_lock:
                    client = self.rcon_client
                if not client or not client.connected:
                    raise RuntimeError("Соединение потеряно.")
                for cmd in commands:
                    client.send(cmd, wait=False)
                    time.sleep(0.15)
                self.log(self.rcon_log, "✅ Команды отправлены.", "green")
            except Exception as e:
                self.log(self.rcon_log, f"❌ Ошибка: {e}", "red")
        threading.Thread(target=worker, daemon=True, name="rcon-wipe-worker").start()

    def toggle_rcon_seed(self):
        if self.rcon_random_seed_var.get():
            self.rcon_seed_entry.config(state="disabled")
        else:
            self.rcon_seed_entry.config(state="normal")

    def generate_rcon_random_seed(self):
        self.rcon_seed_var.set(str(random.randint(1000000, 2147483647)))

    def open_rustmaps(self):
        import webbrowser
        webbrowser.open("https://rustmaps.com")

    def _snapshot_ftp_config(self):
        """Снимок FTP-настроек, безопасный для использования в worker-потоке."""
        return {
            "host": self.host_var.get().strip(),
            "port": self.port_var.get().strip() or "21",
            "user": self.user_var.get().strip(),
            "password": self.pass_var.get(),
            "use_ftps": bool(self.ftps_var.get()),
        }

    def ftp_connect(self, log_widget, config=None):
        if config is None:
            config = self._snapshot_ftp_config()
        host = config.get("host", "").strip()
        port = config.get("port", "21") or "21"
        user = config.get("user", "").strip()
        password = config.get("password", "")
        use_ftps = bool(config.get("use_ftps", False))
        if not all([host, user, password]):
            self.log(log_widget, "❌ Заполни FTP настройки во вкладке \"Настройки\"", "red")
            return None
        ftp = None
        connected = False
        try:
            port = int(port)
            if not 1 <= port <= 65535:
                raise ValueError("FTP-порт должен быть от 1 до 65535.")
            if use_ftps:
                ftp = ftplib.FTP_TLS()
                self.log(log_widget, f"⏳ Подключение по FTPS к {host}:{port}...", "cyan")
            else:
                ftp = ftplib.FTP()
                self.log(log_widget, f"⏳ Подключение по FTP к {host}:{port} (пассивный режим)...", "cyan")
            ftp.connect(host, int(port), timeout=15)
            # Passive mode is required by the hosting setup. Keep it explicitly
            # enabled for every fresh connection/reconnect.
            ftp.set_pasv(True)
            ftp.login(user, password)
            if use_ftps:
                ftp.prot_p()
                self.log(log_widget, f"✅ FTPS подключен: {host}:{port}", "green")
            else:
                self.log(log_widget, f"✅ FTP подключен: {host}:{port} (пассивный)", "green")
            connected = True
            return ftp
        except ftplib.error_perm as e:
            code = str(e)[:3]
            if code == "530":
                self.log(log_widget, "❌ Ошибка 530: Неверный логин или пароль. Проверь учётные данные.", "red")
            elif code == "421":
                self.log(log_widget, "❌ Ошибка 421: Слишком много подключений. Подожди минуту.", "red")
            else:
                self.log(log_widget, f"❌ FTP ошибка (код {code}): {e}", "red")
            return None
        except Exception as e:
            self.log(log_widget, f"❌ FTP ошибка: {e}", "red")
            return None
        finally:
            if ftp is not None and not connected:
                try:
                    ftp.close()
                except Exception:
                    pass

    def _ftp_download_with_retry(self, ftp, folder, filename, local_path, log_widget, ftp_cfg, retries=3):
        """Скачивает файл и восстанавливает FTP data-channel после 425/426.

        Некоторые хостинги периодически отклоняют passive data connection с
        сообщением 'control and data connection do not match'. Это не связано
        с содержимым .cs-файла, поэтому переподключаемся и повторяем передачу.
        Возвращает True при успехе.
        """
        current = ftp
        self._check_worker_ftp = current
        for attempt in range(1, retries + 1):
            if self.stop_event.is_set():
                return False
            if current is None:
                current = self.ftp_connect(log_widget, ftp_cfg)
                self._check_worker_ftp = current
                if current is None:
                    continue
                try:
                    current.cwd(folder)
                except Exception:
                    current.close()
                    current = None
                    self._check_worker_ftp = None
                    continue
            try:
                with open(local_path, "wb") as f:
                    current.retrbinary(f"RETR {filename}", f.write, blocksize=64 * 1024)
                return True
            except (ftplib.error_temp, ftplib.error_reply, EOFError, OSError) as e:
                code_match = re.search(r"\b(425|426)\b", str(e))
                if not code_match and not isinstance(e, (EOFError, OSError)):
                    raise
                self.log(log_widget,
                         f"  ⚠️ Ошибка FTP при скачивании {filename}: {e} "
                         f"(попытка {attempt}/{retries}).", "yellow")
                try:
                    current.close()
                except Exception:
                    pass
                current = None
                self._check_worker_ftp = None
                if attempt < retries and self.stop_event.wait(0.7 * attempt):
                    return False
        return False

    def log(self, widget, text, color="white"):
        # tkinter не потокобезопасен: вызовы из рабочих потоков перенаправляем в главный
        if threading.current_thread() is not threading.main_thread():
            try:
                self.root.after(0, lambda w=widget, t=text, c=color: self.log(w, t, c))
            except Exception:
                pass
            return
        widget.config(state="normal")
        widget.insert("end", text + "\n", color)
        widget.see("end")
        widget.config(state="disabled")

    def _config_log_tags(self, widget):
        widget.tag_configure("red", foreground="#f38ba8")
        widget.tag_configure("green", foreground="#a6e3a1")
        widget.tag_configure("yellow", foreground="#f9e2af")
        widget.tag_configure("cyan", foreground="#89dceb")
        widget.tag_configure("white", foreground="#cdd6f4")

    def load_config(self, path, silent=False):
        if not path or not os.path.isfile(path):
            if not silent:
                messagebox.showwarning("Конфиг", "Файл не найден")
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                raise ValueError("Конфиг должен содержать JSON-объект.")
            self.host_var.set(data.get("ftp_host", ""))
            self.port_var.set(data.get("ftp_port", "21"))
            self.user_var.set(data.get("ftp_user", ""))
            self.pass_var.set(data.get("ftp_pass", ""))
            self.base_var.set(data.get("ftp_base", "/"))
            self.rcon_host_var.set(data.get("rcon_host", ""))
            self.rcon_port_var.set(data.get("rcon_port", "28016"))
            self.rcon_pass_var.set(data.get("rcon_pass", ""))
            self.rcon_path_var.set(data.get("rcon_path", ""))
            self.rcon_ssl_var.set(data.get("rcon_ssl", False))
            self.api_key_var.set(data.get("api_key", ""))
            self.ftps_var.set(data.get("ftps", False))
            # Judgment
            if "judg_on_del" in data:
                self.judg_on_del_text.delete("1.0", "end")
                self.judg_on_del_text.insert("1.0", data.get("judg_on_del", ""))
            self.judg_on_upload_var.set(data.get("judg_on_upload", ""))
            self.judg_on_remote_var.set(data.get("judg_on_remote", self.DEFAULT_JUDGMENT_ON_REMOTE))
            if "judg_off_del" in data:
                self.judg_off_del_text.delete("1.0", "end")
                self.judg_off_del_text.insert("1.0", data.get("judg_off_del", ""))
            self.judg_off_upload_vars[0].set(data.get("judg_off_upload_0", ""))
            self.judg_off_upload_vars[1].set(data.get("judg_off_upload_1", ""))
            self.judg_off_remote_vars[0].set(data.get("judg_off_remote_0", self.DEFAULT_JUDGMENT_OFF_REMOTES[0]))
            self.judg_off_remote_vars[1].set(data.get("judg_off_remote_1", self.DEFAULT_JUDGMENT_OFF_REMOTES[1]))
            # Wipe
            if "wipe_files" in data:
                self.wipe_files_text.delete("1.0", "end")
                self.wipe_files_text.insert("1.0", data.get("wipe_files", ""))
            if "wipe_folders" in data:
                self.wipe_folders_text.delete("1.0", "end")
                self.wipe_folders_text.insert("1.0", data.get("wipe_folders", ""))
            self.wipe_cfg_template_var.set(data.get("wipe_cfg_template", ""))
            self.wipe_worldsize_var.set(data.get("wipe_worldsize", "4250"))
            self.wipe_seed_var.set(data.get("wipe_seed", str(random.randint(1000000, 2147483647))))
            self.wipe_restart_sec_var.set(data.get("wipe_restart_sec", "60"))
            self.wipe_restart_msg_var.set(data.get("wipe_restart_msg", "Вайп сервера! Рестарт через 60 секунд..."))
            self.wipe_change_seed_var.set(data.get("wipe_change_seed", False))
            self.wipe_random_seed_var.set(data.get("wipe_random_seed", True))
            self.wipe_restart_var.set(data.get("wipe_restart", False))

            # Плагины, которые пользователь запретил обновлять через «Обновить все».
            saved_custom = data.get("custom_plugins", [])
            self.custom_plugins = {self._plugin_key(x) for x in saved_custom if self._plugin_key(x)} if isinstance(saved_custom, list) else set()

            # Plugin update list
            if isinstance(data.get("plugins"), list):
                self.clear_plugins()
                for item in data["plugins"]:
                    if isinstance(item, dict):
                        self.add_plugin_row(
                            item.get("name", ""), item.get("url", ""),
                            item.get("page", ""), item.get("remote", "oxide/plugins/")
                        )
            self.plugins_server_path_var.set(data.get("plugins_server_path", "oxide/plugins/"))
            for item, keys in self._installed_item_keys.items():
                self.installed_tree.set(item, "Кастомный", "☑" if keys & self.custom_plugins else "☐")
            self._apply_installed_plugins_sort()
            self.toggle_seed_field()
            self.toggle_rcon_seed()
            if not silent:
                messagebox.showinfo("Конфиг", "Настройки загружены")
        except Exception as e:
            if not silent:
                messagebox.showerror("Ошибка", str(e))

    def save_config(self, silent=False):
        data = {
            "ftp_host": self.host_var.get(),
            "ftp_port": self.port_var.get(),
            "ftp_user": self.user_var.get(),
            "ftp_pass": self.pass_var.get(),
            "ftp_base": self.base_var.get(),
            "rcon_host": self.rcon_host_var.get(),
            "rcon_port": self.rcon_port_var.get(),
            "rcon_pass": self.rcon_pass_var.get(),
            "rcon_path": self.rcon_path_var.get(),
            "rcon_ssl": self.rcon_ssl_var.get(),
            "api_key": self.api_key_var.get(),
            "ftps": self.ftps_var.get(),
            "custom_plugins": sorted(self.custom_plugins),
            "plugins_server_path": self.plugins_server_path_var.get(),
            "judg_on_del": self.judg_on_del_text.get("1.0", "end").strip(),
            "judg_on_upload": self.judg_on_upload_var.get(),
            "judg_on_remote": self.judg_on_remote_var.get(),
            "judg_off_del": self.judg_off_del_text.get("1.0", "end").strip(),
            "judg_off_upload_0": self.judg_off_upload_vars[0].get(),
            "judg_off_upload_1": self.judg_off_upload_vars[1].get(),
            "judg_off_remote_0": self.judg_off_remote_vars[0].get(),
            "judg_off_remote_1": self.judg_off_remote_vars[1].get(),
            "wipe_files": self.wipe_files_text.get("1.0", "end").strip(),
            "wipe_folders": self.wipe_folders_text.get("1.0", "end").strip(),
            "wipe_cfg_template": self.wipe_cfg_template_var.get(),
            "wipe_worldsize": self.wipe_worldsize_var.get(),
            "wipe_seed": self.wipe_seed_var.get(),
            "wipe_restart_sec": self.wipe_restart_sec_var.get(),
            "wipe_restart_msg": self.wipe_restart_msg_var.get(),
            "wipe_change_seed": self.wipe_change_seed_var.get(),
            "wipe_random_seed": self.wipe_random_seed_var.get(),
            "wipe_restart": self.wipe_restart_var.get(),
            "plugins": [
                {
                    "name": r["name"].get(),
                    "url": r["url"].get(),
                    "page": r["page"].get(),
                    "remote": r["remote"].get(),
                }
                for r in self.plugin_rows
            ],
        }
        path = self.auto_config_path
        try:
            tmp = path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, path)
            if not silent:
                messagebox.showinfo("Конфиг", f"Сохранено: {path}")
        except Exception as e:
            if not silent:
                messagebox.showerror("Ошибка", str(e))

    def on_close(self):
        self.stop_event.set()
        self.save_config(silent=True)
        if self.rcon_client:
            self.rcon_client.disconnect()
        self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    app = ZI_Ops(root)
    root.mainloop()
