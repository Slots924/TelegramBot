import requests
from .config import (
    MISTRAL_API_KEY,
    MISTRAL_MODEL,
    MISTRAL_TEMPERATURE,
    MISTRAL_MAX_TOKENS,
)


class MistralAPI:
    """Клієнт Mistral LLM."""

    BASE_URL = "https://api.mistral.ai/v1/chat/completions"

    def __init__(self):
        self.api_key = MISTRAL_API_KEY
        self.model = MISTRAL_MODEL
        self.temperature = MISTRAL_TEMPERATURE
        self.max_tokens = MISTRAL_MAX_TOKENS

        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def send_message(self, text: str, system_prompt: str | None = None) -> str:
        """
        Надсилає один запит у Mistral і повертає текст відповіді.
        БЛОКУЮЧА операція (requests), але для тестів це ок.
        """

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        messages.append({"role": "user", "content": text})

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