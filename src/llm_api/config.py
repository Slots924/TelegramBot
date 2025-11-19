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
LLM_TEMPERATURE = project_settings.LLM_TEMPERATURE
LLM_MAX_TOKENS = project_settings.LLM_MAX_TOKENS
LLM_TOP_P = project_settings.LLM_TOP_P
LLM_PRESENCE_PENALTY = project_settings.LLM_PRESENCE_PENALTY
LLM_FREQUENCY_PENALTY = project_settings.LLM_FREQUENCY_PENALTY

# директорія src/
MODULE_DIR = os.path.dirname(__file__)
SRC_DIR = os.path.dirname(MODULE_DIR)
PROJECT_ROOT = os.path.dirname(SRC_DIR)

# дефолтна папка з системними промптами: data/system_prompts
DEFAULT_SYSTEM_PROMPTS_DIR = os.path.join(PROJECT_ROOT, "data", "system_prompts")

SYSTEM_PROMPTS_DIR = getattr(
    project_settings, "SYSTEM_PROMPTS_DIR", DEFAULT_SYSTEM_PROMPTS_DIR
)
SYSTEM_PROMPT_NAME = project_settings.SYSTEM_PROMPT_NAME
