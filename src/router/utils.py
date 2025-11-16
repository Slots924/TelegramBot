"""Допоміжні функції для LLMRouter."""

from __future__ import annotations

from src.config.settings import TYPING_SECONDS_DEFAULT


def get_typing_duration(answer_text: str) -> float:
    """Повертає тривалість "набору" відповіді у секундах.

    Поки що ми не аналізуємо сам текст, а повертаємо фіксоване значення
    з налаштувань. У майбутньому можна буде зробити залежність від довжини
    відповіді або інших факторів.
    """

    _ = answer_text  # щоб явно показати, що параметр поки не використовується
    return TYPING_SECONDS_DEFAULT
