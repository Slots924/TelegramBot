"""
mistral_api.py — клієнт для Mistral LLM API.
"""

import requests
from .config import (
    MISTRAL_API_KEY,
    MISTRAL_BASE_URL,
    MISTRAL_MODEL,
    MISTRAL_TEMPERATURE,
    MISTRAL_MAX_TOKENS,
)


class MistralAPI:
    """Клієнт Mistral LLM."""

    BASE_URL = MISTRAL_BASE_URL

    def __init__(self):
        self.api_key = MISTRAL_API_KEY
        self.model = MISTRAL_MODEL
        self.temperature = MISTRAL_TEMPERATURE
        self.max_tokens = MISTRAL_MAX_TOKENS

        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def generate(self, messages: list[dict]) -> str:
        """
        Приймає повний список messages (system/user/assistant)
        і повертає текст відповіді.
        """

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }

        print("🌐 Надсилаю запит у Mistral...")

        resp = requests.post(
            self.BASE_URL,
            headers=self.headers,
            json=payload,
            timeout=30,
        )

        if resp.status_code != 200:
            raise RuntimeError(f"❌ Помилка Mistral API: {resp.text}")

        data = resp.json()
        answer = data["choices"][0]["message"]["content"]
        print("✅ Відповідь від Mistral отримано.")
        return answer
