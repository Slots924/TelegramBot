"""
llm_api.py — універсальний клієнт для LLM API.
"""

import requests
from .config import (
    LLM_API_KEY,
    LLM_BASE_URL,
    LLM_MODEL,
    LLM_TEMPERATURE,
    LLM_MAX_TOKENS,
    LLM_TOP_P,
)


class LLMAPI:
    """Клієнт для взаємодії з LLM."""

    BASE_URL = LLM_BASE_URL

    def __init__(self):
        self.api_key = LLM_API_KEY
        self.model = LLM_MODEL
        self.temperature = LLM_TEMPERATURE
        self.max_tokens = LLM_MAX_TOKENS

        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "LLM_TOP_P": str(LLM_TOP_P),
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
            # LLM_TOP_P використовуємо у headers і тілі; решта пенальті поки не потрібні
            "top_p": LLM_TOP_P,
        }

        print("🌐 Надсилаю запит у LLM...")

        resp = requests.post(
            self.BASE_URL,
            headers=self.headers,
            json=payload,
            timeout=30,
        )

        if resp.status_code != 200:
            raise RuntimeError(f"❌ Помилка LLM API: {resp.text}")

        data = resp.json()
        answer = data["choices"][0]["message"]["content"]
        print("✅ Відповідь від LLM отримано.")
        return answer
