import os
from dotenv import load_dotenv

import settings as project_settings

load_dotenv()

# базові LLM налаштування
LLM_API_KEY = os.getenv("LLM_API_KEY")
if not LLM_API_KEY:
    raise RuntimeError("❌ LLM_API_KEY не знайдено в .env")

LLM_BASE_URL = os.getenv(
    "LLM_BASE_URL", "https://api.mistral.ai/v1/chat/completions"
)
LLM_MODEL = os.getenv("LLM_MODEL", "mistral-small-latest")
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.7"))
LLM_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "512"))
LLM_TOP_P = float(os.getenv("LLM_TOP_P", "0.9"))
LLM_PRESENCE_PENALTY = float(os.getenv("LLM_PRESENCE_PENALTY", "0.8"))
LLM_FREQUENCY_PENALTY = float(os.getenv("LLM_FREQUENCY_PENALTY", "0.6"))

# директорія src/
MODULE_DIR = os.path.dirname(__file__)
SRC_DIR = os.path.dirname(MODULE_DIR)

# дефолтна папка з системними промптами: src/system_prompts
DEFAULT_SYSTEM_PROMPTS_DIR = os.path.join(SRC_DIR, "system_prompts")

SYSTEM_PROMPTS_DIR = getattr(
    project_settings, "SYSTEM_PROMPTS_DIR", DEFAULT_SYSTEM_PROMPTS_DIR
)
SYSTEM_PROMPT_NAME = project_settings.SYSTEM_PROMPT_NAME
