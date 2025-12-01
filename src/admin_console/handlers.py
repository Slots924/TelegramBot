"""Хендлери для виконання адмін-команд."""

from __future__ import annotations

import json
import os
import shutil
from datetime import datetime, timezone
from typing import Tuple

from settings import HISTORY_BASE_DIR, USER_INFO_FILENAME
from src.admin_console.commands import (
    AppendSystemPromptCommand,
    DeleteDialogCommand,
    ListDialogsCommand,
    PruneHistoryCommand,
    SendMessageCommand,
    SyncUnreadCommand,
    ShowHistoryCommand,
)
from src.admin_console.utils import sanitize_text
from src.history.history_manager import HistoryManager
from src.router.llm_router import LLMRouter
from src.telegram_api.telegram_api import TelegramAPI


async def _resolve_user(
    raw_target: str,
    user_id: int | None,
    username: str | None,
    telegram: TelegramAPI,
) -> Tuple[int, str | None]:
    """Резолвить user_id за потреби та повертає пару (user_id, username)."""

    if user_id is not None:
        return user_id, username

    if not username:
        raise ValueError("Потрібно вказати user_id або username.")

    try:
        entity = await telegram.client.get_entity(username)
        resolved_id = getattr(entity, "id", None)
        resolved_username = getattr(entity, "username", None) or username
    except Exception as exc:
        raise ValueError(f"Не вдалося знайти користувача за username '{username}': {exc}")

    if resolved_id is None:
        raise ValueError("Не вийшло отримати user_id після резолву username.")

    return int(resolved_id), resolved_username


async def handle_send_message(
    cmd: SendMessageCommand,
    telegram: TelegramAPI,
    history: HistoryManager,
    router: LLMRouter,
) -> None:
    """Обробляє команду send: напряму або через LLMRouter у pro-active режимі."""

    target_user_id, resolved_username = await _resolve_user(
        raw_target=cmd.raw_target,
        user_id=cmd.user_id,
        username=cmd.username,
        telegram=telegram,
    )
    chat_id = target_user_id

    if cmd.text:
        # Режим прямої відправки повідомлення
        clean_text = sanitize_text(cmd.text)

        message = await telegram.send_message(chat_id, clean_text)
        message_time_iso = (
            message.date.astimezone(timezone.utc).isoformat()
            if getattr(message, "date", None)
            else datetime.now(timezone.utc).isoformat()
        )
        history.append_message(
            user_id=target_user_id,
            role="assistant",
            content=clean_text,
            message_time_iso=message_time_iso,
            message_id=getattr(message, "id", None),
        )
        print(
            f"✅ Надіслано повідомлення користувачу {target_user_id} | {resolved_username}: \"{clean_text}\""
        )
        return

    # Якщо тексту немає — просимо LLM самостійно згенерувати та надіслати повідомлення.
    # Використовуємо окремий метод, який повертає JSON-доступні дії й одразу їх виконує
    # без запуску звичних циклів очікування/дебаунсу.
    print(
        f"🤖 LLM ініціює повідомлення для користувача {target_user_id} | {resolved_username} через роутер (proactive single message)."
    )
    await router.send_single_message_proactively(
        user_id=target_user_id,
        chat_id=chat_id,
        instruction="Напиши повідомлення цьому користувачу",
    )


async def handle_append_system_prompt(
    cmd: AppendSystemPromptCommand, history: HistoryManager, telegram: TelegramAPI
) -> None:
    """Додає системний промпт до кінця історії користувача."""

    target_user_id, resolved_username = await _resolve_user(
        raw_target=cmd.raw_target,
        user_id=cmd.user_id,
        username=cmd.username,
        telegram=telegram,
    )

    sanitized_content = sanitize_text(cmd.content)

    history.append_message(
        user_id=target_user_id,
        role="system",
        content=sanitized_content,
        message_time_iso=datetime.now(timezone.utc).isoformat(),
        message_id=None,
    )
    print(
        f"🧩 Додано системний промпт для {target_user_id} | {resolved_username}: {sanitized_content}"
    )


async def handle_list_dialogs(cmd: ListDialogsCommand) -> None:
    """
    Виводить таблицю з усіма діалогами, що є у файловій системі.

    Оновлення: показуємо останній номер чанка і час останньої зміни в папці
    користувача. Форматуємо все у вирівняну таблицю, щоб зручно читалось.
    """

    user_dirs = [
        name
        for name in os.listdir(HISTORY_BASE_DIR)
        if os.path.isdir(os.path.join(HISTORY_BASE_DIR, name)) and name.startswith("user_")
    ]
    if not user_dirs:
        print("ℹ️ Діалогів поки немає.")
        return

    # Збираємо всі дані наперед, щоб порахувати максимальну ширину колонок.
    rows: list[dict[str, str]] = []
    for folder in sorted(user_dirs):
        user_id = _extract_user_id(folder)
        if user_id is None:
            continue

        user_dir = os.path.join(HISTORY_BASE_DIR, folder)
        user_info_path = os.path.join(user_dir, USER_INFO_FILENAME)
        user_info = _load_user_info(user_info_path)

        last_chunk = _get_last_chunk_index(user_dir)
        last_update = _get_last_update_time(user_dir)

        rows.append(
            {
                "user_id": str(user_id),
                "username": user_info.get("username") or "Null",
                "first_name": user_info.get("first_name") or "Null",
                "last_name": user_info.get("last_name") or "Null",
                "last_chunk": last_chunk,
                "last_update": last_update,
            }
        )

    # Рахуємо ширини колонок (беремо максимум між заголовком та значеннями).
    headers = {
        "user_id": "user_id",
        "username": "username",
        "first_name": "first_name",
        "last_name": "last_name",
        "last_chunk": "last_chunk",
        "last_update": "last_update",
    }
    column_widths = {
        key: max(len(headers[key]), *(len(row[key]) for row in rows)) for key in headers
    }

    def format_row(row_values: dict[str, str]) -> str:
        """Форматує один рядок таблиці, вирівнюючи значення по ширинам колонок."""

        return " | ".join(
            row_values[col].ljust(column_widths[col])
            for col in [
                "user_id",
                "username",
                "first_name",
                "last_name",
                "last_chunk",
                "last_update",
            ]
        )

    print(format_row(headers))
    for row in rows:
        print(format_row(row))


def _extract_user_id(folder_name: str) -> int | None:
    """Дістає user_id з назви папки виду user_<id>. Повертає None, якщо формат невалідний."""

    try:
        return int(folder_name.replace("user_", ""))
    except ValueError:
        return None


def _load_user_info(user_info_path: str) -> dict[str, str | None]:
    """Зчитує USER_INFO з файлу, якщо він існує. Повертає словник з ключами username/first_name/last_name."""

    if not os.path.exists(user_info_path):
        return {}

    try:
        with open(user_info_path, "r", encoding="utf-8") as file:
            raw = file.read()
        if "USER_INFO =" not in raw:
            return {}

        json_block = raw.split("USER_INFO =", 1)[1]
        json_block = json_block.split("USER_INFO_BLOCK_END", 1)[0].strip()
        data = json.loads(json_block)
        return {
            "username": data.get("username"),
            "first_name": data.get("first_name"),
            "last_name": data.get("last_name"),
        }
    except Exception as exc:
        # Не валимо команду, просто повідомляємо про проблему.
        print(f"⚠️ Не вдалося прочитати user_info за шляхом {user_info_path}: {exc}")
        return {}


def _get_last_chunk_index(user_dir: str) -> str:
    """Повертає номер останнього чанка користувача або 'тгдд', якщо чанків немає."""

    chunk_files = [
        name
        for name in os.listdir(user_dir)
        if name.startswith("chunk_") and name.endswith(".json")
    ]
    if not chunk_files:
        return "тгдд"

    chunk_files.sort()
    last_name = chunk_files[-1]

    try:
        return str(int(last_name.replace("chunk_", "").replace(".json", "")))
    except ValueError:
        # Якщо назва битa, показуємо її як є, щоб було видно проблему.
        return last_name


def _get_last_update_time(user_dir: str) -> str:
    """Визначає час останньої зміни в папці користувача у форматі HH:MM DD.MM.YYYY."""

    latest_ts = os.path.getmtime(user_dir)

    # Обходимо всі файли в папці користувача, щоб знайти найсвіжішу зміну.
    for root, _, files in os.walk(user_dir):
        for filename in files:
            file_path = os.path.join(root, filename)
            try:
                latest_ts = max(latest_ts, os.path.getmtime(file_path))
            except FileNotFoundError:
                # Файл могли видалити між os.walk і getmtime — пропускаємо.
                continue

    last_update_dt = datetime.fromtimestamp(latest_ts)
    return last_update_dt.strftime("%H:%M %d.%m.%Y")


async def handle_show_history(
    cmd: ShowHistoryCommand, history: HistoryManager, telegram: TelegramAPI
) -> None:
    """Виводить останні повідомлення користувача в читабельній формі."""

    target_user_id, resolved_username = await _resolve_user(
        raw_target=cmd.raw_target,
        user_id=cmd.user_id,
        username=cmd.username,
        telegram=telegram,
    )
    messages = history.get_recent_context(target_user_id)
    if not messages:
        print(f"ℹ️ Історія для {target_user_id} | {resolved_username} порожня.")
        return

    tail = messages[-cmd.limit :]
    for idx, item in enumerate(tail, start=1):
        role = item.get("role") or "unknown"
        content = item.get("content") or "(empty)"
        sent_at = item.get("created_at")
        message_id = item.get("message_id")
        print(
            f"[{idx}] {role} [sent_at={sent_at} | message_id={message_id}]\n  {content}\n"
        )


async def handle_prune_history(
    cmd: PruneHistoryCommand, telegram: TelegramAPI
) -> None:
    """Видаляє всі зайві чанки історії, залишаючи лише потрібну кількість."""

    target_user_id, resolved_username = await _resolve_user(
        raw_target=cmd.raw_target,
        user_id=cmd.user_id,
        username=cmd.username,
        telegram=telegram,
    )
    user_dir = os.path.join(HISTORY_BASE_DIR, f"user_{target_user_id}")

    if not os.path.exists(user_dir):
        print(
            f"ℹ️ Папка {user_dir} не знайдена для {target_user_id} | {resolved_username}. Немає що обрізати."
        )
        return

    chunk_files = [
        f
        for f in os.listdir(user_dir)
        if f.startswith("chunk_") and f.endswith(".json")
    ]
    if not chunk_files:
        print("ℹ️ Чанків не знайдено, видаляти нічого.")
        return

    chunk_files.sort()
    to_delete = chunk_files[:-cmd.keep_chunks] if cmd.keep_chunks < len(chunk_files) else []

    for filename in to_delete:
        try:
            os.remove(os.path.join(user_dir, filename))
        except Exception as exc:
            print(f"⚠️ Не вдалося видалити {filename}: {exc}")

    kept = chunk_files[-cmd.keep_chunks :] if cmd.keep_chunks < len(chunk_files) else chunk_files
    print(
        f"🧹 Видалено {len(to_delete)} файлів для {target_user_id} | {resolved_username}. Залишились: {', '.join(kept)}"
    )


async def handle_delete_dialog(
    cmd: DeleteDialogCommand, telegram: TelegramAPI
) -> None:
    """Повністю видаляє папку діалогу користувача."""

    target_user_id, resolved_username = await _resolve_user(
        raw_target=cmd.raw_target,
        user_id=cmd.user_id,
        username=cmd.username,
        telegram=telegram,
    )
    user_dir = os.path.join(HISTORY_BASE_DIR, f"user_{target_user_id}")

    if not os.path.exists(user_dir):
        print(
            f"ℹ️ Папка {user_dir} не знайдена для {target_user_id} | {resolved_username}."
        )
        return

    try:
        shutil.rmtree(user_dir)
        print(
            f"🗑 Діалог {os.path.basename(user_dir)} видалено повністю для {target_user_id} | {resolved_username}."
        )
    except Exception as exc:
        print(f"⚠️ Не вдалося видалити папку {user_dir}: {exc}")


async def handle_sync_unread(
    cmd: SyncUnreadCommand,
    telegram: TelegramAPI,
    history: HistoryManager,
    router: LLMRouter,
) -> None:
    """Підтягує всі непрочитані повідомлення, оновлює історію та за потреби тригерить LLM."""

    target_user_id, resolved_username = await _resolve_user(
        raw_target=cmd.raw_target,
        user_id=cmd.user_id,
        username=cmd.username,
        telegram=telegram,
    )
    chat_id = target_user_id

    print(
        "🔄 Синхронізую непрочитані повідомлення для "
        f"{target_user_id} | {resolved_username}. trigger_llm={cmd.trigger_llm}"
    )
    await router.sync_unread_for_user(
        user_id=target_user_id,
        chat_id=chat_id,
        trigger_llm=cmd.trigger_llm,
    )
    print("✅ Синхронізацію непрочитаних завершено.")
