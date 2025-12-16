"""Обробник дії add_reaction для LLMRouter."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
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

    # Фіксуємо у історії, що асистент поставив реакцію на повідомлення користувача,
    # уніфіковуючи формат запису для подальшого використання LLM.
    last_assistant_message_id = history.get_last_assistant_message_id(user_id)
    history.append_message(
        user_id=user_id,
        role="assistant",
        content=f"[REACTION] '{emoji}' on message_id = {target_message_id}",
        message_time_iso=datetime.now(timezone.utc).isoformat(),
        # Використовуємо message_id останнього повідомлення асистента, щоб у контексті
        # був прив'язаний саме ботівський запис, а не користувацький target_message_id.
        message_id=last_assistant_message_id,
    )
