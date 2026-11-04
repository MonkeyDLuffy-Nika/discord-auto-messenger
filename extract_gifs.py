import base64
import glob
import json
import os
import re
import sys
import requests
from token_extractor import scan_and_extract_tokens

sys.stdout.reconfigure(encoding="utf-8")

all_found_gifs = set()

# 1. Сканируем Discord API с токенами пользователя
accounts = scan_and_extract_tokens()
print(f"Найдено аккаунтов: {len(accounts)}")

for acc in accounts:
    token = acc["token"]
    uid = acc["id"]
    name = acc["global_name"]
    print(f"\n--- Сканирование аккаунта: {name} (ID: {uid}) ---")
    headers = {
        "Authorization": token,
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "*/*"
    }

    # /gifs/saved
    try:
        r = requests.get("https://discord.com/api/v9/gifs/saved", headers=headers, timeout=8)
        print(f"GET /gifs/saved -> HTTP {r.status_code}")
        if r.status_code == 200:
            data = r.json()
            for item in data:
                url = item.get("url") or item.get("src") or item.get("gif_url")
                if url:
                    all_found_gifs.add(url)
                    print(f"  [Saved GIF] {url}")
    except Exception as e:
        print(f"Err /gifs/saved: {e}")

    # /users/@me/settings-proto/1 и /2
    for proto_id in [1, 2]:
        try:
            r = requests.get(f"https://discord.com/api/v9/users/@me/settings-proto/{proto_id}", headers=headers, timeout=8)
            print(f"GET /users/@me/settings-proto/{proto_id} -> HTTP {r.status_code}")
            if r.status_code == 200:
                b64 = r.json().get("settings")
                if b64:
                    raw = base64.b64decode(b64)
                    matches = re.findall(rb"https?://[a-zA-Z0-9\.\_\-\/\%\?\=\&]+\.(?:gif|mp4|webm)|https?://(?:tenor\.com|giphy\.com|c\.tenor\.com|media\.discordapp\.net)/[^\s\"\'\<\>\\\{\}\x00-\x1f\x7f-\xff]+", raw)
                    for m in matches:
                        url_str = m.decode("latin-1", errors="ignore")
                        all_found_gifs.add(url_str)
                        print(f"  [Proto {proto_id} GIF] {url_str}")
        except Exception as e:
            print(f"Err proto/{proto_id}: {e}")

# 2. Сканируем локальные файлы Discord LevelDB на диске
appdata = os.getenv("APPDATA", "")
localappdata = os.getenv("LOCALAPPDATA", "")

discord_paths = [
    os.path.join(appdata, "discord", "Local Storage", "leveldb"),
    os.path.join(appdata, "discordcanary", "Local Storage", "leveldb"),
    os.path.join(appdata, "discordptb", "Local Storage", "leveldb"),
    os.path.join(appdata, "discord", "IndexedDB"),
    os.path.join(appdata, "Opera Software", "Opera GX Stable", "Local Storage", "leveldb"),
    os.path.join(localappdata, "Google", "Chrome", "User Data", "Default", "Local Storage", "leveldb"),
    os.path.join(localappdata, "Yandex", "YandexBrowser", "User Data", "Default", "Local Storage", "leveldb"),
]

print("\n--- Сканирование локальных хранилищ LevelDB на ПК ---")
for p in discord_paths:
    if os.path.exists(p):
        for fpath in glob.glob(os.path.join(p, "*.ldb")) + glob.glob(os.path.join(p, "*.log")):
            try:
                with open(fpath, "rb") as f:
                    content = f.read()
                    matches = re.findall(rb"https?://(?:tenor\.com/view/[a-zA-Z0-9\-_]+|media\.tenor\.com/[a-zA-Z0-9\-_/]+\.gif|media\.discordapp\.net/attachments/[a-zA-Z0-9\-_/]+\.gif|c\.tenor\.com/[a-zA-Z0-9\-_/]+\.gif)", content)
                    for m in matches:
                        url_str = m.decode("latin-1", errors="ignore")
                        all_found_gifs.add(url_str)
                        print(f"  [LevelDB GIF] {url_str}")
            except Exception:
                pass

print(f"\nИТОГО НАЙДЕНО ИЗБРАННЫХ GIF: {len(all_found_gifs)}")
for g in sorted(all_found_gifs):
    print(" -", g)

# Сохраняем найденные GIF в json
with open("extracted_gifs.json", "w", encoding="utf-8") as f:
    json.dump(list(all_found_gifs), f, indent=4, ensure_ascii=False)
