"""Обгортка над Google Cloud Speech-to-Text."""

from dataclasses import dataclass
from typing import Any, Optional

from google.cloud import speech
from google.protobuf.json_format import MessageToJson

from .config import STT_ALT_LANGUAGES, STT_PRIMARY_LANGUAGE


@dataclass
class SpeechResult:
    """
    Простий контейнер з даними розпізнавання.

    :param text: фінальний текст розпізнавання.
    :param language: мова, яку обрав сервіс.
    :param confidence: рівень впевненості (0..1), може бути None якщо не надано.
    :param raw_response: сирі дані від Google для дебагу.
    """

    text: Optional[str]
    language: Optional[str]
    confidence: Optional[float]
    raw_response: Optional[Any] = None


# Підготовлений клієнт та конфіг, щоб не створювати їх щоразу
_speech_client = speech.SpeechClient()
_recognition_config = speech.RecognitionConfig(
    encoding=speech.RecognitionConfig.AudioEncoding.OGG_OPUS,
    sample_rate_hertz=48000,
    language_code=STT_PRIMARY_LANGUAGE,
    alternative_language_codes=STT_ALT_LANGUAGES,
    enable_automatic_punctuation=True,
)


def transcribe_bytes(audio_bytes: bytes) -> SpeechResult:
    """
    Відправляє байти аудіо у Google Speech-to-Text і повертає результат.

    :param audio_bytes: підготовлений файл OGG/OPUS (наприклад, з Telegram voice/round video).
    :return: SpeechResult з текстом, мовою, впевненістю та сирою відповіддю.
    """

    audio = speech.RecognitionAudio(content=audio_bytes)

    print(
        "📨 Готуємо запит до Google STT:",
        f"довжина байтів={len(audio_bytes)}",
        f"перші_32_байти={audio_bytes[:32]!r}",
    )

    print("=== STT НАЛАШТУВАННЯ ===")
    print("Encoding: OGG_OPUS")
    print("sample_rate_hertz: 48000")
    print(f"Основна мова: {_recognition_config.language_code}")
    print(f"Альтернативні: {_recognition_config.alternative_language_codes}\n")

    print("🚀 Відправляємо запит до Google STT через recognize()")
    try:
        response = _speech_client.recognize(config=_recognition_config, audio=audio)
    except Exception as exc:
        # Логуємо повну помилку, щоб розуміти, що саме відповів SDK/Google
        print("❌ Помилка під час виклику Google STT:", exc)
        raise

    print("✅ Запит до Google STT виконано, отримуємо відповідь")
    if not response.results:
        print("⚠️ Google STT повернув порожній список results")
        return SpeechResult(text=None, language=None, confidence=None, raw_response=response)

    first_result = response.results[0]
    if not first_result.alternatives:
        print("⚠️ У першому result немає alternatives, не вдалося отримати текст")
        return SpeechResult(text=None, language=None, confidence=None, raw_response=response)

    best_alternative = first_result.alternatives[0]
    language_code = first_result.language_code if hasattr(first_result, "language_code") else None

    print(
        "📊 Деталі першого результату STT:",
        f"transcript={best_alternative.transcript!r}",
        f"confidence={best_alternative.confidence if best_alternative.confidence else 'N/A'}",
        f"language_code={language_code}",
        f"alternatives_total={len(first_result.alternatives)}",
    )

    # Якщо є кілька альтернатив, логувати їх усі для дебагу
    if len(first_result.alternatives) > 1:
        print("=== Усі альтернативи Google STT ===")
        for index, alternative in enumerate(first_result.alternatives):
            print(
                f"#{index}: transcript={alternative.transcript!r} |",
                f"confidence={alternative.confidence if alternative.confidence else 'N/A'}",
            )
        print("=== Кінець списку альтернатив ===")

    print(
        "ℹ️ Коротка інформація по відповіді:",
        f"тип={type(response)}",
        f"results_count={len(response.results)}",
        f"перший_transcript={best_alternative.transcript!r}",
    )

    # Відображаємо сирий JSON у консоль, щоб легше діагностувати помилки
    try:
        raw_json = MessageToJson(response)
        print("=== RAW STT RESPONSE ===")
        print(raw_json)
        print("=== END RAW STT RESPONSE ===\n")
    except Exception as exc:
        print(f"⚠️ Не вдалося розпарсити відповідь STT у JSON: {exc}")

    return SpeechResult(
        text=best_alternative.transcript,
        language=language_code,
        confidence=best_alternative.confidence if best_alternative.confidence else None,
        raw_response=response,
    )
