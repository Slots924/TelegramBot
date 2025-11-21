"""Обробник дії add_reaction для LLMRouter."""

from __future__ import annotations

import asyncio
from typing import Any, Dict

from src.history.history_manager import HistoryManager
from src.telegram_api.telegram_api import TelegramAPI


async def handle_add_reaction(
    telegram: TelegramAPI,
    history: HistoryManager,
    chat_id: int,
    user_id: int,
    payload: Dict[str, Any],
    human_seconds: float,
) -> None:
    """Ставить реакцію на конкретне повідомлення користувача.

    Параметри:
    - telegram: інстанс TelegramAPI для надсилання реакції.
    - history: не використовується, але лишається для сумісності інтерфейсу.
    - chat_id: ідентифікатор чату, де лежить цільове повідомлення.
    - user_id: ідентифікатор користувача (лише для логів у разі потреби).
    - payload: очікуємо message_id та emoji.
    - human_seconds: скільки секунд імітувати паузу перед реакцією.
    """

    target_message_id = payload.get("message_id")
    emoji = payload.get("emoji") or "👍"

    if target_message_id is None:
        return

    # Якщо потрібно імітувати затримку перед реакцією – чекаємо в async-режимі.
    if human_seconds > 0:
        await asyncio.sleep(human_seconds)

    await telegram.send_reaction(chat_id, target_message_id, emoji)
