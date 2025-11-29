"""Загальні налаштування проєкту.

Тут збираємо всі параметри, які можуть знадобитися різним модулям
(історія, системні промпти, LLM тощо). Значення визначаються тут,
а не у коді модулів, щоби зручно було їх змінювати в одному місці.
"""

from __future__ import annotations

import os
from dotenv import load_dotenv

load_dotenv()

# Базова директорія проєкту (папка, де лежить цей файл)
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
# Окрема папка для всіх даних
DATA_DIR = os.path.join(PROJECT_ROOT, "data")

# Де зберігаємо історію (базова тека)
HISTORY_BASE_DIR = os.path.join(DATA_DIR, "dialogs")

# Скільки повідомлень у одному чанку (наприклад, 10 пар = 20 меседжів)
HISTORY_MAX_MESSAGES_PER_CHUNK = 20

# Скільки останніх чанків брати в контекст для LLM
HISTORY_MAX_CHUNKS_FOR_CONTEXT = 5

# System prompts
SYSTEM_PROMPT_NAME = "long_dialoge"         # ім'я файлу без .txt
SYSTEM_PROMPTS_DIR = os.path.join(DATA_DIR, "system_prompts")
# Додаткові перемикачі системних промптів
ACTIONS_SYSTEM_PROMPT = True   # чи додавати інструкцію з data/system_prompts/actions.txt
USER_INFO_SYSTEM_PROMPT = True # чи передавати LLM системний промпт з інформацією про юзера

# Назва файлу з інформацією про користувача всередині dialogs/user_<id>
USER_INFO_FILENAME = "user_info.txt"

# Чи відповідаємо на повідомлення від телеграм-ботів (за замовчуванням ні)
ANSWER_TO_TELEGRAM_BOTS = os.getenv("ANSWER_TO_TELEGRAM_BOTS", "False").lower() == "true"

# Просте читання числових налаштувань з env із запасним дефолтом
try:
    DEBOUNCE_SECONDS: float = float(os.getenv("DEBOUNCE_SECONDS", "12"))
except ValueError:
    print(
        "⚠️ Неможливо конвертувати DEBOUNCE_SECONDS у float. Використовую дефолт 12."
    )
    DEBOUNCE_SECONDS = 12.0
"""float: затримка перед запуском чергового циклу відповіді LLM."""

try:
    TYPING_SECONDS_DEFAULT: float = float(os.getenv("TYPING_SECONDS_DEFAULT", "15.0"))
except ValueError:
    print(
        "⚠️ Неможливо конвертувати TYPING_SECONDS_DEFAULT у float. Використовую дефолт 15.0."
    )
    TYPING_SECONDS_DEFAULT = 15.0
"""float: базова тривалість імітації набору тексту у Telegram."""

# Налаштування LLM (параметри запиту)
LLM_TEMPERATURE = 1
LLM_MAX_TOKENS = 1024
LLM_TOP_P = 0.92
# Параметри поки не використовуються в запитах, але читаємо їх для майбутніх доробок
LLM_PRESENCE_PENALTY = 0.92
LLM_FREQUENCY_PENALTY = 0.6
