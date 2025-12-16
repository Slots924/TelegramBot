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
        print("⚙️ STT вимкнено через конфіг, повертаємо порожній результат")
        return SpeechResult(text=None, language=None, confidence=None, raw_response=None)

    temp_files: list[str] = []

    # Створюємо безпечний ліміт для обрізки (не більше STT_MAX_SECONDS)
    # Телеграм інколи не передає duration для voice, тому підставляємо максимально
    # дозволену тривалість, щоб не обрізати файл у «0 секунд» та не псувати аудіо.
    declared_duration = float(duration_seconds) if duration_seconds else float(STT_MAX_SECONDS)
    safe_duration = min(declared_duration, float(STT_MAX_SECONDS))
    print(
        "⌛️ Отримано голосове повідомлення",
        f"len={len(audio_bytes)} байт,",
        f"declared_duration={declared_duration}s,",
        f"safe_duration={safe_duration}s",
    )

    try:
        # Готуємо аудіо: зберегти → за потреби обрізати → відправити як OGG/OPUS
        prepared_bytes, temp_files = audio_utils.prepare_audio_bytes(
            audio_input=audio_bytes,
            duration_seconds=safe_duration,
        )

        print(
            "✅ Аудіо підготовлено до STT",
            f"готовий розмір={len(prepared_bytes)} байт",
            f"тимчасові файли={temp_files}",
        )

        # Відправляємо у Google STT
        result = transcribe_bytes(prepared_bytes)
        print(
            "🤖 Результат STT",
            f"text={result.text!r}",
            f"language={result.language}",
            f"confidence={result.confidence}",
        )
        return result
    finally:
        # Після успішного виклику обов'язково прибираємо тимчасові файли
        print(f"🧹 Видаляємо тимчасові файли після STT: {temp_files}")
        audio_utils.cleanup_temp_files(temp_files)

