# ⚡ Discord Auto-Messenger Desktop App

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python" />
  <img src="https://img.shields.io/badge/GUI-CustomTkinter-blue?style=for-the-badge" alt="GUI" />
  <img src="https://img.shields.io/badge/Discord-Interactions_API-5865F2?style=for-the-badge&logo=discord&logoColor=white" alt="API" />
  <img src="https://img.shields.io/badge/License-MIT-yellow?style=for-the-badge" alt="License" />
</p>

---

## 🇬🇧 English

A modern, standalone desktop client for automated Discord messaging, interactive Slash-command automation (Nekotina, Mudae, etc.), and Spintax template cycling.

### ✨ Key Features

1. **🐱 Native Bot Slash Commands (`Interactions API`):**
   - Automatically detects strings starting with `/` (e.g. `/waifu random`, `/daily`, `/profile`, `/coin`) and triggers native bot slash commands directly via Discord's Gateway / Interactions endpoint.
   - Quick preset buttons for popular bots.
   - One-click channel command scanner (`🔍 Scan Channel Commands`).

2. **⚡ Automatic Local Token Extraction:**
   - Auto-discovers and decrypts Discord user tokens from installed Discord clients (Stable, PTB, Canary) and Chromium-based browsers (Chrome, Edge, Opera GX, Brave, Yandex).

3. **👥 Interactive Dialog & Friend Picker:**
   - Live searchable friend list and recent DM / group chat selector.

4. **🎲 Smart Spintax & Dynamic Formatting:**
   - Spintax syntax support: `{Hello|Hi|Hey} {friend|buddy}, how are you?`
   - Dynamic interpolation tags: `{count}`, `{time}`, `{date}`, `{random}`.
   - Live message preview generator.

5. **🛡️ Anti-Detection & Rate-Limit Safeguards:**
   - Configurable randomized intervals (e.g. $15 - 30\text{ s}$).
   - Human-like typing simulation (`typing...` status).
   - Automatic HTTP 429 backoff handling.

### 🚀 Getting Started

1. Clone or download the repository.
2. Install dependencies:
   ```bash
   pip install customtkinter requests cryptography pystray pillow
   ```
3. Copy `config.example.json` to `config.json` and set your preferences (or use the GUI to auto-extract token).
4. Run the app:
   ```bash
   python main.py
   # Or run via run.bat
   ```

---

## 🇷🇺 Русский

Современное десктопное приложение на Python (CustomTkinter) для автоматизированной отправки сообщений, выполнения нативных слэш-команд ботов (Nekotina, Mudae и др.) и циклической отправки сообщений по шаблонам Spintax.

### ✨ Основные возможности

1. **🐱 Нативные слеш-команды ботов (Interactions API):**
   - Автоматически распознает строки со слэшем (`/waifu random`, `/daily`, `/profile`, `/timely`) и отправляет их как настоящие интерактивные команды Discord.
   - Быстрые пресеты для популярных игровых ботов.
   - Сканирование команд ботов в выбранном канале в один клик.

2. **⚡ Автоматический захват токена:**
   - Автоматически извлекает и расшифровывает токен из установленного Discord (Desktop, Canary, PTB) или браузеров (Chrome, Opera GX, Edge, Yandex, Brave).

3. **👥 Выбор друзей и чатов:**
   - Загрузка списка друзей и недавних диалогов со строкой живого поиска.

4. **🎲 Spintax и динамические шаблоны:**
   - Синтаксис рандомизации: `{Привет|Хай|Куки} {дружище|бро|друг}!`
   - Переменные: `{count}`, `{time}`, `{date}`, `{random}`.
   - Кнопка предпросмотра рандомизированных сообщений.

5. **🛡️ Защита от банов и рейтлимитов:**
   - Настройка случайных интервалов отправки (например: $15 - 30$ секунд).
   - Имитация набора текста (статус «печатает...»).
   - Автоматический кулдаун при ошибках 429 (Rate Limit).

### 🚀 Быстрый запуск

1. Склонируйте репозиторий.
2. Установите зависимости:
   ```bash
   pip install customtkinter requests cryptography pystray pillow
   ```
3. Запустите через `run.bat` или командой:
   ```bash
   python main.py
   ```
