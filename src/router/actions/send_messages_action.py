"""Обробник дії send_messages для LLMRouter."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any, Dict, Iterable

from src.history.history_manager import HistoryManager
from src.telegram_api.telegram_api import TelegramAPI


async def handle_send_messages(
    telegram: TelegramAPI,
    history: HistoryManager,
    chat_id: int,
    user_id: int,
    payload: Dict[str, Any],
    human_seconds: float,
) -> None:
    """Надсилає кілька текстових повідомлень підряд і записує їх в історію.

    Параметри:
    - telegram: інстанс TelegramAPI для реального відправлення.
    - history: менеджер історії, куди додаємо кожен меседж від бота.
    - chat_id: ідентифікатор чату, куди потрібно надіслати текст.
    - user_id: ідентифікатор користувача, якого стосується діалог.
    - payload: словник із полями дії, очікуємо payload["messages"] як список.
    - human_seconds: базовий час для індикації "typing", якщо у вкладених елементах він відсутній.
    """

    raw_messages = payload.get("messages")
    if not raw_messages or not isinstance(raw_messages, Iterable) or isinstance(
        raw_messages, (str, bytes)
    ):
        return

    for raw_message in raw_messages:
        if not isinstance(raw_message, dict):
            continue

        content = raw_message.get("content")
        if not content:
            continue

        message_wait_seconds = float(raw_message.get("wait_seconds", 0) or 0)
        message_human_seconds = float(
            raw_message.get("human_seconds", human_seconds) or human_seconds or 0
        )

        # Пауза перед конкретним повідомленням, щоб зімітувати затримку між ними.
        if message_wait_seconds > 0:
            await asyncio.sleep(message_wait_seconds)

        # Показуємо статус "typing" для кожного меседжу окремо.
        await telegram.send_typing(chat_id, message_human_seconds)

        try:
            message = await telegram.send_message(chat_id, content)
            message_time_iso = (
                message.date.astimezone(timezone.utc).isoformat()
                if getattr(message, "date", None)
                else datetime.now(timezone.utc).isoformat()
            )
            # Фіксуємо кожне відправлене повідомлення бота в історії.
            history.append_message(
                user_id=user_id,
                role="assistant",
                content=content,
                message_time_iso=message_time_iso,
            )
        except Exception as exc:
            # Не кидаємо помилку вище, щоб не зірвати відправку наступних меседжів.
            print(
                f"❌ Не вдалося відправити повідомлення користувачу {user_id}: {exc}"
            )
