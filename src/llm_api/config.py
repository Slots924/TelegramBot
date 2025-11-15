import os
from dotenv import load_dotenv

load_dotenv()

# базові LLM налаштування
MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")
if not MISTRAL_API_KEY:
    raise RuntimeError("❌ MISTRAL_API_KEY не знайдено в .env")

BASE_URL = os.getenv(
    "BASE_URL", "https://api.mistral.ai/v1/chat/completions"
)
MISTRAL_MODEL = os.getenv("MISTRAL_MODEL", "mistral-small-latest")
MISTRAL_TEMPERATURE = float(os.getenv("MISTRAL_TEMPERATURE", "0.7"))
MISTRAL_MAX_TOKENS = int(os.getenv("MISTRAL_MAX_TOKENS", "512"))
MISTRAL_TOP_P = float(os.getenv("MISTRAL_TOP_P", "0.9"))
MISTRAL_PRESENCE_PENALTY = float(os.getenv("MISTRAL_PRESENCE_PENALTY", "0.8"))
MISTRAL_FREQUENCY_PENALTY = float(os.getenv("MISTRAL_FREQUENCY_PENALTY", "0.6"))

# директорія src/
MODULE_DIR = os.path.dirname(__file__)
SRC_DIR = os.path.dirname(MODULE_DIR)

# дефолтна папка з системними промптами: src/system_prompts
DEFAULT_SYSTEM_PROMPTS_DIR = os.path.join(SRC_DIR, "system_prompts")

SYSTEM_PROMPTS_DIR = os.getenv("SYSTEM_PROMPTS_DIR", DEFAULT_SYSTEM_PROMPTS_DIR)
SYSTEM_PROMPT_NAME = os.getenv("SYSTEM_PROMPT_NAME", "default")
