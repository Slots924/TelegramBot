"""Конфігурація для сервісу розпізнавання мовлення."""

import os

from settings import (
    FFMPEG_PATH as SETTINGS_FFMPEG_PATH,
    GOOGLE_CREDENTIALS_PATH,
    STT_ALT_LANGUAGES,
    STT_ENABLED,
    STT_MAX_SECONDS,
    STT_PRIMARY_LANGUAGE,
    STT_TMP_DIR,
)

# Тимчасова директорія для проміжних файлів
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

# Опціональний шлях до ffmpeg, який можна задати через settings.py або змінну оточення
FFMPEG_PATH: str | None = SETTINGS_FFMPEG_PATH
