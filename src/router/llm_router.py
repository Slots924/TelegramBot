"""
llm_router.py — роутер, який зв'язує TelegramAPI та MistralAPI.

Отримує текст від користувача → викликає Mistral → надсилає відповідь у Telegram.
Поки що без історії, без summary, просто echo через LLM.
"""

from src.llm_api.mistral_api import MistralAPI
from src.telegram_api.telegram_api import TelegramAPI


class LLMRouter:
    """Простий роутер: прийняв повідомлення → запитав LLM → відповів у чат."""

    def __init__(self, telegram_api: TelegramAPI, llm_api: MistralAPI):
        self.telegram = telegram_api
        self.llm = llm_api

    async def handle_incoming_message(self, user_id: int, chat_id: int, text: str) -> None:
        """
        Головний метод:
        - отримує нове повідомлення,
        - шле текст у Mistral,
        - надсилає відповідь у той самий чат (НЕ як reply, просто нове повідомлення).
        """
        print(f"🧠 Обробляю повідомлення від {user_id}: {text}")

        try:
            # Викликаємо Mistral (синхронно, через HTTP)
            answer = self.llm.send_message(
                text,
                system_prompt="Ти асистент, який відповідає коротко і зрозуміло.",
            )
        except Exception as e:
            print(f"❌ Помилка при зверненні до LLM: {e}")
            answer = "Вибач, зараз я не можу відповісти 😔."

        # Відправляємо відповідь у Telegram у той самий чат (без reply_to)
        await self.telegram.send_message(chat_id, answer)