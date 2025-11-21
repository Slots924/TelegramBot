"""Обробник дії fake_typing для LLMRouter."""

from __future__ import annotations

from typing import Any, Dict

from src.history.history_manager import HistoryManager
from src.telegram_api.telegram_api import TelegramAPI


async def handle_fake_typing(
    telegram: TelegramAPI,
    history: HistoryManager,
    chat_id: int,
    user_id: int,
    payload: Dict[str, Any],
    human_seconds: float,
) -> None:
    """Показує статус набору тексту без фактичного відправлення повідомлення.

    Параметри:
    - telegram: інстанс TelegramAPI для виклику send_typing.
    - history: не використовується, присутній для єдиного інтерфейсу.
    - chat_id: ідентифікатор чату, де треба показати typing.
    - user_id: ідентифікатор користувача (лише для відповідності сигнатурі).
    - payload: не використовується для цієї дії.
    - human_seconds: тривалість індикації "typing" у секундах.
    """

    if human_seconds > 0:
        await telegram.send_typing(chat_id, human_seconds)
