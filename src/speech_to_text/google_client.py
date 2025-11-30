"""Обгортка над Google Cloud Speech-to-Text."""

from dataclasses import dataclass
from typing import Any, Optional

from google.cloud import speech

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

    :param audio_bytes: підготовлений файл у форматі OGG_OPUS 48000Hz.
    :return: SpeechResult з текстом, мовою, впевненістю та сирою відповіддю.
    """

    audio = speech.RecognitionAudio(content=audio_bytes)
    response = _speech_client.recognize(config=_recognition_config, audio=audio)

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

