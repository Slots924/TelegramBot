import os
from dotenv import load_dotenv

load_dotenv()

# базові LLM налаштування
MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")
if not MISTRAL_API_KEY:
    raise RuntimeError("❌ MISTRAL_API_KEY не знайдено в .env")

MISTRAL_MODEL = os.getenv("MISTRAL_MODEL", "mistral-small-latest")
MISTRAL_TEMPERATURE = float(os.getenv("MISTRAL_TEMPERATURE", "0.7"))
MISTRAL_MAX_TOKENS = int(os.getenv("MISTRAL_MAX_TOKENS", "512"))

# директорія src/
MODULE_DIR = os.path.dirname(__file__)
SRC_DIR = os.path.dirname(MODULE_DIR)

# дефолтна папка з системними промптами: src/system_prompts
DEFAULT_SYSTEM_PROMPTS_DIR = os.path.join(SRC_DIR, "system_prompts")

SYSTEM_PROMPTS_DIR = os.getenv("SYSTEM_PROMPTS_DIR", DEFAULT_SYSTEM_PROMPTS_DIR)
SYSTEM_PROMPT_NAME = os.getenv("SYSTEM_PROMPT_NAME", "default")