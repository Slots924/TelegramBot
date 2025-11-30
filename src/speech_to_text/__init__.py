"""Публічний інтерфейс модуля розпізнавання мовлення."""

from .google_client import SpeechResult
from .service import transcribe_voice

__all__ = ["SpeechResult", "transcribe_voice"]
