"""Обробник дії wait для LLMRouter."""

from __future__ import annotations

import asyncio
from typing import Any, Dict

from src.history.history_manager import HistoryManager
from src.telegram_api.telegram_api import TelegramAPI


async def handle_wait(
    telegram: TelegramAPI,
    history: HistoryManager,
    chat_id: int,
    user_id: int,
    payload: Dict[str, Any],
    human_seconds: float,
) -> None:
    """Просто очікує задану кількість секунд без інших дій.

    Параметри:
    - telegram: не використовується, але залишається для сумісності інтерфейсу.
    - history: не використовується для цієї дії.
    - chat_id: не використовується.
    - user_id: не використовується.
    - payload: не використовується, час беремо з human_seconds.
    - human_seconds: кількість секунд, яку потрібно перечекати.
    """

    if human_seconds > 0:
        await asyncio.sleep(human_seconds)
