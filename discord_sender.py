"""
Модуль для отправки сообщений и выполнения нативных Slash-команд (Nekotina /waifu random, Mudae и др.)
в Discord через REST API и Interactions API.
"""

import json
import random
import re
import time
import uuid
from datetime import datetime
from typing import Callable, Dict, List, Optional, Tuple
import requests

DISCORD_API_BASE = "https://discord.com/api/v9"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)


def get_base_headers(token: str) -> dict:
    """Формирует базовые заголовки авторизации Discord."""
    clean_token = token.strip().strip('"').strip("'")
    return {
        "Authorization": clean_token,
        "User-Agent": USER_AGENT,
        "Accept": "*/*",
        "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
        "Origin": "https://discord.com",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
    }


def generate_nonce() -> str:
    """Генерирует Discord snowflake nonce."""
    return str((int(time.time() * 1000) - 1420070400000) << 22)


def generate_session_id() -> str:
    """Генерирует 32-значный hex session_id для Discord interactions."""
    return uuid.uuid4().hex


def parse_spintax(text: str) -> str:
    """
    Обрабатывает Spintax шаблоны вида {вариант1|вариант2|вариант3}.
    Поддерживает вложенность.
    """
    pattern = re.compile(r"\{([^{}]+)\}")
    while True:
        match = pattern.search(text)
        if not match:
            break
        choices = match.group(1).split("|")
        chosen = random.choice(choices)
        text = text[:match.start()] + chosen + text[match.end():]
    return text


def format_message(template: str, count: int) -> str:
    """
    Форматирует шаблон сообщения:
    1. Заменяет плейсхолдеры {count}, {time}, {date}, {random}.
    2. Применяет Spintax {слово1|слово2}.
    """
    now = datetime.now()
    replacements = {
        "{count}": str(count),
        "{time}": now.strftime("%H:%M:%S"),
        "{date}": now.strftime("%d.%m.%Y"),
        "{random}": str(random.randint(1000, 9999)),
        "{rand}": str(random.randint(10, 99)),
    }

    result = template
    for key, val in replacements.items():
        result = result.replace(key, val)

    # Обрабатываем Spintax
    result = parse_spintax(result)
    return result


class DiscordSender:
    def __init__(self, token: str, log_callback: Optional[Callable[[str, str], None]] = None):
        """
        :param token: Токен пользователя Discord
        :param log_callback: Функция для вывода логов вида callback(message, level)
        """
        self.token = token.strip().strip('"').strip("'")
        self.log_callback = log_callback or (lambda msg, lvl: print(f"[{lvl.upper()}] {msg}"))
        self._cached_commands: Dict[str, List[dict]] = {}
        self._cached_channel_info: Dict[str, dict] = {}

    def log(self, message: str, level: str = "info"):
        self.log_callback(message, level)

    def check_token(self) -> Tuple[bool, Optional[dict], str]:
        """
        Проверяет валидность токена и возвращает информацию о пользователе.
        Возвращает (success, user_data, error_message).
        """
        if not self.token:
            return False, None, "Токен пуст. Укажите Discord токен."

        url = f"{DISCORD_API_BASE}/users/@me"
        headers = get_base_headers(self.token)
        headers["Content-Type"] = "application/json"
        try:
            resp = requests.get(url, headers=headers, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                username = data.get("username", "Unknown")
                discriminator = data.get("discriminator", "0")
                user_id = data.get("id", "")
                global_name = data.get("global_name") or username
                tag = f"{username}#{discriminator}" if discriminator != "0" else username
                return True, data, f"Авторизован: {global_name} (@{tag}, ID: {user_id})"
            elif resp.status_code == 401:
                return False, None, "Неверный токен (Код 401 Unauthorized)."
            else:
                return False, None, f"Ошибка проверки токена: HTTP {resp.status_code} - {resp.text}"
        except Exception as e:
            return False, None, f"Сетевая ошибка при проверке токена: {e}"

    def get_friends_and_dms(self) -> Tuple[bool, List[dict], str]:
        """
        Получает список друзей и открытых личных чатов (DM).
        """
        if not self.token:
            return False, [], "Токен пуст."

        contacts: Dict[str, dict] = {}
        headers = get_base_headers(self.token)
        headers["Content-Type"] = "application/json"

        # 1. Получаем список друзей из /users/@me/relationships
        try:
            rel_url = f"{DISCORD_API_BASE}/users/@me/relationships"
            r_rel = requests.get(rel_url, headers=headers, timeout=10)
            if r_rel.status_code == 200:
                for item in r_rel.json():
                    if item.get("type") == 1:  # 1 = Friend
                        u = item.get("user", {})
                        u_id = u.get("id")
                        if u_id:
                            username = u.get("username", "Unknown")
                            global_name = u.get("global_name") or u.get("display_name") or username
                            contacts[u_id] = {
                                "user_id": u_id,
                                "username": username,
                                "global_name": global_name,
                                "avatar": u.get("avatar"),
                                "is_friend": True,
                                "dm_channel_id": None,
                                "is_group": False
                            }
        except Exception as e:
            self.log(f"Не удалось получить relationships: {e}", "warning")

        # 2. Получаем список открытых DM чатов из /users/@me/channels
        try:
            ch_url = f"{DISCORD_API_BASE}/users/@me/channels"
            r_ch = requests.get(ch_url, headers=headers, timeout=10)
            if r_ch.status_code == 200:
                for ch in r_ch.json():
                    ch_id = ch.get("id")
                    ch_type = ch.get("type")  # 1 = DM, 3 = Group DM
                    recipients = ch.get("recipients", [])
                    if ch_type == 1 and recipients:
                        u = recipients[0]
                        u_id = u.get("id")
                        if u_id:
                            username = u.get("username", "Unknown")
                            global_name = u.get("global_name") or u.get("display_name") or username
                            if u_id in contacts:
                                contacts[u_id]["dm_channel_id"] = ch_id
                            else:
                                contacts[u_id] = {
                                    "user_id": u_id,
                                    "username": username,
                                    "global_name": global_name,
                                    "avatar": u.get("avatar"),
                                    "is_friend": False,
                                    "dm_channel_id": ch_id,
                                    "is_group": False
                                }
                    elif ch_type == 3:
                        recip_names = [r.get("global_name") or r.get("username", "") for r in recipients[:3]]
                        name = ch.get("name") or (", ".join(recip_names) if recip_names else "Групповой чат")
                        contacts[f"group_{ch_id}"] = {
                            "user_id": ch_id,
                            "username": f"group_{ch_id}",
                            "global_name": f"👥 {name}",
                            "avatar": ch.get("icon"),
                            "is_friend": False,
                            "dm_channel_id": ch_id,
                            "is_group": True
                        }
        except Exception as e:
            self.log(f"Не удалось получить DM каналы: {e}", "warning")

        contact_list = list(contacts.values())
        contact_list.sort(key=lambda x: (not x.get("is_friend", False), x.get("global_name", "").lower()))

        if not contact_list:
            return False, [], "Список друзей и чатов пуст или не удалось загрузить."
        return True, contact_list, f"Найдено контактов: {len(contact_list)}"

    def get_guilds_and_channels(self) -> Tuple[bool, List[dict], str]:
        """
        Получает список всех серверов пользователя и их текстовых каналов.
        Возвращает (success, guilds_list, message).
        """
        if not self.token:
            return False, [], "Токен пуст."

        headers = get_base_headers(self.token)
        headers["Content-Type"] = "application/json"

        url_guilds = f"{DISCORD_API_BASE}/users/@me/guilds"
        try:
            resp = requests.get(url_guilds, headers=headers, timeout=10)
            if resp.status_code != 200:
                return False, [], f"Ошибка загрузки серверов: HTTP {resp.status_code}"

            guilds_data = resp.json()
            guilds_result = []

            for g in guilds_data:
                g_id = g.get("id")
                g_name = g.get("name")
                g_icon = g.get("icon")

                # Получаем каналы сервера
                url_ch = f"{DISCORD_API_BASE}/guilds/{g_id}/channels"
                try:
                    resp_ch = requests.get(url_ch, headers=headers, timeout=8)
                    channels = []
                    if resp_ch.status_code == 200:
                        for ch in resp_ch.json():
                            # type 0 = GUILD_TEXT, type 5 = GUILD_ANNOUNCEMENT
                            if ch.get("type") in (0, 5):
                                channels.append({
                                    "id": ch.get("id"),
                                    "name": ch.get("name"),
                                    "type": ch.get("type"),
                                    "guild_id": g_id,
                                    "guild_name": g_name
                                })
                    # Сортируем каналы по имени
                    channels.sort(key=lambda x: x["name"].lower())
                    guilds_result.append({
                        "id": g_id,
                        "name": g_name,
                        "icon": g_icon,
                        "channels": channels
                    })
                except Exception:
                    continue

            return True, guilds_result, f"Загружено серверов: {len(guilds_result)}"
        except Exception as e:
            return False, [], f"Сетевая ошибка при загрузке серверов: {e}"

    def get_or_create_dm_channel(self, recipient_user_id: str) -> Tuple[bool, Optional[str], str]:
        """
        Создает или возвращает существующий DM канал с пользователем по его User ID.
        """
        clean_user_id = recipient_user_id.strip()
        if not clean_user_id.isdigit():
            return False, None, f"ID пользователя должен состоять только из цифр. Получено: '{clean_user_id}'"

        url = f"{DISCORD_API_BASE}/users/@me/channels"
        headers = get_base_headers(self.token)
        headers["Content-Type"] = "application/json"
        payload = {"recipient_id": clean_user_id}

        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=10)
            if resp.status_code in (200, 201):
                channel_data = resp.json()
                channel_id = channel_data.get("id")
                return True, channel_id, f"Канал ЛС найден/создан: {channel_id}"
            elif resp.status_code == 400:
                return False, None, f"Не удалось открыть ЛС с пользователем {clean_user_id} (Код 400: возможно, неверный ID)."
            elif resp.status_code == 403:
                return False, None, f"Доступ запрещен (Код 403: ЛС закрыты настройками приватности или вы заблокированы)."
            elif resp.status_code == 429:
                retry_after = resp.json().get("retry_after", 5)
                return False, None, f"Рейтлимит на создание ЛС. Подождите {retry_after} сек."
            else:
                return False, None, f"Ошибка создания ЛС: HTTP {resp.status_code} - {resp.text}"
        except Exception as e:
            return False, None, f"Сетевая ошибка при открытии ЛС: {e}"

    def get_channel_info(self, channel_id: str) -> Optional[dict]:
        """Получает и кэширует информацию о канале (включая guild_id и тип канала)."""
        if channel_id in self._cached_channel_info:
            return self._cached_channel_info[channel_id]

        url = f"{DISCORD_API_BASE}/channels/{channel_id}"
        headers = get_base_headers(self.token)
        headers["Content-Type"] = "application/json"
        try:
            resp = requests.get(url, headers=headers, timeout=8)
            if resp.status_code == 200:
                data = resp.json()
                self._cached_channel_info[channel_id] = data
                return data
        except Exception:
            pass
        return None

    def search_slash_commands(self, channel_id: str, query: str = "") -> Tuple[bool, List[dict], str]:
        """
        Поиск доступных слеш-команд в канале через Discord API.
        """
        clean_query = query.strip().lstrip("/")
        headers = get_base_headers(self.token)
        headers["Content-Type"] = "application/json"

        url = f"{DISCORD_API_BASE}/channels/{channel_id}/application-commands/search"
        params = {"type": 1, "include_applications": "true"}
        if clean_query:
            params["query"] = clean_query

        commands = []
        applications = {}

        try:
            resp = requests.get(url, headers=headers, params=params, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                commands = data.get("application_commands", [])
                applications = {app.get("id"): app.get("name", "Bot") for app in data.get("applications", [])}
            elif resp.status_code in (404, 400):
                ch_info = self.get_channel_info(channel_id)
                guild_id = ch_info.get("guild_id") if ch_info else None
                if guild_id:
                    url_g = f"{DISCORD_API_BASE}/guilds/{guild_id}/application-commands/search"
                    resp_g = requests.get(url_g, headers=headers, params=params, timeout=10)
                    if resp_g.status_code == 200:
                        data = resp_g.json()
                        commands = data.get("application_commands", [])
                        applications = {app.get("id"): app.get("name", "Bot") for app in data.get("applications", [])}

            parsed_commands = []
            for cmd in commands:
                app_id = cmd.get("application_id")
                app_name = applications.get(app_id, "Bot")
                cmd_name = cmd.get("name")
                desc = cmd.get("description", "")
                options = cmd.get("options", [])

                subcommands = []
                for opt in options:
                    if opt.get("type") == 1:  # Subcommand
                        subcommands.append(opt.get("name"))

                parsed_commands.append({
                    "name": cmd_name,
                    "description": desc,
                    "app_name": app_name,
                    "app_id": app_id,
                    "subcommands": subcommands,
                    "raw": cmd
                })

            if parsed_commands:
                self._cached_commands[channel_id] = commands
                return True, parsed_commands, f"Найдено слеш-команд: {len(parsed_commands)}"
            else:
                return False, [], "В этом канале нет зарегистрированных слеш-команд ботов."
        except Exception as e:
            return False, [], f"Сетевая ошибка при поиске команд: {e}"

    def execute_slash_command(self, channel_id: str, raw_command: str) -> Tuple[bool, str, Optional[float]]:
        """
        Выполняет Discord Slash Command (например /waifu random, /daily и т.д.) через Interactions API.
        """
        cmd_text = raw_command.strip().lstrip("/")
        parts = cmd_text.split()
        if not parts:
            return False, "Пустая слеш-команда", None

        root_name = parts[0].lower()
        sub_name = parts[1].lower() if len(parts) > 1 else None
        extra_args = parts[2:] if len(parts) > 2 else []

        headers = get_base_headers(self.token)

        # 1. Получаем информацию о канале
        ch_info = self.get_channel_info(channel_id)
        guild_id = ch_info.get("guild_id") if ch_info else None
        ch_type = ch_info.get("type") if ch_info else None

        # Если это 1-on-1 DM с пользователем
        if ch_type == 1:
            self.log(f"Внимание: Выбран личный чат (ЛС). Слеш-команды ботов (/waifu random) работают на серверах, где добавлен бот Nekotina.", "warning")

        # 2. Ищем метаданные команды в канале или на сервере
        commands = []
        apps = {}

        url_search = f"{DISCORD_API_BASE}/channels/{channel_id}/application-commands/search"
        try:
            resp_search = requests.get(
                url_search,
                headers=dict(headers, **{"Content-Type": "application/json"}),
                params={"type": 1, "query": root_name, "include_applications": "true"},
                timeout=10
            )
            if resp_search.status_code == 200:
                data = resp_search.json()
                commands = data.get("application_commands", [])
                apps = {a.get("id"): a.get("name", "Bot") for a in data.get("applications", [])}
            elif guild_id:
                url_g = f"{DISCORD_API_BASE}/guilds/{guild_id}/application-commands/search"
                resp_g = requests.get(
                    url_g,
                    headers=dict(headers, **{"Content-Type": "application/json"}),
                    params={"type": 1, "query": root_name, "include_applications": "true"},
                    timeout=10
                )
                if resp_g.status_code == 200:
                    data = resp_g.json()
                    commands = data.get("application_commands", [])
                    apps = {a.get("id"): a.get("name", "Bot") for a in data.get("applications", [])}
        except Exception as e:
            return False, f"Ошибка соединения при поиске команды: {e}", None

        # Ищем команду с совпадением имени
        target_cmd = None
        for c in commands:
            if c.get("name", "").lower() == root_name:
                target_cmd = c
                break

        if not target_cmd:
            return False, f"Слеш-команда /{root_name} не найдена в API этого канала (убедитесь, что бот добавлен на этот сервер)", None

        app_id = target_cmd.get("application_id")
        app_name = apps.get(app_id, "Bot")
        cmd_id = target_cmd.get("id")
        cmd_version = target_cmd.get("version")
        cmd_options_schema = target_cmd.get("options", [])

        # Формируем структуру options
        interaction_options = []

        if sub_name and any(opt.get("name") == sub_name and opt.get("type") == 1 for opt in cmd_options_schema):
            sub_opt_schema = next(opt for opt in cmd_options_schema if opt.get("name") == sub_name)
            sub_params = []
            param_schemas = sub_opt_schema.get("options", [])
            for i, arg_val in enumerate(extra_args):
                if i < len(param_schemas):
                    param_schema = param_schemas[i]
                    sub_params.append({
                        "type": param_schema.get("type", 3),
                        "name": param_schema.get("name"),
                        "value": arg_val
                    })
            interaction_options.append({
                "type": 1,  # SUB_COMMAND
                "name": sub_name,
                "options": sub_params
            })
        else:
            for i, arg_val in enumerate(parts[1:]):
                if i < len(cmd_options_schema):
                    param_schema = cmd_options_schema[i]
                    interaction_options.append({
                        "type": param_schema.get("type", 3),
                        "name": param_schema.get("name"),
                        "value": arg_val
                    })

        session_id = generate_session_id()
        nonce = generate_nonce()

        payload = {
            "type": 2,  # APPLICATION_COMMAND
            "application_id": str(app_id),
            "channel_id": str(channel_id),
            "session_id": session_id,
            "data": {
                "version": str(cmd_version),
                "id": str(cmd_id),
                "name": str(target_cmd.get("name")),
                "type": 1,
                "options": interaction_options,
                "application_command": target_cmd,
                "attachments": []
            },
            "nonce": nonce
        }

        if guild_id:
            payload["guild_id"] = str(guild_id)

        # Отправляем Interaction через multipart/form-data
        url_int = f"{DISCORD_API_BASE}/interactions"
        multipart_files = {
            "payload_json": (None, json.dumps(payload, ensure_ascii=False), "application/json")
        }

        try:
            self.log(f"⚡ Отправка слеш-команды /{cmd_text} боту {app_name}...", "info")
            resp_int = requests.post(url_int, headers=headers, files=multipart_files, timeout=12)

            if resp_int.status_code in (200, 204):
                return True, f"Слеш-команда /{cmd_text} успешно отправлена боту {app_name}!", None

            elif resp_int.status_code == 429:
                try:
                    retry_after = float(resp_int.json().get("retry_after", 5.0))
                except Exception:
                    retry_after = 5.0
                return False, f"Рейтлимит на команды! Подождите {retry_after:.1f} сек.", retry_after

            elif resp_int.status_code == 400:
                try:
                    err_json = resp_int.json()
                    err_msg = err_json.get("message") or resp_int.text[:120]
                except Exception:
                    err_msg = resp_int.text[:120]
                return False, f"Discord вернул ошибку 400: {err_msg}", None

            elif resp_int.status_code == 403:
                return False, "Ошибка 403: Недостаточно прав для вызова команд ботов в этом канале.", None

            else:
                return False, f"Ошибка выполнения команды: HTTP {resp_int.status_code} ({resp_int.text[:100]})", None

        except Exception as e:
            return False, f"Сетевая ошибка при выполнении слеш-команды: {e}", None

    def send_typing(self, channel_id: str) -> bool:
        """Отправляет индикатор набора текста (typing...) в канал."""
        url = f"{DISCORD_API_BASE}/channels/{channel_id}/typing"
        headers = get_base_headers(self.token)
        headers["Content-Type"] = "application/json"
        try:
            resp = requests.post(url, headers=headers, timeout=6)
            return resp.status_code in (200, 204)
        except Exception:
            return False

    def send_message(self, channel_id: str, content: str, tts: bool = False) -> Tuple[bool, str, Optional[float]]:
        """
        Отправляет обычное текстовое сообщение в указанный канал.
        """
        url = f"{DISCORD_API_BASE}/channels/{channel_id}/messages"
        headers = get_base_headers(self.token)
        headers["Content-Type"] = "application/json"
        payload = {
            "content": content,
            "tts": tts
        }

        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=10)

            if resp.status_code in (200, 201):
                msg_data = resp.json()
                msg_id = msg_data.get("id", "")
                return True, f"Сообщение успешно отправлено (ID: {msg_id})", None

            elif resp.status_code == 429:
                try:
                    data = resp.json()
                    retry_after = float(data.get("retry_after", 5.0))
                except Exception:
                    retry_after = 5.0
                return False, f"Рейтлимит Discord! Необходимо подождать {retry_after:.1f} сек.", retry_after

            elif resp.status_code == 401:
                return False, "Ошибка 401: Токен недействителен или был сброшен.", None

            elif resp.status_code == 403:
                return False, "Ошибка 403: Недостаточно прав для отправки сообщения в этот канал.", None

            elif resp.status_code == 404:
                return False, "Ошибка 404: Канал не найден (проверьте ID канала).", None

            else:
                return False, f"Ошибка отправки: HTTP {resp.status_code} ({resp.text[:100]})", None

        except Exception as e:
            return False, f"Сетевая ошибка при отправке: {e}", None

    def send_message_or_command(
        self,
        channel_id: str,
        content: str,
        tts: bool = False,
        command_mode: str = "auto",
        fallback_to_text: bool = True
    ) -> Tuple[bool, str, Optional[float]]:
        """
        Универсальная отправка:
        - Если начинается со слэша '/' и command_mode != 'text_only':
            Выполняет как нативную слеш-команду.
            Если команда не найдена в API канала и fallback_to_text == True:
                Шлет как обычный текст.
        - Иначе -> отправляет обычным текстом.
        """
        clean_content = content.strip()
        is_slash = clean_content.startswith("/") and len(clean_content) > 1

        if is_slash and command_mode != "text_only":
            success, msg, retry_after = self.execute_slash_command(channel_id, clean_content)
            if success:
                return True, msg, None
            if retry_after:
                return False, msg, retry_after

            if fallback_to_text and command_mode == "auto":
                self.log(f"Слеш-команда в API не сработала ({msg}). Отправляем как текст...", "warning")
                return self.send_message(channel_id, clean_content, tts)

            return False, msg, None
        else:
            return self.send_message(channel_id, content, tts)
