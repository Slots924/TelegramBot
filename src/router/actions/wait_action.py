"""Обробник дії wait для LLMRouter."""

from __future__ import annotations

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
    """Порожній хендлер для дії очікування без додаткових ефектів.

    Часова затримка для цієї дії уже обробляється на рівні LLMRouter
    через поле ``wait_seconds``. Тут ми нічого не робимо, щоб просто
    дозволити сценарію перейти до наступної дії без помилок.
    """

    # Намірено нічого не робимо, щоб лише зафіксувати коректність дії.
    return
