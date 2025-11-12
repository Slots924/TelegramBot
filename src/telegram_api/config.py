import os
from dotenv import load_dotenv

# Завантажує .env у змінні оточення
load_dotenv()

# Зчитує значення з .env
TELEGRAM_API_ID = int(os.getenv("TELEGRAM_API_ID", "0"))
TELEGRAM_API_HASH = os.getenv("TELEGRAM_API_HASH", "")
SESSION_NAME = os.getenv("SESSION_NAME", "user_session") 