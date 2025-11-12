"""
mistral_api.py — простий клієнт для Mistral LLM API.
- Автоматично читає API-ключ з .env
- Має метод send_message() для відправки одного запиту
"""

import os
import requests
from dotenv import load_dotenv

# Завантажуємо .env (якщо ще не завантажено десь інде)
load_dotenv()


class MistralAPI:
    """
    Клас-обгортка для роботи з Mistral LLM через HTTP API.
    """

    def __init__(self, model: str | None = None):
        # Читаємо API-ключ та модель з .env
        self.api_key = os.getenv("MISTRAL_API_KEY")
        if not self.api_key:
            raise RuntimeError("❌ MISTRAL_API_KEY не знайдено в .env")

        self.model = model or os.getenv("MISTRAL_MODEL", "mistral-small-latest")

        # Базовий URL Mistral API (chat/completions)
        self.base_url = "https://api.mistral.ai/v1/chat/completions"

        # Заголовки для запитів
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def send_message(self, user_message: str, system_prompt: str | None = None) -> str:
        """
        Відправляє один запит до Mistral і повертає текст відповіді.
        - user_message: текст від користувача
        - system_prompt: необов'язковий system-повідомлення (роль бота, інструкції)
        """

        # Формуємо список повідомлень у форматі chat-completions
        messages = []
        if system_prompt:
            messages.append({
                "role": "system",
                "content": system_prompt,
            })

        messages.append({
            "role": "user",
            "content": user_message,
        })

        payload = {
            "model": self.model,
            "messages": messages,
            # можна тюнити:
            "temperature": 0.7,
            "max_tokens": 512,
        }

        print("🌐 Відправляю запит в Mistral...")
        try:
            response = requests.post(
                self.base_url,
                headers=self.headers,
                json=payload,
                timeout=30,  # таймаут на всяк випадок
            )
        except requests.exceptions.RequestException as e:
            print(f"❌ Помилка мережі при зверненні до Mistral: {e}")
            raise

        if response.status_code != 200:
            print(f"❌ Помилка від Mistral API: {response.status_code} {response.text}")
            raise RuntimeError(f"Mistral API error: {response.status_code}")

        data = response.json()

        # Очікуємо стандартну структуру відповіді: choices[0].message.content
        try:
            answer = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError) as e:
            print("❌ Неочікуваний формат відповіді від Mistral:", data)
            raise RuntimeError("Invalid Mistral response format") from e

        print("✅ Відповідь від Mistral отримано.")
        return answer