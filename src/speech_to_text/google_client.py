"""Обгортка над Google Cloud Speech-to-Text."""

import os
import time
import traceback
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

    print("=== STT НАЛАШТУВАННЯ ===")
    print("Encoding: OGG_OPUS")
    print("sample_rate_hertz: 48000")
    print(f"Основна мова: {_recognition_config.language_code}")
    print(f"Альтернативні: {_recognition_config.alternative_language_codes}\n")

    credentials_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    print(f"Credentials path: {credentials_path}")

    start_time = time.perf_counter()
    response = _speech_client.recognize(config=_recognition_config, audio=audio)
    elapsed = time.perf_counter() - start_time
    results_count = len(getattr(response, "results", [])) if response else 0
    alternatives_count = (
        len(response.results[0].alternatives)
        if response and getattr(response, "results", None)
        else 0
    )

    print(
        f"⏱️ Google STT виклик завершено за {elapsed:.2f}s: results={results_count}, "
        f"alternatives_first={alternatives_count}"
    )

    # Відображаємо сирий JSON у консоль, щоб легше діагностувати помилки
    try:
        raw_json = MessageToJson(response)
        print("=== RAW STT RESPONSE ===")
        print(raw_json)
        print("=== END RAW STT RESPONSE ===\n")
    except Exception as exc:
        print(f"⚠️ Не вдалося розпарсити відповідь STT у JSON: {exc}")
        print(traceback.format_exc())

    if not response.results:
        return SpeechResult(text=None, language=None, confidence=None, raw_response=response)

    first_result = response.results[0]
    if not first_result.alternatives:
        return SpeechResult(text=None, language=None, confidence=None, raw_response=response)

    best_alternative = first_result.alternatives[0]
    language_code = first_result.language_code if hasattr(first_result, "language_code") else None

    return SpeechResult(
        text=best_alternative.transcript,
        language=language_code,
        confidence=best_alternative.confidence if best_alternative.confidence else None,
        raw_response=response,
    )
