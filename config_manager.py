"""
Модуль управления конфигурацией приложения.
Сохраняет и загружает настройки в файл config.json.
"""

import json
import os
from presets import DEFAULT_FAVORITE_GIFS

DEFAULT_CONFIG = {
    "token": "",
    "target_type": "user_id",  # "user_id" или "channel_id"
    "target_id": "",
    "messages": [
        "Nya~ {приветик|хай|куки}! Няшка передает привет #{count} (✿◠‿◠)",
        "UwU {сенпай|братик|дружище}, ты сегодня такой милашка~ {time}",
        "( > ‿ < ) Мяу! Напоминаю, что ты самый лучший #{count}!"
    ],
    "message_mode": "random",  # "random" или "sequential"
    "single_message": "Привет! Это сообщение #{count}",
    "command_mode": "slash_only",  # "slash_only", "auto", "text_only"
    "fallback_to_text": True,
    "attach_gif": True,  # прикреплять ли рандомную GIF из избранного
    "gif_chance": 100,  # шанс прикрепления GIF в процентах (1-100)
    "favorite_gifs": DEFAULT_FAVORITE_GIFS,
    "use_spintax": True,
    "use_typing": True,
    "typing_duration": 2.0,
    "interval_mode": "random",  # "fixed" или "random"
    "fixed_interval": 15.0,
    "random_interval_min": 15.0,
    "random_interval_max": 30.0,
    "limit_mode": "infinite",  # "infinite" или "count"
    "max_messages": 50,
    "tts": False,
    "save_token_on_exit": True,
    # Кастомный статус Discord и авторство
    "discord_status_enabled": True,
    "discord_status_preset": "Фембой",
    "discord_creator_nick": "Aharen7san",
    "discord_status_template": "🎀 AutoMsg by Aharen7san | Пресет: {preset} • #{count}",
    # Скрытие в системный трей
    "minimize_to_tray_on_close": True,
    "minimize_to_tray": True
}

CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")


def load_config() -> dict:
    """Загрузить настройки из config.json или вернуть дефолтные."""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                config = DEFAULT_CONFIG.copy()
                config.update(data)
                if not config.get("favorite_gifs"):
                    config["favorite_gifs"] = DEFAULT_FAVORITE_GIFS
                return config
        except Exception as e:
            print(f"[Config] Ошибка чтения config.json: {e}")
            return DEFAULT_CONFIG.copy()
    return DEFAULT_CONFIG.copy()


def save_config(config: dict) -> bool:
    """Сохранить текущие настройки в config.json."""
    try:
        data_to_save = config.copy()
        if not data_to_save.get("save_token_on_exit", True):
            data_to_save["token"] = ""
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(data_to_save, f, indent=4, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"[Config] Ошибка сохранения config.json: {e}")
        return False
