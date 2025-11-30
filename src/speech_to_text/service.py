"""Публічний сервіс для розпізнавання голосу без залежності від Telegram."""

import os
import time

from . import audio_utils
from .config import (
    STT_ALT_LANGUAGES,
    STT_ENABLED,
    STT_MAX_SECONDS,
    STT_PRIMARY_LANGUAGE,
)
from .google_client import SpeechResult, transcribe_bytes


def transcribe_voice(audio_bytes: bytes, duration_seconds: float | int) -> SpeechResult:
    """
    Приймає сирі байти аудіо, готує їх та відправляє в Google STT.

    :param audio_bytes: вхідне аудіо (наприклад, з Telegram voice) у байтах.
    :param duration_seconds: заявлена тривалість повідомлення у секундах.
    :return: SpeechResult з текстом, мовою та впевненістю.
    """

    # Якщо розпізнавання вимкнено, повертаємо пустий результат
    if not STT_ENABLED:
        return SpeechResult(text=None, language=None, confidence=None, raw_response=None)

    temp_files: list[str] = []

    # Створюємо безпечний ліміт для обрізки (не більше STT_MAX_SECONDS)
    # Телеграм інколи не передає duration для voice, тому підставляємо максимально
    # дозволену тривалість, щоб не обрізати файл у «0 секунд» та не псувати аудіо.
    declared_duration = float(duration_seconds) if duration_seconds else float(STT_MAX_SECONDS)
    safe_duration = min(declared_duration, float(STT_MAX_SECONDS))

    credentials_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")

    try:
        # Готуємо аудіо: зберегти → за потреби обрізати → відправити як OGG/OPUS
        prepared_bytes, temp_files = audio_utils.prepare_audio_bytes(
            audio_input=audio_bytes,
            duration_seconds=safe_duration,
        )

        print(
            "🎯 STT виклик підготовлено: bytes_len={blen}, safe_duration={sdur}, "
            "primary_lang={primary}, alt_langs={alt}, creds={creds}".format(
                blen=len(prepared_bytes),
                sdur=safe_duration,
                primary=STT_PRIMARY_LANGUAGE,
                alt=STT_ALT_LANGUAGES,
                creds=credentials_path,
            )
        )

        # Відправляємо у Google STT
        start_time = time.perf_counter()
        result = transcribe_bytes(prepared_bytes)
        elapsed = time.perf_counter() - start_time

        raw_response = getattr(result, "raw_response", None)
        results_count = len(getattr(raw_response, "results", [])) if raw_response else 0
        first_alternatives = (
            len(raw_response.results[0].alternatives)
            if raw_response and getattr(raw_response, "results", None)
            else 0
        )

        print(
            f"⏱️ STT завершено за {elapsed:.2f}s: results={results_count}, alternatives_first={first_alternatives}"
        )
        return result
    finally:
        # Після успішного виклику обов'язково прибираємо тимчасові файли
        audio_utils.cleanup_temp_files(temp_files)

