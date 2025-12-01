import os
from dotenv import load_dotenv
from pathlib import Path

# Завантажує .env у змінні оточення
load_dotenv()

# Зчитує значення з .env
TELEGRAM_API_ID = int(os.getenv("TELEGRAM_API_ID", "0"))
TELEGRAM_API_HASH = os.getenv("TELEGRAM_API_HASH", "")

# Окрема папка для сесій Telethon (з інструкції: telegram_api/sesions/)
SESSION_DIR = Path(__file__).parent / "sesions"

# Ім'я сесії для основного клієнта (user API)
SESSION_NAME = os.getenv("TG_SESSION_NAME", os.getenv("SESSION_NAME", "user_session"))

# Власний .session для адмін-консолі, щоб не змішувати авторизації
ADMIN_CONSOLE_SESSION_NAME = os.getenv(
    "TG_SESSION_NAME_ADMIN_CONSOLE", f"{SESSION_NAME}_admin_console"
)