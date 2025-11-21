"""Обробник дії ignore для LLMRouter."""

from __future__ import annotations

from typing import Any, Dict

from src.history.history_manager import HistoryManager
from src.telegram_api.telegram_api import TelegramAPI


async def handle_ignore(
    telegram: TelegramAPI,
    history: HistoryManager,
    chat_id: int,
    user_id: int,
    payload: Dict[str, Any],
    human_seconds: float,
) -> None:
    """Ігнорує запитану дію без будь-яких побічних ефектів.

    Параметри залишено для сумісності з іншими хендлерами, але не використовуються.
    """

    # Намірено нічого не робимо, щоб пропустити дію без змін стану.
    return
