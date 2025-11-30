"""Публічний сервіс для розпізнавання голосу без залежності від Telegram."""

from . import audio_utils
from .config import STT_ENABLED, STT_MAX_SECONDS
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
    safe_duration = min(float(duration_seconds), float(STT_MAX_SECONDS))

    try:
        # Готуємо аудіо: зберегти → обрізати → конвертувати у потрібний формат
        prepared_bytes, temp_files = audio_utils.prepare_audio_bytes(
            audio_input=audio_bytes,
            duration_seconds=safe_duration,
        )

        # Відправляємо у Google STT
        result = transcribe_bytes(prepared_bytes)
        return result
    finally:
        # Після успішного виклику обов'язково прибираємо тимчасові файли
        audio_utils.cleanup_temp_files(temp_files)

