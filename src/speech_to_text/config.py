"""Конфігурація для сервісу розпізнавання мовлення."""

import os
from distutils.util import strtobool
from dotenv import load_dotenv

# Завантажуємо змінні з .env у середовище виконання
load_dotenv()


def _get_bool(env_value: str | None, default: bool) -> bool:
    """Перетворює значення з .env у bool з безпечним дефолтом."""

    if env_value is None:
        return default
    try:
        return bool(strtobool(env_value))
    except ValueError:
        return default


# Чи дозволено запускати STT
STT_ENABLED: bool = _get_bool(os.getenv("STT_ENABLED"), False)

# Шлях до JSON з ключами сервісного акаунта Google
GOOGLE_CREDENTIALS_PATH: str = os.getenv("GOOGLE_CREDENTIALS_PATH", "")

# Максимальна довжина обробки аудіо (секунди)
STT_MAX_SECONDS: int = int(os.getenv("STT_MAX_SECONDS", "50"))

# Основна мова розпізнавання
STT_PRIMARY_LANGUAGE: str = os.getenv("STT_PRIMARY_LANGUAGE", "uk-UA")

# Альтернативні мови (рядок через кому → список)
STT_ALT_LANGUAGES_RAW: str = os.getenv("STT_ALT_LANGUAGES", "")
STT_ALT_LANGUAGES: list[str] = [
    lang.strip()
    for lang in STT_ALT_LANGUAGES_RAW.split(",")
    if lang.strip()
]

# Тимчасова директорія для проміжних файлів
STT_TMP_DIR: str = os.getenv("STT_TMP_DIR", os.path.join("data", "audio_tmp"))
os.makedirs(STT_TMP_DIR, exist_ok=True)

# Перевіряємо існування файлу з ключами та виставляємо змінну для Google SDK
if STT_ENABLED and not GOOGLE_CREDENTIALS_PATH:
    raise RuntimeError("❌ GOOGLE_CREDENTIALS_PATH обов'язковий, коли STT_ENABLED=True")

if GOOGLE_CREDENTIALS_PATH:
    if not os.path.isfile(GOOGLE_CREDENTIALS_PATH):
        raise FileNotFoundError(
            f"❌ GOOGLE_CREDENTIALS_PATH не існує: {GOOGLE_CREDENTIALS_PATH}"
        )
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = GOOGLE_CREDENTIALS_PATH

