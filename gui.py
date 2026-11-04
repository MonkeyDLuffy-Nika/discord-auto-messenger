"""
Графический интерфейс Discord Auto-Messenger на CustomTkinter.
Современный темный дизайн, авто-захват токенов Discord/браузеров,
выбор серверов и текстовых каналов (с ботами Nekotina, Mudae и др.),
выбор друзей из контактов, выполнение нативных Slash-команд,
мега-пресет фембоя на 250 сообщений, прикрепление случайных GIF из избранного Discord (1552 шт.),
автоматическая установка кастомного статуса Discord с указанием автора (Aharen7san) и пресета,
полное сворачивание в системный трей (System Tray) Windows и сборка в автономный .EXE.
"""

import os
import random
import sys
import threading
import time
import tkinter as tk
from datetime import datetime
from typing import Dict, List, Optional
from PIL import Image, ImageDraw

import customtkinter as ctk
import pystray

from config_manager import load_config, save_config
from discord_sender import DiscordSender, format_message
from presets import DEFAULT_FAVORITE_GIFS, FEMBOY_PRESET, NEKOTINA_PRESET
from token_extractor import scan_and_extract_tokens

# Устанавливаем общую тему
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

# Цветовая палитра в стиле Discord
COLOR_BG = "#1E1F22"
COLOR_SIDEBAR = "#2B2D31"
COLOR_CARD = "#313338"
COLOR_CARD_HOVER = "#383A40"
COLOR_ACCENT = "#5865F2"
COLOR_ACCENT_HOVER = "#4752C4"
COLOR_SUCCESS = "#23A55A"
COLOR_SUCCESS_HOVER = "#1E8B4C"
COLOR_DANGER = "#F23F43"
COLOR_WARNING = "#F0B232"
COLOR_PURPLE = "#9B59B6"
COLOR_PINK = "#E91E63"
COLOR_PINK_HOVER = "#C2185B"
COLOR_TEXT_MUTED = "#949BA4"
COLOR_TEXT_MAIN = "#F2F3F5"


class DiscordAutoMessengerApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Discord Auto-Messenger • by Aharen7san")
        self.geometry("1120x920")
        self.minsize(960, 720)

        # Установка иконки окна, если существует
        icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "icon.ico")
        if os.path.exists(icon_path):
            try:
                self.iconbitmap(icon_path)
            except Exception:
                pass

        # Загрузка конфигурации
        self.config_data = load_config()

        # Состояние работы воркера
        self.is_running = False
        self.is_paused = False
        self.worker_thread: Optional[threading.Thread] = None
        self.stop_event = threading.Event()
        self.pause_event = threading.Event()
        self.pause_event.set()

        # Статистика
        self.sent_count = 0
        self.error_count = 0
        self.start_time: Optional[datetime] = None
        self.current_seq_index = 0

        # Кэши и GIF
        self.cached_contacts: List[dict] = []
        self.cached_guilds: List[dict] = []
        self.favorite_gifs: List[str] = self.config_data.get("favorite_gifs") or list(DEFAULT_FAVORITE_GIFS)

        # Трей
        self.tray_icon: Optional[pystray.Icon] = None
        self._init_tray()

        # Построение интерфейса
        self._build_ui()

        # Восстановление данных из конфигурации
        self._populate_fields_from_config()

        # Запуск таймера обновления статистики
        self.after(500, self._update_timer_loop)

        # Обработка закрытия окна
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _get_tray_image(self) -> Image.Image:
        icon_png = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "icon.png")
        if os.path.exists(icon_png):
            try:
                return Image.open(icon_png)
            except Exception:
                pass
        # Fallback generated icon
        img = Image.new("RGBA", (64, 64), color=(88, 101, 242, 255))
        draw = ImageDraw.Draw(img)
        draw.ellipse([8, 8, 56, 56], fill="#313338")
        draw.polygon([(35, 12), (18, 36), (32, 36), (28, 52), (48, 28), (34, 28)], fill="#57F287")
        return img

    def _init_tray(self):
        """Инициализация системного трея Windows."""
        try:
            image = self._get_tray_image()
            menu = pystray.Menu(
                pystray.MenuItem("📌 Показать окно", lambda: self.after(0, self.show_window), default=True),
                pystray.MenuItem("▶️ Запустить", lambda: self.after(0, self._on_start_click)),
                pystray.MenuItem("⏸️ Пауза", lambda: self.after(0, self._on_pause_click)),
                pystray.MenuItem("⏹️ Остановить", lambda: self.after(0, self._on_stop_click)),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("❌ Выход", lambda: self.after(0, self._force_quit))
            )
            self.tray_icon = pystray.Icon("AutoMsg", image, "Discord Auto-Messenger • by Aharen7san", menu)
            threading.Thread(target=self.tray_icon.run, daemon=True).start()
        except Exception as e:
            print(f"[Tray] Ошибка инициализации трея: {e}")

    def show_window(self):
        """Показать окно из трея."""
        self.deiconify()
        self.lift()
        self.focus_force()

    def minimize_to_tray(self):
        """Свернуть окно в системный трей."""
        self.withdraw()
        self.log_message("📥 Приложение свернуто в системный трей Windows. Работа продолжается в фоне.", "info")

    def _build_ui(self):
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)

        # Сайдбар
        self.sidebar_frame = ctk.CTkFrame(self, width=220, corner_radius=0, fg_color=COLOR_SIDEBAR)
        self.sidebar_frame.grid(row=0, column=0, sticky="nsew")
        self.sidebar_frame.grid_rowconfigure(6, weight=1)

        self.logo_label = ctk.CTkLabel(
            self.sidebar_frame,
            text="⚡ AutoMsg",
            font=ctk.CTkFont(size=22, weight="bold"),
            text_color=COLOR_ACCENT
        )
        self.logo_label.grid(row=0, column=0, padx=20, pady=(20, 2), sticky="w")

        self.author_label = ctk.CTkLabel(
            self.sidebar_frame,
            text="by Aharen7san",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=COLOR_PINK
        )
        self.author_label.grid(row=1, column=0, padx=20, pady=(0, 15), sticky="w")

        # Кнопки навигации
        self.nav_btn_dash = ctk.CTkButton(
            self.sidebar_frame,
            text="📌 Главная",
            font=ctk.CTkFont(size=14, weight="bold"),
            height=40,
            fg_color=COLOR_ACCENT,
            hover_color=COLOR_ACCENT_HOVER,
            anchor="w",
            command=lambda: self._select_tab("dash")
        )
        self.nav_btn_dash.grid(row=2, column=0, padx=15, pady=5, sticky="ew")

        self.nav_btn_settings = ctk.CTkButton(
            self.sidebar_frame,
            text="⚙️ Настройки & Статус",
            font=ctk.CTkFont(size=14),
            height=40,
            fg_color="transparent",
            hover_color=COLOR_CARD,
            anchor="w",
            command=lambda: self._select_tab("settings")
        )
        self.nav_btn_settings.grid(row=3, column=0, padx=15, pady=5, sticky="ew")

        self.nav_btn_logs = ctk.CTkButton(
            self.sidebar_frame,
            text="📜 Логи и Консоль",
            font=ctk.CTkFont(size=14),
            height=40,
            fg_color="transparent",
            hover_color=COLOR_CARD,
            anchor="w",
            command=lambda: self._select_tab("logs")
        )
        self.nav_btn_logs.grid(row=4, column=0, padx=15, pady=5, sticky="ew")

        self.nav_btn_help = ctk.CTkButton(
            self.sidebar_frame,
            text="❓ Инструкция",
            font=ctk.CTkFont(size=14),
            height=40,
            fg_color="transparent",
            hover_color=COLOR_CARD,
            anchor="w",
            command=lambda: self._select_tab("help")
        )
        self.nav_btn_help.grid(row=5, column=0, padx=15, pady=5, sticky="ew")

        # Кнопка быстрого скрытия в трей
        self.btn_tray_quick = ctk.CTkButton(
            self.sidebar_frame,
            text="📥 СВЕРНУТЬ В ТРЕЙ",
            font=ctk.CTkFont(size=12, weight="bold"),
            height=34,
            fg_color="#2E86C1",
            hover_color="#1B4F72",
            command=self.minimize_to_tray
        )
        self.btn_tray_quick.grid(row=6, column=0, padx=15, pady=(15, 5), sticky="s")

        self.sidebar_status_frame = ctk.CTkFrame(self.sidebar_frame, fg_color=COLOR_CARD, corner_radius=10)
        self.sidebar_status_frame.grid(row=7, column=0, padx=15, pady=(5, 15), sticky="ew")

        self.status_badge = ctk.CTkLabel(
            self.sidebar_status_frame,
            text="● Остановлен",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=COLOR_DANGER
        )
        self.status_badge.pack(pady=8)

        # Контейнер
        self.main_container = ctk.CTkFrame(self, fg_color=COLOR_BG, corner_radius=0)
        self.main_container.grid(row=0, column=1, sticky="nsew")
        self.main_container.grid_rowconfigure(0, weight=1)
        self.main_container.grid_columnconfigure(0, weight=1)

        self.tab_dash = self._create_dashboard_tab()
        self.tab_settings = self._create_settings_tab()
        self.tab_logs = self._create_logs_tab()
        self.tab_help = self._create_help_tab()

        self._select_tab("dash")

    def _select_tab(self, name: str):
        for tab in [self.tab_dash, self.tab_settings, self.tab_logs, self.tab_help]:
            tab.grid_forget()

        for btn in [self.nav_btn_dash, self.nav_btn_settings, self.nav_btn_logs, self.nav_btn_help]:
            btn.configure(fg_color="transparent", font=ctk.CTkFont(size=14))

        if name == "dash":
            self.tab_dash.grid(row=0, column=0, sticky="nsew", padx=20, pady=20)
            self.nav_btn_dash.configure(fg_color=COLOR_ACCENT, font=ctk.CTkFont(size=14, weight="bold"))
        elif name == "settings":
            self.tab_settings.grid(row=0, column=0, sticky="nsew", padx=20, pady=20)
            self.nav_btn_settings.configure(fg_color=COLOR_ACCENT, font=ctk.CTkFont(size=14, weight="bold"))
        elif name == "logs":
            self.tab_logs.grid(row=0, column=0, sticky="nsew", padx=20, pady=20)
            self.nav_btn_logs.configure(fg_color=COLOR_ACCENT, font=ctk.CTkFont(size=14, weight="bold"))
        elif name == "help":
            self.tab_help.grid(row=0, column=0, sticky="nsew", padx=20, pady=20)
            self.nav_btn_help.configure(fg_color=COLOR_ACCENT, font=ctk.CTkFont(size=14, weight="bold"))

    # ==========================
    # ВКЛАДКА: ДАШБОРД (ГЛАВНАЯ)
    # ==========================
    def _create_dashboard_tab(self) -> ctk.CTkScrollableFrame:
        tab = ctk.CTkScrollableFrame(self.main_container, fg_color="transparent")
        tab.grid_columnconfigure(0, weight=1)

        # 1. Секция: Токен
        token_card = ctk.CTkFrame(tab, fg_color=COLOR_CARD, corner_radius=12)
        token_card.grid(row=0, column=0, sticky="ew", pady=(0, 15), padx=5)
        token_card.grid_columnconfigure(0, weight=1)

        t_title_row = ctk.CTkFrame(token_card, fg_color="transparent")
        t_title_row.grid(row=0, column=0, columnspan=2, sticky="ew", padx=15, pady=(12, 6))
        t_title_row.grid_columnconfigure(0, weight=1)

        t_title = ctk.CTkLabel(
            t_title_row,
            text="🔑 Авторизация Discord (User Token)",
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color=COLOR_TEXT_MAIN
        )
        t_title.grid(row=0, column=0, sticky="w")

        self.auto_grab_btn = ctk.CTkButton(
            t_title_row,
            text="⚡ АВТО-ЗАХВАТ ТОКЕНА",
            font=ctk.CTkFont(size=12, weight="bold"),
            height=30,
            fg_color=COLOR_SUCCESS,
            hover_color=COLOR_SUCCESS_HOVER,
            command=self._on_auto_grab_token_click
        )
        self.auto_grab_btn.grid(row=0, column=1, sticky="e")

        token_row = ctk.CTkFrame(token_card, fg_color="transparent")
        token_row.grid(row=1, column=0, columnspan=2, sticky="ew", padx=15, pady=(0, 10))
        token_row.grid_columnconfigure(0, weight=1)

        self.token_entry = ctk.CTkEntry(
            token_row,
            placeholder_text="Вставьте ваш токен или нажмите «⚡ Авто-захват токена»...",
            show="•",
            height=38,
            font=ctk.CTkFont(size=13)
        )
        self.token_entry.grid(row=0, column=0, sticky="ew", padx=(0, 8))

        self.show_token_btn = ctk.CTkButton(
            token_row,
            text="👁️",
            width=40,
            height=38,
            fg_color=COLOR_CARD_HOVER,
            hover_color="#4E5058",
            command=self._toggle_token_visibility
        )
        self.show_token_btn.grid(row=0, column=1, padx=(0, 8))

        self.check_token_btn = ctk.CTkButton(
            token_row,
            text="🔍 Проверить",
            width=110,
            height=38,
            fg_color=COLOR_ACCENT,
            hover_color=COLOR_ACCENT_HOVER,
            command=self._on_check_token_click
        )
        self.check_token_btn.grid(row=0, column=2)

        self.account_info_lbl = ctk.CTkLabel(
            token_card,
            text="Статус токена: Не проверен",
            font=ctk.CTkFont(size=12),
            text_color=COLOR_TEXT_MUTED
        )
        self.account_info_lbl.grid(row=2, column=0, columnspan=2, sticky="w", padx=15, pady=(0, 12))

        # 2. Секция: Адресат (Сервер/Канал бота или Друг)
        target_card = ctk.CTkFrame(tab, fg_color=COLOR_CARD, corner_radius=12)
        target_card.grid(row=1, column=0, sticky="ew", pady=(0, 15), padx=5)
        target_card.grid_columnconfigure(0, weight=1)

        target_title_row = ctk.CTkFrame(target_card, fg_color="transparent")
        target_title_row.grid(row=0, column=0, sticky="ew", padx=15, pady=(12, 6))
        target_title_row.grid_columnconfigure(0, weight=1)

        target_title = ctk.CTkLabel(
            target_title_row,
            text="🎯 Адресат (Канал сервера с ботом / ЛС друга)",
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color=COLOR_TEXT_MAIN
        )
        target_title.grid(row=0, column=0, sticky="w")

        btn_box = ctk.CTkFrame(target_title_row, fg_color="transparent")
        btn_box.grid(row=0, column=1, sticky="e")

        self.pick_guild_btn = ctk.CTkButton(
            btn_box,
            text="🏰 СЕРВЕРЫ И КАНАЛЫ (ДЛЯ БОТОВ)",
            font=ctk.CTkFont(size=12, weight="bold"),
            height=30,
            fg_color="#8E44AD",
            hover_color="#7D3C98",
            command=self._on_pick_guild_channel_click
        )
        self.pick_guild_btn.pack(side="left", padx=(0, 8))

        self.pick_friend_btn = ctk.CTkButton(
            btn_box,
            text="👥 ДРУЗЬЯ (ЛС)",
            font=ctk.CTkFont(size=12, weight="bold"),
            height=30,
            fg_color=COLOR_ACCENT,
            hover_color=COLOR_ACCENT_HOVER,
            command=self._on_pick_friend_click
        )
        self.pick_friend_btn.pack(side="left")

        self.target_type_var = ctk.StringVar(value="channel_id")

        radio_row = ctk.CTkFrame(target_card, fg_color="transparent")
        radio_row.grid(row=1, column=0, sticky="w", padx=15, pady=(0, 8))

        self.radio_channel = ctk.CTkRadioButton(
            radio_row,
            text="💬 Канал сервера (Рекомендуется для ботов /waifu random)",
            variable=self.target_type_var,
            value="channel_id",
            command=self._on_target_type_change
        )
        self.radio_channel.pack(side="left", padx=(0, 20))

        self.radio_user = ctk.CTkRadioButton(
            radio_row,
            text="👤 Личные сообщения (ID друга)",
            variable=self.target_type_var,
            value="user_id",
            command=self._on_target_type_change
        )
        self.radio_user.pack(side="left")

        target_input_row = ctk.CTkFrame(target_card, fg_color="transparent")
        target_input_row.grid(row=2, column=0, sticky="ew", padx=15, pady=(0, 6))
        target_input_row.grid_columnconfigure(0, weight=1)

        self.target_id_entry = ctk.CTkEntry(
            target_input_row,
            placeholder_text="Введите ID канала (для ботов) или ID друга...",
            height=38,
            font=ctk.CTkFont(size=13)
        )
        self.target_id_entry.grid(row=0, column=0, sticky="ew", padx=(0, 8))

        self.btn_pick_server_quick = ctk.CTkButton(
            target_input_row,
            text="🏰 Серверы",
            width=90,
            height=38,
            fg_color=COLOR_CARD_HOVER,
            hover_color="#4E5058",
            command=self._on_pick_guild_channel_click
        )
        self.btn_pick_server_quick.grid(row=0, column=1, padx=(0, 6))

        self.target_quick_btn = ctk.CTkButton(
            target_input_row,
            text="👥 Друзья",
            width=90,
            height=38,
            fg_color=COLOR_CARD_HOVER,
            hover_color="#4E5058",
            command=self._on_pick_friend_click
        )
        self.target_quick_btn.grid(row=0, column=2)

        self.target_info_lbl = ctk.CTkLabel(
            target_card,
            text="Адресат не выбран. Для бота выберите «🏰 СЕРВЕРЫ И КАНАЛЫ», для друга — «👥 ДРУЗЬЯ (ЛС)».",
            font=ctk.CTkFont(size=12),
            text_color=COLOR_TEXT_MUTED
        )
        self.target_info_lbl.grid(row=3, column=0, sticky="w", padx=15, pady=(0, 12))

        # 3. Секция: Сообщения, Пресет Фембоя, Избранные GIF & Боты
        msg_card = ctk.CTkFrame(tab, fg_color=COLOR_CARD, corner_radius=12)
        msg_card.grid(row=2, column=0, sticky="ew", pady=(0, 15), padx=5)
        msg_card.grid_columnconfigure(0, weight=1)

        msg_title_row = ctk.CTkFrame(msg_card, fg_color="transparent")
        msg_title_row.grid(row=0, column=0, sticky="ew", padx=15, pady=(12, 4))
        msg_title_row.grid_columnconfigure(0, weight=1)

        msg_title = ctk.CTkLabel(
            msg_title_row,
            text="✉️ Текст сообщений, Избранные GIF & Пресеты",
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color=COLOR_TEXT_MAIN
        )
        msg_title.grid(row=0, column=0, sticky="w")

        right_btn_box = ctk.CTkFrame(msg_title_row, fg_color="transparent")
        right_btn_box.grid(row=0, column=1, sticky="e")

        self.btn_manage_gifs_top = ctk.CTkButton(
            right_btn_box,
            text=f"🖼️ Избранные GIF ({len(self.favorite_gifs)})",
            font=ctk.CTkFont(size=12, weight="bold"),
            height=28,
            fg_color="#2E86C1",
            hover_color="#1B4F72",
            command=self._show_gif_manager_modal
        )
        self.btn_manage_gifs_top.pack(side="left", padx=(0, 6))

        preview_btn = ctk.CTkButton(
            right_btn_box,
            text="🎲 Предпросмотр",
            font=ctk.CTkFont(size=12),
            height=28,
            fg_color=COLOR_CARD_HOVER,
            hover_color="#4E5058",
            command=self._on_preview_msg_click
        )
        preview_btn.pack(side="left")

        # ПАНЕЛЬ ПРЕСЕТОВ: РЯД 1 (ФЕМБОЙ И ГОТОВЫЕ НАБОРЫ)
        femboy_bar = ctk.CTkFrame(msg_card, fg_color="#241B28", corner_radius=8)
        femboy_bar.grid(row=1, column=0, sticky="ew", padx=15, pady=(2, 5))

        lbl_fem = ctk.CTkLabel(femboy_bar, text="🎀 Готовые пресеты:", font=ctk.CTkFont(size=12, weight="bold"), text_color="#FF69B4")
        lbl_fem.pack(side="left", padx=(10, 8), pady=6)

        btn_femboy_250 = ctk.CTkButton(
            femboy_bar,
            text="🎀 ЗАГРУЗИТЬ МЕГА-ПРЕСЕТ ФЕМБОЯ (250 СООБЩЕНИЙ)",
            font=ctk.CTkFont(size=12, weight="bold"),
            height=28,
            fg_color=COLOR_PINK,
            hover_color=COLOR_PINK_HOVER,
            command=self._load_femboy_preset
        )
        btn_femboy_250.pack(side="left", padx=4, pady=6)

        btn_clear_msgs = ctk.CTkButton(
            femboy_bar,
            text="🗑️ Очистить список",
            font=ctk.CTkFont(size=11),
            height=28,
            fg_color="#383A40",
            hover_color="#4E5058",
            command=self._clear_messages_box
        )
        btn_clear_msgs.pack(side="right", padx=(4, 10), pady=6)

        # ПАНЕЛЬ ПРЕСЕТОВ: РЯД 2 (NEKOTINA & БОТЫ)
        presets_bar = ctk.CTkFrame(msg_card, fg_color="#26282C", corner_radius=8)
        presets_bar.grid(row=2, column=0, sticky="ew", padx=15, pady=(0, 8))

        lbl_pres = ctk.CTkLabel(presets_bar, text="🐱 Nekotina & Боты:", font=ctk.CTkFont(size=12, weight="bold"), text_color=COLOR_PURPLE)
        lbl_pres.pack(side="left", padx=(10, 8), pady=6)

        btn_waifu = ctk.CTkButton(
            presets_bar,
            text="➕ /waifu random",
            font=ctk.CTkFont(size=11, weight="bold"),
            height=26,
            fg_color="#433554",
            hover_color="#5E437C",
            command=lambda: self._insert_text_to_messages("/waifu random")
        )
        btn_waifu.pack(side="left", padx=3, pady=6)

        btn_waifu_prefix = ctk.CTkButton(
            presets_bar,
            text="➕ n.waifu",
            font=ctk.CTkFont(size=11),
            height=26,
            fg_color="#313338",
            hover_color=COLOR_CARD_HOVER,
            command=lambda: self._insert_text_to_messages("n.waifu")
        )
        btn_waifu_prefix.pack(side="left", padx=3, pady=6)

        btn_daily = ctk.CTkButton(
            presets_bar,
            text="➕ /daily",
            font=ctk.CTkFont(size=11),
            height=26,
            fg_color="#313338",
            hover_color=COLOR_CARD_HOVER,
            command=lambda: self._insert_text_to_messages("/daily")
        )
        btn_daily.pack(side="left", padx=3, pady=6)

        btn_profile = ctk.CTkButton(
            presets_bar,
            text="➕ /profile",
            font=ctk.CTkFont(size=11),
            height=26,
            fg_color="#313338",
            hover_color=COLOR_CARD_HOVER,
            command=lambda: self._insert_text_to_messages("/profile")
        )
        btn_profile.pack(side="left", padx=3, pady=6)

        btn_scan_cmds = ctk.CTkButton(
            presets_bar,
            text="🔍 Все команды канала",
            font=ctk.CTkFont(size=11, weight="bold"),
            height=26,
            fg_color=COLOR_ACCENT,
            hover_color=COLOR_ACCENT_HOVER,
            command=self._on_browse_channel_commands_click
        )
        btn_scan_cmds.pack(side="right", padx=(3, 10), pady=6)

        msg_hint = ctk.CTkLabel(
            msg_card,
            text=f"💡 Избранные GIF активны ({len(self.favorite_gifs)} шт.) • При отправке будет автоматически прикрепляться случайная GIF из базы.",
            font=ctk.CTkFont(size=11),
            text_color="#57F287"
        )
        msg_hint.grid(row=3, column=0, sticky="w", padx=15, pady=(0, 6))

        self.messages_textbox = ctk.CTkTextbox(
            msg_card,
            height=140,
            font=ctk.CTkFont(size=13),
            fg_color="#202225"
        )
        self.messages_textbox.grid(row=4, column=0, sticky="ew", padx=15, pady=(0, 15))

        # 4. Секция: Управление и Статистика
        control_card = ctk.CTkFrame(tab, fg_color=COLOR_CARD, corner_radius=12)
        control_card.grid(row=3, column=0, sticky="ew", pady=(0, 15), padx=5)
        control_card.grid_columnconfigure((0, 1, 2), weight=1)

        self.start_btn = ctk.CTkButton(
            control_card,
            text="▶️ НАЧАТЬ ОТПРАВКУ",
            font=ctk.CTkFont(size=15, weight="bold"),
            height=46,
            fg_color=COLOR_SUCCESS,
            hover_color=COLOR_SUCCESS_HOVER,
            command=self._on_start_click
        )
        self.start_btn.grid(row=0, column=0, padx=12, pady=15, sticky="ew")

        self.pause_btn = ctk.CTkButton(
            control_card,
            text="⏸️ ПАУЗА",
            font=ctk.CTkFont(size=15, weight="bold"),
            height=46,
            fg_color=COLOR_WARNING,
            hover_color="#D99B26",
            state="disabled",
            command=self._on_pause_click
        )
        self.pause_btn.grid(row=0, column=1, padx=6, pady=15, sticky="ew")

        self.stop_btn = ctk.CTkButton(
            control_card,
            text="⏹️ СТОП",
            font=ctk.CTkFont(size=15, weight="bold"),
            height=46,
            fg_color=COLOR_DANGER,
            hover_color="#D83A3E",
            state="disabled",
            command=self._on_stop_click
        )
        self.stop_btn.grid(row=0, column=2, padx=12, pady=15, sticky="ew")

        # Статистика
        stats_row = ctk.CTkFrame(control_card, fg_color="#202225", corner_radius=8)
        stats_row.grid(row=1, column=0, columnspan=3, sticky="ew", padx=12, pady=(0, 15))
        stats_row.grid_columnconfigure((0, 1, 2, 3), weight=1)

        self.stat_sent_lbl = ctk.CTkLabel(
            stats_row,
            text="Выполнено: 0",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color="#57F287"
        )
        self.stat_sent_lbl.grid(row=0, column=0, pady=10)

        self.stat_err_lbl = ctk.CTkLabel(
            stats_row,
            text="Ошибок: 0",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color="#ED4245"
        )
        self.stat_err_lbl.grid(row=0, column=1, pady=10)

        self.stat_time_lbl = ctk.CTkLabel(
            stats_row,
            text="Время: 00:00:00",
            font=ctk.CTkFont(size=13),
            text_color=COLOR_TEXT_MAIN
        )
        self.stat_time_lbl.grid(row=0, column=2, pady=10)

        self.stat_next_lbl = ctk.CTkLabel(
            stats_row,
            text="След. через: -",
            font=ctk.CTkFont(size=13),
            text_color=COLOR_TEXT_MUTED
        )
        self.stat_next_lbl.grid(row=0, column=3, pady=10)

        return tab

    # ==========================
    # ВКЛАДКА: НАСТРОЙКИ, СТАТУС & ТРЕЙ
    # ==========================
    def _create_settings_tab(self) -> ctk.CTkScrollableFrame:
        tab = ctk.CTkScrollableFrame(self.main_container, fg_color="transparent")
        tab.grid_columnconfigure(0, weight=1)

        # 1. Кастомный статус Discord & Авторство (Aharen7san)
        status_card = ctk.CTkFrame(tab, fg_color=COLOR_CARD, corner_radius=12)
        status_card.grid(row=0, column=0, sticky="ew", pady=(0, 15), padx=5)
        status_card.grid_columnconfigure(1, weight=1)

        s_title = ctk.CTkLabel(
            status_card,
            text="👑 Кастомный статус Discord & Авторство",
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color=COLOR_TEXT_MAIN
        )
        s_title.grid(row=0, column=0, columnspan=2, sticky="w", padx=15, pady=(12, 8))

        self.discord_status_var = ctk.BooleanVar(value=True)
        self.discord_status_switch = ctk.CTkSwitch(
            status_card,
            text="👑 Устанавливать статус Discord во время отправки (с указанием пресета и автора)",
            variable=self.discord_status_var
        )
        self.discord_status_switch.grid(row=1, column=0, columnspan=2, sticky="w", padx=15, pady=(0, 8))

        author_row = ctk.CTkFrame(status_card, fg_color="transparent")
        author_row.grid(row=2, column=0, columnspan=2, sticky="w", padx=15, pady=(0, 8))

        lbl_auth = ctk.CTkLabel(author_row, text="Ник автора:", font=ctk.CTkFont(size=13))
        lbl_auth.pack(side="left", padx=(0, 8))

        self.discord_creator_entry = ctk.CTkEntry(author_row, width=140)
        self.discord_creator_entry.pack(side="left", padx=(0, 15))

        lbl_pres_name = ctk.CTkLabel(author_row, text="Название пресета:", font=ctk.CTkFont(size=13))
        lbl_pres_name.pack(side="left", padx=(0, 8))

        self.discord_preset_entry = ctk.CTkEntry(author_row, width=160)
        self.discord_preset_entry.pack(side="left")

        status_hint = ctk.CTkLabel(
            status_card,
            text="💡 Пример статуса в Discord профиле: «🎀 AutoMsg by Aharen7san | Пресет: Фембой • #15»",
            font=ctk.CTkFont(size=11),
            text_color=COLOR_TEXT_MUTED
        )
        status_hint.grid(row=3, column=0, columnspan=2, sticky="w", padx=15, pady=(0, 12))

        # 2. Системный трей Windows
        tray_card = ctk.CTkFrame(tab, fg_color=COLOR_CARD, corner_radius=12)
        tray_card.grid(row=1, column=0, sticky="ew", pady=(0, 15), padx=5)
        tray_card.grid_columnconfigure(1, weight=1)

        tr_title = ctk.CTkLabel(
            tray_card,
            text="📥 Скрытие в системный трей (System Tray)",
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color=COLOR_TEXT_MAIN
        )
        tr_title.grid(row=0, column=0, columnspan=2, sticky="w", padx=15, pady=(12, 8))

        self.minimize_tray_var = ctk.BooleanVar(value=True)
        self.minimize_tray_switch = ctk.CTkSwitch(
            tray_card,
            text="📥 Сворачивать в трей при нажатии на крестик (закрытие окна)",
            variable=self.minimize_tray_var
        )
        self.minimize_tray_switch.grid(row=1, column=0, columnspan=2, sticky="w", padx=15, pady=(0, 12))

        # 3. Избранные GIF
        gif_card = ctk.CTkFrame(tab, fg_color=COLOR_CARD, corner_radius=12)
        gif_card.grid(row=2, column=0, sticky="ew", pady=(0, 15), padx=5)
        gif_card.grid_columnconfigure(1, weight=1)

        g_title = ctk.CTkLabel(
            gif_card,
            text=f"🖼️ Авто-прикрепление GIF из избранного ({len(self.favorite_gifs)} шт.)",
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color=COLOR_TEXT_MAIN
        )
        g_title.grid(row=0, column=0, columnspan=2, sticky="w", padx=15, pady=(12, 8))

        self.attach_gif_var = ctk.BooleanVar(value=True)
        self.attach_gif_switch = ctk.CTkSwitch(
            gif_card,
            text="🖼️ Прикреплять случайную GIF из избранного к каждому сообщению",
            variable=self.attach_gif_var
        )
        self.attach_gif_switch.grid(row=1, column=0, columnspan=2, sticky="w", padx=15, pady=(0, 8))

        chance_row = ctk.CTkFrame(gif_card, fg_color="transparent")
        chance_row.grid(row=2, column=0, columnspan=2, sticky="w", padx=15, pady=(0, 12))

        lbl_ch = ctk.CTkLabel(chance_row, text="Шанс прикрепления GIF (%):", font=ctk.CTkFont(size=13))
        lbl_ch.pack(side="left", padx=(0, 8))

        self.gif_chance_entry = ctk.CTkEntry(chance_row, width=70)
        self.gif_chance_entry.pack(side="left", padx=(0, 15))

        btn_open_gifs = ctk.CTkButton(
            chance_row,
            text=f"🖼️ Менеджер GIF ({len(self.favorite_gifs)} шт.)",
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color="#2E86C1",
            hover_color="#1B4F72",
            height=32,
            command=self._show_gif_manager_modal
        )
        btn_open_gifs.pack(side="left")

        # 4. Тайминги и интервалы
        timing_card = ctk.CTkFrame(tab, fg_color=COLOR_CARD, corner_radius=12)
        timing_card.grid(row=3, column=0, sticky="ew", pady=(0, 15), padx=5)
        timing_card.grid_columnconfigure(1, weight=1)

        t_title = ctk.CTkLabel(
            timing_card,
            text="⏱️ Настройки интервалов отправки",
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color=COLOR_TEXT_MAIN
        )
        t_title.grid(row=0, column=0, columnspan=2, sticky="w", padx=15, pady=(12, 8))

        self.interval_mode_var = ctk.StringVar(value="random")

        i_radio_row = ctk.CTkFrame(timing_card, fg_color="transparent")
        i_radio_row.grid(row=1, column=0, columnspan=2, sticky="w", padx=15, pady=(0, 10))

        self.radio_interval_random = ctk.CTkRadioButton(
            i_radio_row,
            text="🎲 Случайный диапазон (рекомендуется для естественности)",
            variable=self.interval_mode_var,
            value="random",
            command=self._on_interval_mode_change
        )
        self.radio_interval_random.pack(anchor="w", pady=4)

        self.radio_interval_fixed = ctk.CTkRadioButton(
            i_radio_row,
            text="📏 Фиксированный интервал",
            variable=self.interval_mode_var,
            value="fixed",
            command=self._on_interval_mode_change
        )
        self.radio_interval_fixed.pack(anchor="w", pady=4)

        self.random_interval_frame = ctk.CTkFrame(timing_card, fg_color="transparent")
        self.random_interval_frame.grid(row=2, column=0, columnspan=2, sticky="ew", padx=15, pady=(0, 10))

        lbl_min = ctk.CTkLabel(self.random_interval_frame, text="От (сек):", font=ctk.CTkFont(size=13))
        lbl_min.pack(side="left", padx=(0, 6))

        self.rand_min_entry = ctk.CTkEntry(self.random_interval_frame, width=70)
        self.rand_min_entry.pack(side="left", padx=(0, 15))

        lbl_max = ctk.CTkLabel(self.random_interval_frame, text="До (сек):", font=ctk.CTkFont(size=13))
        lbl_max.pack(side="left", padx=(0, 6))

        self.rand_max_entry = ctk.CTkEntry(self.random_interval_frame, width=70)
        self.rand_max_entry.pack(side="left")

        self.fixed_interval_frame = ctk.CTkFrame(timing_card, fg_color="transparent")
        self.fixed_interval_frame.grid(row=3, column=0, columnspan=2, sticky="ew", padx=15, pady=(0, 15))

        lbl_fix = ctk.CTkLabel(self.fixed_interval_frame, text="Каждые (сек):", font=ctk.CTkFont(size=13))
        lbl_fix.pack(side="left", padx=(0, 6))

        self.fixed_entry = ctk.CTkEntry(self.fixed_interval_frame, width=80)
        self.fixed_entry.pack(side="left")

        # 5. Режим выполнения команд ботов
        cmd_card = ctk.CTkFrame(tab, fg_color=COLOR_CARD, corner_radius=12)
        cmd_card.grid(row=4, column=0, sticky="ew", pady=(0, 15), padx=5)
        cmd_card.grid_columnconfigure(1, weight=1)

        c_title = ctk.CTkLabel(
            cmd_card,
            text="⚡ Режим выполнения команд ботов",
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color=COLOR_TEXT_MAIN
        )
        c_title.grid(row=0, column=0, columnspan=2, sticky="w", padx=15, pady=(12, 8))

        c_mode_row = ctk.CTkFrame(cmd_card, fg_color="transparent")
        c_mode_row.grid(row=1, column=0, columnspan=2, sticky="w", padx=15, pady=(0, 8))

        lbl_cmode = ctk.CTkLabel(c_mode_row, text="Способ отправки: ", font=ctk.CTkFont(size=13))
        lbl_cmode.pack(side="left", padx=(0, 8))

        self.command_mode_combo = ctk.CTkComboBox(
            c_mode_row,
            values=["Только Slash-команды (Interactions API)", "Авто (Slash с переходом на текст)", "Только текстовые сообщения"],
            width=280
        )
        self.command_mode_combo.pack(side="left")

        self.fallback_to_text_var = ctk.BooleanVar(value=True)
        self.fallback_switch = ctk.CTkSwitch(
            cmd_card,
            text="🛡️ Отправить команду как обычный текст, если бот не поддерживает Slash API в канале",
            variable=self.fallback_to_text_var
        )
        self.fallback_switch.grid(row=2, column=0, sticky="w", padx=15, pady=(6, 15))

        # 6. Лимиты отправки
        limit_card = ctk.CTkFrame(tab, fg_color=COLOR_CARD, corner_radius=12)
        limit_card.grid(row=5, column=0, sticky="ew", pady=(0, 15), padx=5)
        limit_card.grid_columnconfigure(1, weight=1)

        l_title = ctk.CTkLabel(
            limit_card,
            text="🛑 Лимит количества выполнений",
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color=COLOR_TEXT_MAIN
        )
        l_title.grid(row=0, column=0, columnspan=2, sticky="w", padx=15, pady=(12, 8))

        self.limit_mode_var = ctk.StringVar(value="infinite")

        self.radio_limit_inf = ctk.CTkRadioButton(
            limit_card,
            text="♾️ Бесконечно (пока не нажмете СТОП)",
            variable=self.limit_mode_var,
            value="infinite"
        )
        self.radio_limit_inf.grid(row=1, column=0, sticky="w", padx=15, pady=4)

        l_count_row = ctk.CTkFrame(limit_card, fg_color="transparent")
        l_count_row.grid(row=2, column=0, columnspan=2, sticky="w", padx=15, pady=(4, 15))

        self.radio_limit_count = ctk.CTkRadioButton(
            l_count_row,
            text="🔢 Остановиться после (кол-во):",
            variable=self.limit_mode_var,
            value="count"
        )
        self.radio_limit_count.pack(side="left", padx=(0, 8))

        self.max_count_entry = ctk.CTkEntry(l_count_row, width=80)
        self.max_count_entry.pack(side="left")

        # 7. Режим выбора сообщений и имитация
        behavior_card = ctk.CTkFrame(tab, fg_color=COLOR_CARD, corner_radius=12)
        behavior_card.grid(row=6, column=0, sticky="ew", pady=(0, 15), padx=5)
        behavior_card.grid_columnconfigure(1, weight=1)

        b_title = ctk.CTkLabel(
            behavior_card,
            text="🎭 Поведение и имитация человека",
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color=COLOR_TEXT_MAIN
        )
        b_title.grid(row=0, column=0, columnspan=2, sticky="w", padx=15, pady=(12, 8))

        self.msg_mode_var = ctk.StringVar(value="random")

        b_mode_row = ctk.CTkFrame(behavior_card, fg_color="transparent")
        b_mode_row.grid(row=1, column=0, columnspan=2, sticky="w", padx=15, pady=(0, 8))

        lbl_sel = ctk.CTkLabel(b_mode_row, text="Выбор сообщения/команды: ", font=ctk.CTkFont(size=13))
        lbl_sel.pack(side="left", padx=(0, 8))

        self.msg_mode_combo = ctk.CTkComboBox(
            b_mode_row,
            values=["Случайное из списка", "По порядку (по кругу)"],
            variable=self.msg_mode_var,
            width=200
        )
        self.msg_mode_combo.pack(side="left")

        self.use_typing_var = ctk.BooleanVar(value=True)
        self.typing_switch = ctk.CTkSwitch(
            behavior_card,
            text="💬 Имитировать статус «печатает...» перед отправкой сообщений",
            variable=self.use_typing_var
        )
        self.typing_switch.grid(row=2, column=0, sticky="w", padx=15, pady=6)

        self.tts_var = ctk.BooleanVar(value=False)
        self.tts_switch = ctk.CTkSwitch(
            behavior_card,
            text="📢 Отправлять обычные сообщения с озвучкой (TTS)",
            variable=self.tts_var
        )
        self.tts_switch.grid(row=3, column=0, sticky="w", padx=15, pady=6)

        self.save_token_var = ctk.BooleanVar(value=True)
        self.save_token_switch = ctk.CTkSwitch(
            behavior_card,
            text="🔒 Сохранять токен в файле config.json при выходе",
            variable=self.save_token_var
        )
        self.save_token_switch.grid(row=4, column=0, sticky="w", padx=15, pady=(6, 15))

        save_btn = ctk.CTkButton(
            tab,
            text="💾 СОХРАНИТЬ ВСЕ НАСТРОЙКИ",
            font=ctk.CTkFont(size=14, weight="bold"),
            height=42,
            fg_color=COLOR_ACCENT,
            hover_color=COLOR_ACCENT_HOVER,
            command=self._on_save_settings_click
        )
        save_btn.grid(row=7, column=0, sticky="ew", padx=5, pady=(0, 20))

        return tab

    # ==========================
    # ВКЛАДКА: ЛОГИ И КОНСОЛЬ
    # ==========================
    def _create_logs_tab(self) -> ctk.CTkFrame:
        tab = ctk.CTkFrame(self.main_container, fg_color="transparent")
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(1, weight=1)

        top_bar = ctk.CTkFrame(tab, fg_color=COLOR_CARD, corner_radius=10)
        top_bar.grid(row=0, column=0, sticky="ew", pady=(0, 10))

        lbl = ctk.CTkLabel(
            top_bar,
            text="📜 Журнал событий, слеш-команд и ответов Discord",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=COLOR_TEXT_MAIN
        )
        lbl.pack(side="left", padx=15, pady=10)

        clear_btn = ctk.CTkButton(
            top_bar,
            text="🗑️ Очистить логи",
            width=120,
            height=32,
            fg_color=COLOR_CARD_HOVER,
            hover_color="#4E5058",
            command=self._clear_logs
        )
        clear_btn.pack(side="right", padx=15, pady=10)

        self.log_textbox = ctk.CTkTextbox(
            tab,
            font=ctk.CTkFont(family="Consolas", size=12),
            fg_color="#141517",
            text_color="#DCDDDE",
            wrap="word"
        )
        self.log_textbox.grid(row=1, column=0, sticky="nsew")

        try:
            self.log_textbox._textbox.tag_config("info", foreground="#DCDDDE")
            self.log_textbox._textbox.tag_config("success", foreground="#57F287")
            self.log_textbox._textbox.tag_config("warning", foreground="#FEE75C")
            self.log_textbox._textbox.tag_config("error", foreground="#ED4245")
            self.log_textbox._textbox.tag_config("accent", foreground="#5865F2")
        except Exception:
            pass

        return tab

    # ==========================
    # ВКЛАДКА: ИНСТРУКЦИЯ
    # ==========================
    def _create_help_tab(self) -> ctk.CTkScrollableFrame:
        tab = ctk.CTkScrollableFrame(self.main_container, fg_color="transparent")
        tab.grid_columnconfigure(0, weight=1)

        help_text = (
            "📖 ПОДРОБНАЯ ИНСТРУКЦИЯ ПО ИСПОЛЬЗОВАНИЮ\n\n"
            "👑 СТАТУС DISCORD И АВТОРСТВО (Aharen7san):\n"
            "--------------------------------------------------\n"
            "  • При запуске отправки в вашем Discord автоматически ставится красивый статус:\n"
            "    «🎀 AutoMsg by Aharen7san | Пресет: Фембой • #{count}».\n"
            "  • Вы можете настроить имя автора и название пресета во вкладке «Настройки & Статус».\n\n"
            "📥 СВОРАЧИВАНИЕ В СИСТЕМНЫЙ ТРЕЙ (SYSTEM TRAY):\n"
            "--------------------------------------------------\n"
            "  • Нажмите кнопку «📥 СВЕРНУТЬ В ТРЕЙ» в левом меню, либо закройте окно крестиком.\n"
            "  • Приложение спрячется в трей около системных часов и продолжит отправку в фоне!\n"
            "  • Дважды кликните по иконке трея или нажмите правой кнопкой -> «📌 Показать окно».\n\n"
            "🖼️ ПРИКРЕПЛЕНИЕ СЛУЧАЙНЫХ GIF ИЗ ИЗБРАННОГО:\n"
            "--------------------------------------------------\n"
            "  • В приложение загружена вся ваша личная база из 1552 избранных GIF.\n"
            "  • К каждому сообщению автоматически прикрепляется случайная гифка.\n\n"
            "🎀 МЕГА-ПРЕСЕТ ФЕМБОЯ (250 СООБЩЕНИЙ):\n"
            "--------------------------------------------------\n"
            "  • Нажмите «🎀 ЗАГРУЗИТЬ МЕГА-ПРЕСЕТ ФЕМБОЯ (250 СООБЩЕНИЙ)».\n"
            "  • 250 уникальных сообщений с каомодзи (✿◠‿◠), UwU, Nya~ и Spintax.\n\n"
            "🐱 СЛЕШ-КОМАНДЫ БОТОВ (NEKOTINA, MUDAE И ДР.):\n"
            "--------------------------------------------------\n"
            "  1. Чтобы бот Nekotina отвечал на `/waifu random`:\n"
            "     • Выберите «🏰 СЕРВЕРЫ И КАНАЛЫ» и укажите текстовый канал сервера.\n"
            "     • Введите команду `/waifu random` и нажмите «▶️ НАЧАТЬ ОТПРАВКУ»."
        )

        card = ctk.CTkFrame(tab, fg_color=COLOR_CARD, corner_radius=12)
        card.grid(row=0, column=0, sticky="ew", padx=5, pady=5)
        card.grid_columnconfigure(0, weight=1)

        help_lbl = ctk.CTkLabel(
            card,
            text=help_text,
            font=ctk.CTkFont(size=13),
            justify="left",
            text_color=COLOR_TEXT_MAIN,
            wraplength=700
        )
        help_lbl.pack(padx=20, pady=20, anchor="w")

        return tab

    # ==========================
    # МЕНЕДЖЕР ИЗБРАННЫХ GIF
    # ==========================
    def _show_gif_manager_modal(self):
        """Модальное окно управления списком избранных GIF."""
        dialog = ctk.CTkToplevel(self)
        dialog.title("Менеджер избранных GIF")
        dialog.geometry("640x600")
        dialog.minsize(540, 480)
        dialog.transient(self)
        dialog.grab_set()

        top_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        top_frame.pack(fill="x", padx=20, pady=(15, 6))

        lbl = ctk.CTkLabel(
            top_frame,
            text=f"🖼️ Избранные GIF для отправки ({len(self.favorite_gifs)} ссылок):",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=COLOR_TEXT_MAIN
        )
        lbl.pack(side="left")

        actions_bar = ctk.CTkFrame(dialog, fg_color="#26282C", corner_radius=8)
        actions_bar.pack(fill="x", padx=20, pady=(0, 8))

        btn_sync = ctk.CTkButton(
            actions_bar,
            text="🔄 Синхронизировать с Discord",
            font=ctk.CTkFont(size=12, weight="bold"),
            height=28,
            fg_color=COLOR_ACCENT,
            hover_color=COLOR_ACCENT_HOVER,
            command=lambda: self._sync_discord_gifs(textbox, dialog)
        )
        btn_sync.pack(side="left", padx=(10, 6), pady=6)

        btn_load_def = ctk.CTkButton(
            actions_bar,
            text="🎀 Коллекция Аниме/Фембой",
            font=ctk.CTkFont(size=11),
            height=28,
            fg_color=COLOR_PINK,
            hover_color=COLOR_PINK_HOVER,
            command=lambda: self._load_default_gifs_into_box(textbox)
        )
        btn_load_def.pack(side="left", padx=4, pady=6)

        hint = ctk.CTkLabel(
            dialog,
            text="💡 Вставьте ссылки на Tenor, Giphy или .gif (каждая ссылка с новой строки):",
            font=ctk.CTkFont(size=11),
            text_color=COLOR_TEXT_MUTED
        )
        hint.pack(anchor="w", padx=20, pady=(0, 4))

        textbox = ctk.CTkTextbox(dialog, height=320, font=ctk.CTkFont(family="Consolas", size=12), fg_color="#141517")
        textbox.pack(fill="both", expand=True, padx=20, pady=5)
        textbox.insert("1.0", "\n".join(self.favorite_gifs))

        btn_row = ctk.CTkFrame(dialog, fg_color="transparent")
        btn_row.pack(fill="x", padx=20, pady=(10, 15))

        def save_and_close():
            raw = textbox.get("1.0", "end-1c").strip().splitlines()
            clean = [x.strip() for x in raw if x.strip() and x.strip().startswith("http")]
            if not clean:
                clean = list(DEFAULT_FAVORITE_GIFS)
            self.favorite_gifs = clean
            self.btn_manage_gifs_top.configure(text=f"🖼️ Избранные GIF ({len(self.favorite_gifs)})")
            self.log_message(f"Сохранено {len(self.favorite_gifs)} GIF в список избранного!", "success")
            cfg = self._get_current_gui_config()
            save_config(cfg)
            dialog.destroy()

        btn_save = ctk.CTkButton(
            btn_row,
            text="💾 СОХРАНИТЬ СПИСОК GIF",
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color=COLOR_SUCCESS,
            hover_color=COLOR_SUCCESS_HOVER,
            height=36,
            command=save_and_close
        )
        btn_save.pack(side="left", fill="x", expand=True, padx=(0, 8))

        btn_cancel = ctk.CTkButton(
            btn_row,
            text="Отмена",
            fg_color=COLOR_CARD_HOVER,
            hover_color="#4E5058",
            height=36,
            command=dialog.destroy
        )
        btn_cancel.pack(side="right", padx=(0, 0))

    def _sync_discord_gifs(self, textbox: ctk.CTkTextbox, dialog):
        token = self.token_entry.get().strip()
        if not token:
            self.log_message("Ошибка: Сначала укажите токен Discord!", "error")
            return

        self.log_message("🔍 Запрос избранных GIF из аккаунта Discord...", "info")

        def run():
            sender = DiscordSender(token, self.log_message)
            ok, gifs, msg = sender.get_discord_favorite_gifs()
            def update():
                if ok and gifs:
                    current_text = textbox.get("1.0", "end-1c").strip()
                    existing = set(x.strip() for x in current_text.splitlines() if x.strip())
                    new_added = [g for g in gifs if g not in existing]
                    all_gifs = list(existing) + new_added
                    textbox.delete("1.0", "end")
                    textbox.insert("1.0", "\n".join(all_gifs))
                    self.log_message(f"✅ Из Discord загружено {len(gifs)} GIF! Добавлено новых: {len(new_added)}.", "success")
                else:
                    self.log_message(f"Синхронизация GIF: {msg}", "warning")
            self.after(0, update)

        threading.Thread(target=run, daemon=True).start()

    def _load_default_gifs_into_box(self, textbox: ctk.CTkTextbox):
        textbox.delete("1.0", "end")
        textbox.insert("1.0", "\n".join(DEFAULT_FAVORITE_GIFS))
        self.log_message(f"Вставлена коллекция из {len(DEFAULT_FAVORITE_GIFS)} избранных GIF.", "info")

    # ==========================
    # ВНУТРЕННЯЯ ЛОГИКА И СВЯЗКА
    # ==========================
    def _load_femboy_preset(self):
        self.messages_textbox.delete("1.0", "end")
        self.messages_textbox.insert("1.0", "\n".join(FEMBOY_PRESET))
        self.msg_mode_combo.set("Случайное из списка")
        self.msg_mode_var.set("random")
        self.attach_gif_var.set(True)
        self.discord_preset_entry.delete(0, "end")
        self.discord_preset_entry.insert(0, "Фембой (250 msg)")
        self.log_message(f"🎀 Загружен Мега-Пресет Фембоя: {len(FEMBOY_PRESET)} уникальных сообщений + авто-прикрепление GIF!", "success")
        cfg = self._get_current_gui_config()
        save_config(cfg)

    def _clear_messages_box(self):
        self.messages_textbox.delete("1.0", "end")
        self.log_message("Список сообщений очищен.", "info")

    def _populate_fields_from_config(self):
        c = self.config_data
        saved_token = c.get("token", "")
        self.token_entry.insert(0, saved_token)

        target_type = c.get("target_type", "channel_id")
        self.target_type_var.set(target_type)
        self.target_id_entry.insert(0, c.get("target_id", ""))
        self._on_target_type_change()

        msgs = c.get("messages", [])
        if isinstance(msgs, list) and msgs:
            self.messages_textbox.insert("1.0", "\n".join(msgs))
        else:
            self.messages_textbox.insert("1.0", "\n".join(FEMBOY_PRESET[:5]))

        # Статус Discord & Авторство
        self.discord_status_var.set(c.get("discord_status_enabled", True))
        self.discord_creator_entry.delete(0, "end")
        self.discord_creator_entry.insert(0, c.get("discord_creator_nick", "Aharen7san"))
        self.discord_preset_entry.delete(0, "end")
        self.discord_preset_entry.insert(0, c.get("discord_status_preset", "Фембой"))

        # Трей
        self.minimize_tray_var.set(c.get("minimize_to_tray_on_close", True))

        # GIF настройки
        self.attach_gif_var.set(c.get("attach_gif", True))
        self.gif_chance_entry.delete(0, "end")
        self.gif_chance_entry.insert(0, str(c.get("gif_chance", 100)))

        loaded_gifs = c.get("favorite_gifs")
        if not loaded_gifs or len(loaded_gifs) <= 25:
            from presets import DEFAULT_FAVORITE_GIFS
            loaded_gifs = list(DEFAULT_FAVORITE_GIFS)
        self.favorite_gifs = loaded_gifs
        self.btn_manage_gifs_top.configure(text=f"🖼️ Избранные GIF ({len(self.favorite_gifs)})")

        raw_cmd_mode = c.get("command_mode", "slash_only")
        if raw_cmd_mode == "auto":
            self.command_mode_combo.set("Авто (Slash с переходом на текст)")
        elif raw_cmd_mode == "text_only":
            self.command_mode_combo.set("Только текстовые сообщения")
        else:
            self.command_mode_combo.set("Только Slash-команды (Interactions API)")

        self.fallback_to_text_var.set(c.get("fallback_to_text", True))

        self.interval_mode_var.set(c.get("interval_mode", "random"))
        self.rand_min_entry.insert(0, str(c.get("random_interval_min", 15.0)))
        self.rand_max_entry.insert(0, str(c.get("random_interval_max", 30.0)))
        self.fixed_entry.insert(0, str(c.get("fixed_interval", 15.0)))
        self._on_interval_mode_change()

        self.limit_mode_var.set(c.get("limit_mode", "infinite"))
        self.max_count_entry.insert(0, str(c.get("max_messages", 50)))

        mode_str = "Случайное из списка" if c.get("message_mode", "random") == "random" else "По порядку (по кругу)"
        self.msg_mode_combo.set(mode_str)
        self.use_typing_var.set(c.get("use_typing", True))
        self.tts_var.set(c.get("tts", False))
        self.save_token_var.set(c.get("save_token_on_exit", True))

        self.log_message(f"Приложение готово (Dev: Aharen7san). Избранные GIF: {len(self.favorite_gifs)} шт. Трей и статус активны.", "info")

        if not saved_token:
            self.after(600, self._on_auto_grab_token_click)
        else:
            self.after(600, self._on_check_token_click)

    def _insert_text_to_messages(self, text: str):
        curr = self.messages_textbox.get("1.0", "end-1c").strip()
        if curr:
            self.messages_textbox.insert("end", f"\n{text}")
        else:
            self.messages_textbox.insert("1.0", text)
        self.log_message(f"Добавлено в список: {text}", "accent")

    def _get_current_gui_config(self) -> dict:
        raw_msgs = self.messages_textbox.get("1.0", "end-1c").strip().splitlines()
        clean_msgs = [m.strip() for m in raw_msgs if m.strip()]
        if not clean_msgs:
            clean_msgs = ["/waifu random"]

        try:
            r_min = float(self.rand_min_entry.get().strip() or "15.0")
        except ValueError:
            r_min = 15.0

        try:
            r_max = float(self.rand_max_entry.get().strip() or "30.0")
        except ValueError:
            r_max = 30.0

        try:
            f_val = float(self.fixed_entry.get().strip() or "15.0")
        except ValueError:
            f_val = 15.0

        try:
            max_c = int(self.max_count_entry.get().strip() or "50")
        except ValueError:
            max_c = 50

        try:
            g_chance = int(self.gif_chance_entry.get().strip() or "100")
        except ValueError:
            g_chance = 100

        mode_val = "random" if self.msg_mode_combo.get() == "Случайное из списка" else "sequential"

        c_combo = self.command_mode_combo.get()
        if "Авто" in c_combo:
            cmd_mode_str = "auto"
        elif "Только текстовые" in c_combo:
            cmd_mode_str = "text_only"
        else:
            cmd_mode_str = "slash_only"

        return {
            "token": self.token_entry.get().strip(),
            "target_type": self.target_type_var.get(),
            "target_id": self.target_id_entry.get().strip(),
            "messages": clean_msgs,
            "message_mode": mode_val,
            "command_mode": cmd_mode_str,
            "fallback_to_text": self.fallback_to_text_var.get(),
            "attach_gif": self.attach_gif_var.get(),
            "gif_chance": g_chance,
            "favorite_gifs": self.favorite_gifs,
            "interval_mode": self.interval_mode_var.get(),
            "fixed_interval": f_val,
            "random_interval_min": r_min,
            "random_interval_max": r_max,
            "limit_mode": self.limit_mode_var.get(),
            "max_messages": max_c,
            "use_typing": self.use_typing_var.get(),
            "tts": self.tts_var.get(),
            "save_token_on_exit": self.save_token_var.get(),
            "discord_status_enabled": self.discord_status_var.get(),
            "discord_creator_nick": self.discord_creator_entry.get().strip() or "Aharen7san",
            "discord_status_preset": self.discord_preset_entry.get().strip() or "Фембой",
            "minimize_to_tray_on_close": self.minimize_tray_var.get()
        }

    def _toggle_token_visibility(self):
        if self.token_entry.cget("show") == "•":
            self.token_entry.configure(show="")
            self.show_token_btn.configure(text="🙈")
        else:
            self.token_entry.configure(show="•")
            self.show_token_btn.configure(text="👁️")

    def _on_target_type_change(self):
        t_type = self.target_type_var.get()
        if t_type == "user_id":
            self.target_id_entry.configure(placeholder_text="Введите ID друга или нажмите «👥 ДРУЗЬЯ (ЛС)»...")
        else:
            self.target_id_entry.configure(placeholder_text="Введите ID канала сервера или нажмите «🏰 СЕРВЕРЫ И КАНАЛЫ»...")

    def _on_interval_mode_change(self):
        pass

    def log_message(self, message: str, level: str = "info"):
        def append():
            timestamp = datetime.now().strftime("%H:%M:%S")
            tag = level.lower()
            text_to_insert = f"[{timestamp}] [{level.upper()}] {message}\n"
            self.log_textbox.insert("end", text_to_insert, tag)
            self.log_textbox.see("end")
        self.after(0, append)

    def _clear_logs(self):
        self.log_textbox.delete("1.0", "end")

    # ==========================
    # АВТО-ЗАХВАТ ТОКЕНА
    # ==========================
    def _on_auto_grab_token_click(self):
        self.account_info_lbl.configure(text="🔍 Поиск и расшифровка токенов в Discord / браузерах...", text_color=COLOR_WARNING)
        self.auto_grab_btn.configure(state="disabled", text="⏳ Поиск...")
        self.log_message("Запущен автоматический поиск токенов Discord на ПК...", "info")

        def run_scan():
            accounts = scan_and_extract_tokens()

            def update_ui():
                self.auto_grab_btn.configure(state="normal", text="⚡ АВТО-ЗАХВАТ ТОКЕНА")
                if not accounts:
                    self.account_info_lbl.configure(
                        text="⚠️ Токены не найдены автоматически. Укажите токен вручную.",
                        text_color=COLOR_WARNING
                    )
                    self.log_message("Автопоиск: активные токены Discord не обнаружены в хранилищах.", "warning")
                elif len(accounts) == 1:
                    acc = accounts[0]
                    self._apply_account(acc)
                else:
                    self.log_message(f"Обнаружено {len(accounts)} аккаунтов. Выберите нужный.", "info")
                    self._show_account_picker_modal(accounts)

            self.after(0, update_ui)

        threading.Thread(target=run_scan, daemon=True).start()

    def _apply_account(self, acc: dict):
        token = acc["token"]
        self.token_entry.delete(0, "end")
        self.token_entry.insert(0, token)
        name = acc["global_name"]
        uname = acc["username"]
        uid = acc["id"]
        source = acc["source"]

        self.account_info_lbl.configure(
            text=f"✅ Авторизован: {name} (@{uname}) | ID: {uid} (Источник: {source})",
            text_color=COLOR_SUCCESS
        )
        self.log_message(f"Успешно захвачен токен: {name} (@{uname}) из {source}", "success")
        cfg = self._get_current_gui_config()
        save_config(cfg)
        self._preload_friends(token)

    def _preload_friends(self, token: str):
        def fetch():
            sender = DiscordSender(token)
            ok, contacts, msg = sender.get_friends_and_dms()
            if ok:
                self.cached_contacts = contacts
        threading.Thread(target=fetch, daemon=True).start()

    def _show_account_picker_modal(self, accounts: List[dict]):
        dialog = ctk.CTkToplevel(self)
        dialog.title("Выберите аккаунт Discord")
        dialog.geometry("520x420")
        dialog.resizable(False, False)
        dialog.transient(self)
        dialog.grab_set()

        lbl = ctk.CTkLabel(
            dialog,
            text="⚡ Найдено несколько активных аккаунтов Discord:",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=COLOR_TEXT_MAIN
        )
        lbl.pack(padx=20, pady=(15, 10), anchor="w")

        scroll = ctk.CTkScrollableFrame(dialog, fg_color="transparent", height=280)
        scroll.pack(fill="both", expand=True, padx=15, pady=5)

        for acc in accounts:
            card = ctk.CTkFrame(scroll, fg_color=COLOR_CARD, corner_radius=10)
            card.pack(fill="x", pady=6)
            card.grid_columnconfigure(0, weight=1)

            title_txt = f"{acc['global_name']} (@{acc['username']})"
            info_txt = f"Источник: {acc['source']}  •  ID: {acc['id']}"

            title_l = ctk.CTkLabel(card, text=title_txt, font=ctk.CTkFont(size=13, weight="bold"), text_color=COLOR_TEXT_MAIN)
            title_l.grid(row=0, column=0, sticky="w", padx=12, pady=(8, 2))

            sub_l = ctk.CTkLabel(card, text=info_txt, font=ctk.CTkFont(size=11), text_color=COLOR_TEXT_MUTED)
            sub_l.grid(row=1, column=0, sticky="w", padx=12, pady=(0, 8))

            select_btn = ctk.CTkButton(
                card,
                text="Выбрать",
                width=90,
                height=32,
                fg_color=COLOR_ACCENT,
                hover_color=COLOR_ACCENT_HOVER,
                command=lambda a=acc: [self._apply_account(a), dialog.destroy()]
            )
            select_btn.grid(row=0, column=1, rowspan=2, padx=12, pady=8)

        close_btn = ctk.CTkButton(
            dialog,
            text="Закрыть",
            fg_color=COLOR_CARD_HOVER,
            hover_color="#4E5058",
            height=34,
            command=dialog.destroy
        )
        close_btn.pack(pady=(5, 15))

    # ==========================
    # ВЫБОР СЕРВЕРА И КАНАЛА (ДЛЯ БОТОВ)
    # ==========================
    def _on_pick_guild_channel_click(self):
        token = self.token_entry.get().strip()
        if not token:
            self.target_info_lbl.configure(
                text="⚠️ Сначала укажите токен или нажмите «⚡ Авто-захват токена»!",
                text_color=COLOR_WARNING
            )
            self.log_message("Ошибка: токен пуст. Авторизуйтесь, чтобы загрузить серверы.", "error")
            return

        self.pick_guild_btn.configure(state="disabled", text="⏳ Загрузка серверов...")

        def run_fetch():
            sender = DiscordSender(token, self.log_message)
            ok, guilds, msg = sender.get_guilds_and_channels()
            def update_ui():
                self.pick_guild_btn.configure(state="normal", text="🏰 СЕРВЕРЫ И КАНАЛЫ (ДЛЯ БОТОВ)")
                if ok and guilds:
                    self.cached_guilds = guilds
                    self._show_guilds_modal(guilds)
                else:
                    self.target_info_lbl.configure(text=f"⚠️ {msg}", text_color=COLOR_WARNING)
                    self.log_message(f"Не удалось загрузить серверы: {msg}", "error")
            self.after(0, update_ui)

        threading.Thread(target=run_fetch, daemon=True).start()

    def _show_guilds_modal(self, guilds: List[dict]):
        dialog = ctk.CTkToplevel(self)
        dialog.title("Выберите сервер и текстовый канал с ботом")
        dialog.geometry("640x620")
        dialog.minsize(540, 500)
        dialog.transient(self)
        dialog.grab_set()

        top_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        top_frame.pack(fill="x", padx=20, pady=(15, 8))

        lbl = ctk.CTkLabel(
            top_frame,
            text=f"🏰 Выберите канал на сервере (доступно: {len(guilds)})",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=COLOR_TEXT_MAIN
        )
        lbl.pack(side="left")

        search_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        search_frame.pack(fill="x", padx=20, pady=(0, 10))

        search_entry = ctk.CTkEntry(
            search_frame,
            placeholder_text="🔍 Поиск по названию сервера или канала...",
            height=38,
            font=ctk.CTkFont(size=13)
        )
        search_entry.pack(fill="x")

        scroll = ctk.CTkScrollableFrame(dialog, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=15, pady=5)

        def render_guilds(filtered: List[dict]):
            for widget in scroll.winfo_children():
                widget.destroy()

            if not filtered:
                no_res = ctk.CTkLabel(scroll, text="Ничего не найдено", font=ctk.CTkFont(size=13), text_color=COLOR_TEXT_MUTED)
                no_res.pack(pady=20)
                return

            for g in filtered:
                channels = g.get("channels", [])
                if not channels:
                    continue

                g_card = ctk.CTkFrame(scroll, fg_color=COLOR_CARD, corner_radius=10)
                g_card.pack(fill="x", pady=6, padx=5)

                g_header = ctk.CTkLabel(
                    g_card,
                    text=f"🏰 {g['name']} ({len(channels)} каналов)",
                    font=ctk.CTkFont(size=14, weight="bold"),
                    text_color="#FEE75C"
                )
                g_header.pack(anchor="w", padx=12, pady=(10, 6))

                for ch in channels:
                    ch_row = ctk.CTkFrame(g_card, fg_color="#26282C", corner_radius=6)
                    ch_row.pack(fill="x", padx=10, pady=3)
                    ch_row.grid_columnconfigure(0, weight=1)

                    ch_title = ctk.CTkLabel(
                        ch_row,
                        text=f"#{ch['name']}",
                        font=ctk.CTkFont(size=13, weight="bold"),
                        text_color="#57F287"
                    )
                    ch_title.grid(row=0, column=0, sticky="w", padx=10, pady=(6, 2))

                    ch_sub = ctk.CTkLabel(
                        ch_row,
                        text=f"ID: {ch['id']}",
                        font=ctk.CTkFont(size=11),
                        text_color=COLOR_TEXT_MUTED
                    )
                    ch_sub.grid(row=1, column=0, sticky="w", padx=10, pady=(0, 6))

                    sel_btn = ctk.CTkButton(
                        ch_row,
                        text="Выбрать канал",
                        width=110,
                        height=30,
                        fg_color=COLOR_ACCENT,
                        hover_color=COLOR_ACCENT_HOVER,
                        command=lambda c=ch, gn=g['name']: [self._apply_channel_target(c, gn), dialog.destroy()]
                    )
                    sel_btn.grid(row=0, column=1, rowspan=2, padx=10, pady=6)

        render_guilds(guilds)

        def on_search_change(*args):
            q = search_entry.get().strip().lower()
            if not q:
                render_guilds(guilds)
            else:
                filtered_guilds = []
                for g in guilds:
                    g_matches = q in g.get("name", "").lower()
                    matching_channels = [c for c in g.get("channels", []) if q in c.get("name", "").lower() or q in c.get("id", "").lower()]
                    if g_matches or matching_channels:
                        filtered_guilds.append({
                            "id": g["id"],
                            "name": g["name"],
                            "channels": matching_channels if not g_matches else g["channels"]
                        })
                render_guilds(filtered_guilds)

        search_entry.bind("<KeyRelease>", on_search_change)

        close_btn = ctk.CTkButton(
            dialog,
            text="Закрыть",
            fg_color=COLOR_CARD_HOVER,
            hover_color="#4E5058",
            height=34,
            command=dialog.destroy
        )
        close_btn.pack(pady=(5, 15))

    def _apply_channel_target(self, ch: dict, guild_name: str):
        cid = ch["id"]
        cname = ch["name"]

        self.target_id_entry.delete(0, "end")
        self.target_id_entry.insert(0, cid)
        self.target_type_var.set("channel_id")
        self._on_target_type_change()

        self.target_info_lbl.configure(
            text=f"🎯 Выбран канал сервера: [{guild_name}] #{cname} (ID: {cid})",
            text_color=COLOR_SUCCESS
        )
        self.log_message(f"Выбран канал сервера: [{guild_name}] #{cname} (ID: {cid})", "success")

        cfg = self._get_current_gui_config()
        save_config(cfg)

    # ==========================
    # ВЫБОР ДРУГА ИЗ СПИСКА
    # ==========================
    def _on_pick_friend_click(self):
        token = self.token_entry.get().strip()
        if not token:
            self.target_info_lbl.configure(
                text="⚠️ Сначала укажите токен или нажмите «⚡ Авто-захват токена»!",
                text_color=COLOR_WARNING
            )
            self.log_message("Ошибка: токен пуст. Авторизуйтесь, чтобы загрузить список друзей.", "error")
            return

        self.pick_friend_btn.configure(state="disabled", text="⏳ Загрузка...")

        def run_fetch():
            sender = DiscordSender(token, self.log_message)
            ok, contacts, msg = sender.get_friends_and_dms()
            def update_ui():
                self.pick_friend_btn.configure(state="normal", text="👥 ДРУЗЬЯ (ЛС)")
                if ok and contacts:
                    self.cached_contacts = contacts
                    self._show_friend_picker_modal(contacts)
                else:
                    self.target_info_lbl.configure(text=f"⚠️ {msg}", text_color=COLOR_WARNING)
                    self.log_message(f"Не удалось загрузить контакты: {msg}", "error")
            self.after(0, update_ui)

        threading.Thread(target=run_fetch, daemon=True).start()

    def _show_friend_picker_modal(self, contacts: List[dict]):
        dialog = ctk.CTkToplevel(self)
        dialog.title("Выберите друга или личный чат Discord")
        dialog.geometry("580x560")
        dialog.minsize(500, 450)
        dialog.transient(self)
        dialog.grab_set()

        top_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        top_frame.pack(fill="x", padx=20, pady=(15, 8))

        lbl = ctk.CTkLabel(
            top_frame,
            text=f"👥 Выберите адресата (найдено: {len(contacts)})",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=COLOR_TEXT_MAIN
        )
        lbl.pack(side="left")

        search_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        search_frame.pack(fill="x", padx=20, pady=(0, 10))

        search_entry = ctk.CTkEntry(
            search_frame,
            placeholder_text="🔍 Поиск по нику или имени...",
            height=38,
            font=ctk.CTkFont(size=13)
        )
        search_entry.pack(fill="x")

        scroll = ctk.CTkScrollableFrame(dialog, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=15, pady=5)

        def render_contacts(filtered: List[dict]):
            for widget in scroll.winfo_children():
                widget.destroy()

            if not filtered:
                no_res = ctk.CTkLabel(scroll, text="Никого не найдено", font=ctk.CTkFont(size=13), text_color=COLOR_TEXT_MUTED)
                no_res.pack(pady=20)
                return

            for contact in filtered:
                card = ctk.CTkFrame(scroll, fg_color=COLOR_CARD, corner_radius=10)
                card.pack(fill="x", pady=4, padx=5)
                card.grid_columnconfigure(1, weight=1)

                is_friend = contact.get("is_friend", False)
                is_group = contact.get("is_group", False)

                icon_text = "👥" if is_group else ("⭐" if is_friend else "💬")
                icon_lbl = ctk.CTkLabel(card, text=icon_text, font=ctk.CTkFont(size=18))
                icon_lbl.grid(row=0, column=0, rowspan=2, padx=(12, 8), pady=8)

                name = contact["global_name"]
                uname = contact["username"]
                uid = contact["user_id"]

                title_txt = f"{name} (@{uname})" if not is_group else name
                badge = " [Друг]" if is_friend else (" [Группа]" if is_group else " [Чат]")

                title_l = ctk.CTkLabel(
                    card,
                    text=title_txt + badge,
                    font=ctk.CTkFont(size=13, weight="bold"),
                    text_color=COLOR_TEXT_MAIN
                )
                title_l.grid(row=0, column=1, sticky="w", pady=(8, 2))

                sub_l = ctk.CTkLabel(
                    card,
                    text=f"ID: {uid}",
                    font=ctk.CTkFont(size=11),
                    text_color=COLOR_TEXT_MUTED
                )
                sub_l.grid(row=1, column=1, sticky="w", pady=(0, 8))

                select_btn = ctk.CTkButton(
                    card,
                    text="Выбрать",
                    width=90,
                    height=32,
                    fg_color=COLOR_ACCENT,
                    hover_color=COLOR_ACCENT_HOVER,
                    command=lambda c=contact: [self._apply_target_contact(c), dialog.destroy()]
                )
                select_btn.grid(row=0, column=2, rowspan=2, padx=12, pady=8)

        render_contacts(contacts)

        def on_search_change(*args):
            q = search_entry.get().strip().lower()
            if not q:
                render_contacts(contacts)
            else:
                filtered = [
                    c for c in contacts
                    if q in c.get("global_name", "").lower()
                    or q in c.get("username", "").lower()
                    or q in c.get("user_id", "").lower()
                ]
                render_contacts(filtered)

        search_entry.bind("<KeyRelease>", on_search_change)

        close_btn = ctk.CTkButton(
            dialog,
            text="Закрыть",
            fg_color=COLOR_CARD_HOVER,
            hover_color="#4E5058",
            height=34,
            command=dialog.destroy
        )
        close_btn.pack(pady=(5, 15))

    def _apply_target_contact(self, contact: dict):
        uid = contact["user_id"]
        name = contact["global_name"]
        uname = contact["username"]
        is_group = contact.get("is_group", False)

        self.target_id_entry.delete(0, "end")
        self.target_id_entry.insert(0, uid)

        if is_group:
            self.target_type_var.set("channel_id")
            self._on_target_type_change()
            self.target_info_lbl.configure(
                text=f"🎯 Выбран чат: {name} | Channel ID: {uid}",
                text_color=COLOR_SUCCESS
            )
        else:
            self.target_type_var.set("user_id")
            self._on_target_type_change()
            self.target_info_lbl.configure(
                text=f"🎯 Выбран друг (ЛС): {name} (@{uname}) | ID: {uid}",
                text_color=COLOR_SUCCESS
            )

        self.log_message(f"Выбран адресат (ЛС): {name} (@{uname}) [ID: {uid}]", "success")

        cfg = self._get_current_gui_config()
        save_config(cfg)

    # ==========================
    # ОБЗОР СЛЕШ-КОМАНД В КАНАЛЕ
    # ==========================
    def _on_browse_channel_commands_click(self):
        token = self.token_entry.get().strip()
        target_id = self.target_id_entry.get().strip()
        if not token:
            self.log_message("Ошибка: Сначала укажите токен Discord!", "error")
            return
        if not target_id:
            self.log_message("Ошибка: Сначала укажите ID канала или сервера!", "error")
            return

        self.log_message(f"🔍 Сканирование доступных слеш-команд ботов для {target_id}...", "info")

        def run_search():
            sender = DiscordSender(token, self.log_message)
            target_type = self.target_type_var.get()
            ch_id = target_id
            if target_type == "user_id":
                ok_dm, resolved_ch, _ = sender.get_or_create_dm_channel(target_id)
                if ok_dm and resolved_ch:
                    ch_id = resolved_ch

            ok, commands, msg = sender.search_slash_commands(ch_id)

            def update_ui():
                if ok and commands:
                    self._show_commands_modal(commands)
                else:
                    self.log_message(f"Слеш-команды в API: {msg}", "info")
                    default_cmds = [
                        {"name": "waifu", "subcommands": ["random"], "app_name": "Nekotina", "description": "Случайная вайфу от Nekotina (/waifu random)"},
                        {"name": "daily", "subcommands": [], "app_name": "Nekotina", "description": "Получить ежедневную награду (/daily)"},
                        {"name": "profile", "subcommands": [], "app_name": "Nekotina", "description": "Посмотреть профиль (/profile)"},
                        {"name": "timely", "subcommands": [], "app_name": "Nekotina", "description": "Временный бонус каждые 2 часа (/timely)"},
                        {"name": "coin", "subcommands": [], "app_name": "Nekotina", "description": "Подбросить монетку (/coin)"},
                        {"name": "rep", "subcommands": [], "app_name": "Nekotina", "description": "Выдать репутацию (/rep)"},
                    ]
                    self._show_commands_modal(default_cmds, title_extra=" (Популярные команды Nekotina)")

            self.after(0, update_ui)

        threading.Thread(target=run_search, daemon=True).start()

    def _show_commands_modal(self, commands: List[dict], title_extra: str = ""):
        dialog = ctk.CTkToplevel(self)
        dialog.title(f"Слеш-команды ботов{title_extra}")
        dialog.geometry("620x580")
        dialog.minsize(520, 480)
        dialog.transient(self)
        dialog.grab_set()

        top_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        top_frame.pack(fill="x", padx=20, pady=(15, 8))

        lbl = ctk.CTkLabel(
            top_frame,
            text=f"⚡ Доступные команды ботов{title_extra}:",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=COLOR_TEXT_MAIN
        )
        lbl.pack(side="left")

        search_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        search_frame.pack(fill="x", padx=20, pady=(0, 10))

        search_entry = ctk.CTkEntry(
            search_frame,
            placeholder_text="🔍 Поиск команды (например: waifu, daily)...",
            height=38,
            font=ctk.CTkFont(size=13)
        )
        search_entry.pack(fill="x")

        scroll = ctk.CTkScrollableFrame(dialog, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=15, pady=5)

        def render_cmds(filtered: List[dict]):
            for widget in scroll.winfo_children():
                widget.destroy()

            if not filtered:
                no_res = ctk.CTkLabel(scroll, text="Команды не найдены", font=ctk.CTkFont(size=13), text_color=COLOR_TEXT_MUTED)
                no_res.pack(pady=20)
                return

            for cmd in filtered:
                cmd_name = cmd.get("name", "")
                app_name = cmd.get("app_name", "Bot")
                desc = cmd.get("description", "")
                subcommands = cmd.get("subcommands", [])

                if subcommands:
                    for sub in subcommands:
                        full_cmd = f"/{cmd_name} {sub}"
                        self._create_cmd_card(scroll, full_cmd, app_name, desc, dialog)
                else:
                    full_cmd = f"/{cmd_name}"
                    self._create_cmd_card(scroll, full_cmd, app_name, desc, dialog)

        render_cmds(commands)

        def on_search(*args):
            q = search_entry.get().strip().lower().lstrip("/")
            if not q:
                render_cmds(commands)
            else:
                filtered = [
                    c for c in commands
                    if q in c.get("name", "").lower()
                    or q in c.get("app_name", "").lower()
                    or q in c.get("description", "").lower()
                    or any(q in s.lower() for s in c.get("subcommands", []))
                ]
                render_cmds(filtered)

        search_entry.bind("<KeyRelease>", on_search)

        close_btn = ctk.CTkButton(
            dialog,
            text="Закрыть",
            fg_color=COLOR_CARD_HOVER,
            hover_color="#4E5058",
            height=34,
            command=dialog.destroy
        )
        close_btn.pack(pady=(5, 15))

    def _create_cmd_card(self, parent, full_cmd: str, app_name: str, desc: str, dialog):
        card = ctk.CTkFrame(parent, fg_color=COLOR_CARD, corner_radius=10)
        card.pack(fill="x", pady=4, padx=5)
        card.grid_columnconfigure(1, weight=1)

        icon_lbl = ctk.CTkLabel(card, text="🤖", font=ctk.CTkFont(size=18))
        icon_lbl.grid(row=0, column=0, rowspan=2, padx=(12, 8), pady=8)

        title_l = ctk.CTkLabel(
            card,
            text=f"{full_cmd}  [{app_name}]",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color="#57F287"
        )
        title_l.grid(row=0, column=1, sticky="w", pady=(8, 2))

        sub_l = ctk.CTkLabel(
            card,
            text=desc or "Выполнить команду бота",
            font=ctk.CTkFont(size=11),
            text_color=COLOR_TEXT_MUTED
        )
        sub_l.grid(row=1, column=1, sticky="w", pady=(0, 8))

        insert_btn = ctk.CTkButton(
            card,
            text="Вставить",
            width=90,
            height=32,
            fg_color=COLOR_ACCENT,
            hover_color=COLOR_ACCENT_HOVER,
            command=lambda: [self._insert_text_to_messages(full_cmd), dialog.destroy()]
        )
        insert_btn.grid(row=0, column=2, rowspan=2, padx=12, pady=8)

    def _on_check_token_click(self):
        token = self.token_entry.get().strip()
        if not token:
            self.account_info_lbl.configure(text="⚠️ Укажите токен или нажмите «⚡ Авто-захват токена»!", text_color=COLOR_WARNING)
            return

        self.account_info_lbl.configure(text="⏳ Проверка токена...", text_color=COLOR_TEXT_MUTED)
        self.check_token_btn.configure(state="disabled")

        def run_check():
            sender = DiscordSender(token, self.log_message)
            success, user_data, msg = sender.check_token()
            def update_ui():
                self.check_token_btn.configure(state="normal")
                if success and user_data:
                    name = user_data.get("global_name") or user_data.get("username")
                    tag = user_data.get("username")
                    u_id = user_data.get("id")
                    self.account_info_lbl.configure(
                        text=f"✅ Авторизован: {name} (@{tag}) | ID: {u_id}",
                        text_color=COLOR_SUCCESS
                    )
                    self.log_message(f"Токен валиден: {name} (@{tag}) ID: {u_id}", "success")
                    self._preload_friends(token)
                else:
                    self.account_info_lbl.configure(text=f"❌ Ошибка: {msg}", text_color=COLOR_DANGER)
                    self.log_message(f"Ошибка проверки токена: {msg}", "error")
            self.after(0, update_ui)

        threading.Thread(target=run_check, daemon=True).start()

    def _on_preview_msg_click(self):
        raw_msgs = self.messages_textbox.get("1.0", "end-1c").strip().splitlines()
        clean_msgs = [m.strip() for m in raw_msgs if m.strip()]
        if not clean_msgs:
            clean_msgs = FEMBOY_PRESET
        template = random.choice(clean_msgs)
        sample = format_message(template, random.randint(1, 99))
        if self.attach_gif_var.get() and self.favorite_gifs:
            sample = f"{sample}\n{random.choice(self.favorite_gifs)}"
        self.log_message(f"🎲 Пример сгенерированного сообщения с GIF:\n\"{sample}\"", "accent")

    def _on_save_settings_click(self):
        cfg = self._get_current_gui_config()
        if save_config(cfg):
            self.log_message("Все настройки успешно сохранены в config.json", "success")
        else:
            self.log_message("Ошибка сохранения настроек", "error")

    # ==========================
    # УПРАВЛЕНИЕ ОТПРАВКОЙ (СТАРТ/ПАУЗА/СТОП)
    # ==========================
    def _on_start_click(self):
        cfg = self._get_current_gui_config()
        if not cfg["token"]:
            self.log_message("Ошибка: Не указан Discord токен! Нажмите «⚡ Авто-захват токена».", "error")
            self._select_tab("dash")
            return

        if not cfg["target_id"]:
            self.log_message("Ошибка: Не указан адресат/канал! Нажмите «🏰 СЕРВЕРЫ И КАНАЛЫ» или «👥 ДРУЗЬЯ (ЛС)».", "error")
            self._select_tab("dash")
            return

        if not cfg["target_id"].isdigit():
            self.log_message("Ошибка: ID адресата должен состоять только из цифр!", "error")
            return

        save_config(cfg)

        self.is_running = True
        self.is_paused = False
        self.stop_event.clear()
        self.pause_event.set()

        self.start_time = datetime.now()
        self.sent_count = 0
        self.error_count = 0
        self.current_seq_index = 0

        self.start_btn.configure(state="disabled")
        self.pause_btn.configure(state="normal", text="⏸️ ПАУЗА", fg_color=COLOR_WARNING)
        self.stop_btn.configure(state="normal")
        self.status_badge.configure(text="● Выполнение...", text_color=COLOR_SUCCESS)

        self.log_message("▶️ Процесс запущен!", "success")

        self.worker_thread = threading.Thread(target=self._worker_loop, args=(cfg,), daemon=True)
        self.worker_thread.start()

    def _on_pause_click(self):
        if not self.is_running:
            return

        if not self.is_paused:
            self.is_paused = True
            self.pause_event.clear()
            self.pause_btn.configure(text="▶️ ПРОДОЛЖИТЬ", fg_color=COLOR_SUCCESS)
            self.status_badge.configure(text="● На паузе", text_color=COLOR_WARNING)
            self.log_message("⏸️ Приостановлено.", "warning")
        else:
            self.is_paused = False
            self.pause_event.set()
            self.pause_btn.configure(text="⏸️ ПАУЗА", fg_color=COLOR_WARNING)
            self.status_badge.configure(text="● Выполнение...", text_color=COLOR_SUCCESS)
            self.log_message("▶️ Возобновлено.", "success")

    def _on_stop_click(self):
        if not self.is_running:
            return

        self.is_running = False
        self.is_paused = False
        self.stop_event.set()
        self.pause_event.set()

        self.start_btn.configure(state="normal")
        self.pause_btn.configure(state="disabled", text="⏸️ ПАУЗА", fg_color=COLOR_WARNING)
        self.stop_btn.configure(state="disabled")
        self.status_badge.configure(text="● Остановлен", text_color=COLOR_DANGER)
        self.stat_next_lbl.configure(text="След. через: -")

        self.log_message("⏹️ Остановлено пользователем.", "warning")

    # ==========================
    # ФОНОВЫЙ ВОРКЕР ОТПРАВКИ
    # ==========================
    def _worker_loop(self, cfg: dict):
        sender = DiscordSender(cfg["token"], self.log_message)

        self.log_message("Проверка авторизации перед стартом...", "info")
        ok, user_data, msg = sender.check_token()
        if not ok:
            self.log_message(f"Критическая ошибка авторизации: {msg}", "error")
            self.after(0, self._on_stop_click)
            return

        target_type = cfg["target_type"]
        target_id = cfg["target_id"]
        channel_id = target_id

        if target_type == "user_id":
            self.log_message(f"Открытие ЛС с пользователем ID: {target_id}...", "info")
            dm_ok, resolved_ch_id, dm_msg = sender.get_or_create_dm_channel(target_id)
            if not dm_ok or not resolved_ch_id:
                self.log_message(f"Не удалось открыть ЛС с пользователем: {dm_msg}", "error")
                self.after(0, self._on_stop_click)
                return
            channel_id = resolved_ch_id
            self.log_message(f"ЛС канал получен (ID: {channel_id})", "success")

        messages_list = cfg["messages"]
        if not messages_list:
            messages_list = FEMBOY_PRESET

        cmd_mode = cfg.get("command_mode", "slash_only")
        fallback_text = cfg.get("fallback_to_text", True)
        attach_gif = cfg.get("attach_gif", True)
        gif_chance = cfg.get("gif_chance", 100)
        fav_gifs = cfg.get("favorite_gifs") or list(DEFAULT_FAVORITE_GIFS)

        # Установка кастомного статуса Discord с автором (Aharen7san) и пресетом
        discord_status_enabled = cfg.get("discord_status_enabled", True)
        creator_nick = cfg.get("discord_creator_nick", "Aharen7san")
        preset_name = cfg.get("discord_status_preset", "Фембой")

        if discord_status_enabled:
            initial_status = f"🎀 AutoMsg by {creator_nick} | Пресет: {preset_name} • #1"
            if sender.set_custom_status(initial_status, "🎀"):
                self.log_message(f"👑 Установлен статус Discord: \"{initial_status}\"", "success")

        while not self.stop_event.is_set():
            self.pause_event.wait()
            if self.stop_event.is_set():
                break

            if cfg["limit_mode"] == "count" and self.sent_count >= cfg["max_messages"]:
                self.log_message(f"🎉 Достигнут лимит выполнений ({cfg['max_messages']}). Завершение.", "success")
                break

            if cfg["message_mode"] == "random":
                template = random.choice(messages_list)
            else:
                template = messages_list[self.current_seq_index % len(messages_list)]
                self.current_seq_index += 1

            current_msg_num = self.sent_count + 1
            formatted_text = format_message(template, current_msg_num)

            # Прикрепление случайной GIF из избранного
            has_attached_gif = False
            if attach_gif and not formatted_text.startswith("/") and fav_gifs:
                if random.randint(1, 100) <= gif_chance:
                    chosen_gif = random.choice(fav_gifs).strip()
                    if chosen_gif:
                        formatted_text = f"{formatted_text}\n{chosen_gif}"
                        has_attached_gif = True

            if cfg.get("use_typing", True) and not formatted_text.startswith("/"):
                sender.send_typing(channel_id)
                time.sleep(min(2.0, max(0.5, len(formatted_text) * 0.05)))

            if self.stop_event.is_set():
                break

            success, status_msg, retry_after = sender.send_message_or_command(
                channel_id=channel_id,
                content=formatted_text,
                tts=cfg.get("tts", False),
                command_mode=cmd_mode,
                fallback_to_text=fallback_text
            )

            if success:
                self.sent_count += 1
                if formatted_text.startswith("/"):
                    self.log_message(f"[{self.sent_count}] ⚡ Нативная слеш-команда: \"{formatted_text}\" выполнена!", "success")
                else:
                    gif_tag = " (+🖼️ GIF)" if has_attached_gif else ""
                    self.log_message(f"[{self.sent_count}] Отправлено: \"{formatted_text.splitlines()[0]}\"{gif_tag}", "success")

                # Обновление статуса Discord
                if discord_status_enabled:
                    cur_status = f"🎀 AutoMsg by {creator_nick} | Пресет: {preset_name} • #{self.sent_count}"
                    sender.set_custom_status(cur_status, "🎀")

            else:
                self.error_count += 1
                self.log_message(f"Ошибка выполнения: {status_msg}", "error")

                if retry_after:
                    wait_time = retry_after + 1.0
                    self.log_message(f"⏳ Ожидание снятия рейтлимита: {wait_time:.1f} сек...", "warning")
                    self._sleep_with_stop_check(wait_time)
                    continue

            if cfg["interval_mode"] == "fixed":
                delay = cfg["fixed_interval"]
            else:
                d_min = min(cfg["random_interval_min"], cfg["random_interval_max"])
                d_max = max(cfg["random_interval_min"], cfg["random_interval_max"])
                delay = random.uniform(d_min, d_max)

            self._sleep_with_stop_check(delay)

        # Очистка кастомного статуса после остановки
        if discord_status_enabled:
            sender.clear_custom_status()
            self.log_message("Статус Discord сброшен после остановки.", "info")

        self.after(0, self._on_stop_click)

    def _sleep_with_stop_check(self, seconds: float):
        start = time.time()
        while time.time() - start < seconds:
            if self.stop_event.is_set():
                break
            self.pause_event.wait()

            remaining = max(0.0, seconds - (time.time() - start))
            self.after(0, lambda r=remaining: self.stat_next_lbl.configure(text=f"След. через: {r:.1f}с"))
            time.sleep(0.1)

    def _update_timer_loop(self):
        if self.is_running and self.start_time:
            elapsed = datetime.now() - self.start_time
            seconds = int(elapsed.total_seconds())
            hours, remainder = divmod(seconds, 3600)
            minutes, sec = divmod(remainder, 60)
            self.stat_time_lbl.configure(text=f"Время: {hours:02d}:{minutes:02d}:{sec:02d}")

        self.stat_sent_lbl.configure(text=f"Выполнено: {self.sent_count}")
        self.stat_err_lbl.configure(text=f"Ошибок: {self.error_count}")

        self.after(500, self._update_timer_loop)

    def _on_close(self):
        if self.minimize_tray_var.get():
            self.minimize_to_tray()
        else:
            self._force_quit()

    def _force_quit(self):
        """Полное закрытие приложения."""
        if self.is_running:
            self._on_stop_click()
        if self.tray_icon:
            try:
                self.tray_icon.stop()
            except Exception:
                pass
        cfg = self._get_current_gui_config()
        save_config(cfg)
        self.destroy()
        sys.exit(0)


def launch_app():
    app = DiscordAutoMessengerApp()
    app.mainloop()


if __name__ == "__main__":
    launch_app()
