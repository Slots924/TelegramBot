"""Налаштування проєкту, що стосуються роутера та імітації typing."""

from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()


def _get_float_env(var_name: str, default: float) -> float:
    """Пробує прочитати float зі змінної середовища, інакше повертає дефолт."""

    raw_value = os.getenv(var_name)
    if raw_value is None:
        return default

    try:
        return float(raw_value)
    except ValueError:
        print(
            f"⚠️ Неможливо конвертувати змінну {var_name}='{raw_value}' у float. Використовую дефолт {default}."
        )
        return default


DEBOUNCE_SECONDS: float = _get_float_env("DEBOUNCE_SECONDS", 2.0)
"""float: затримка перед запуском чергового циклу відповіді LLM."""

TYPING_SECONDS_DEFAULT: float = _get_float_env("TYPING_SECONDS_DEFAULT", 5.0)
"""float: базова тривалість імітації набору тексту у Telegram."""


def get_typing_duration(answer_text: str) -> float:
    """Обчислює, скільки секунд імітувати набір відповіді.

    Поки що функція повертає фіксоване значення з налаштувань.
    У майбутньому тут можна буде аналізувати довжину відповіді,
    складність тексту тощо.

    Parameters
    ----------
    answer_text: str
        Текст, який плануємо відправити користувачу.

    Returns
    -------
    float
        Кількість секунд, протягом яких показуємо статус "typing".
    """

    _ = answer_text  # Параметр поки не використовується, але залишаємо для майбутніх змін.
    return TYPING_SECONDS_DEFAULT
