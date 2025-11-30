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
    ShowHistoryCommand,
)
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
        message = await telegram.send_message(chat_id, cmd.text)
        message_time_iso = (
            message.date.astimezone(timezone.utc).isoformat()
            if getattr(message, "date", None)
            else datetime.now(timezone.utc).isoformat()
        )
        history.append_message(
            user_id=target_user_id,
            role="assistant",
            content=cmd.text,
            message_time_iso=message_time_iso,
            message_id=getattr(message, "id", None),
        )
        print(
            f"✅ Надіслано повідомлення користувачу {target_user_id} | {resolved_username}: \"{cmd.text}\""
        )
        return

    # Якщо тексту немає — запускаємо LLMRouter, щоб він сам сформував дії.
    print(
        f"🤖 LLM ініціює повідомлення для користувача {target_user_id} | {resolved_username} через роутер (proactive mode)."
    )
    await router.trigger_proactive_message(
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

    history.append_message(
        user_id=target_user_id,
        role="system",
        content=cmd.content,
        message_time_iso=datetime.now(timezone.utc).isoformat(),
        message_id=None,
    )
    print(
        f"🧩 Додано системний промпт для {target_user_id} | {resolved_username}: {cmd.content}"
    )


async def handle_list_dialogs(cmd: ListDialogsCommand) -> None:
    """Виводить таблицю з усіма діалогами, що є у файловій системі."""

    user_dirs = [
        name
        for name in os.listdir(HISTORY_BASE_DIR)
        if os.path.isdir(os.path.join(HISTORY_BASE_DIR, name)) and name.startswith("user_")
    ]
    if not user_dirs:
        print("ℹ️ Діалогів поки немає.")
        return

    print("user_id | username | first_name | last_name")
    for folder in sorted(user_dirs):
        try:
            user_id = int(folder.replace("user_", ""))
        except ValueError:
            continue
        user_info_path = os.path.join(HISTORY_BASE_DIR, folder, USER_INFO_FILENAME)
        username = None
        first_name = None
        last_name = None

        if os.path.exists(user_info_path):
            try:
                with open(user_info_path, "r", encoding="utf-8") as file:
                    raw = file.read()
                if "USER_INFO =" in raw:
                    json_block = raw.split("USER_INFO =", 1)[1]
                    json_block = json_block.split("USER_INFO_BLOCK_END", 1)[0].strip()
                    data = json.loads(json_block)
                    username = data.get("username")
                    first_name = data.get("first_name")
                    last_name = data.get("last_name")
            except Exception as exc:
                print(f"⚠️ Не вдалося прочитати user_info для {user_id}: {exc}")

        username_value = username if username else "Null"
        first_value = first_name if first_name else "Null"
        last_value = last_name if last_name else "Null"
        print(f"{user_id} | {username_value} | {first_value} | {last_value}")


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
