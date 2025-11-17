# Де зберігаємо історію (базова тека)
HISTORY_BASE_DIR = "data/history/dialogs"

# Скільки повідомлень у одному чанку (наприклад, 10 пар = 20 меседжів)
HISTORY_MAX_MESSAGES_PER_CHUNK = 20

# Скільки останніх чанків брати в контекст для LLM
HISTORY_MAX_CHUNKS_FOR_CONTEXT = 5

# System prompts
SYSTEM_PROMPT_NAME = "maria_koval"         # ім'я файлу без .txt
# SYSTEM_PROMPTS_DIR = "src/system_prompts"
