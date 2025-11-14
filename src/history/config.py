import os
from dotenv import load_dotenv

load_dotenv()

# Базова директорія, де буде data/history/...
HISTORY_BASE_DIR = os.getenv("HISTORY_BASE_DIR", "data/history/dialogs")

# Максимальна кількість повідомлень в одному чанку (user+assistant разом)
HISTORY_MAX_MESSAGES_PER_CHUNK = int(os.getenv("HISTORY_MAX_MESSAGES_PER_CHUNK", "20"))

# Скільки останніх чанків брати для побудови контексту
HISTORY_MAX_CHUNKS_FOR_CONTEXT = int(os.getenv("HISTORY_MAX_CHUNKS_FOR_CONTEXT", "5"))