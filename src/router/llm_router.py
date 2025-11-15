"""
llm_router.py — роутер, який зв'язує TelegramAPI, HistoryManager та MistralAPI.

Логіка:
- отримує нове повідомлення від користувача
- записує його в історію
- завантажує system prompt з файлу (залежно від налаштувань)
- будує messages (system + історія user/assistant)
- викликає Mistral
- зберігає відповідь в історію
- надсилає відповідь у Telegram (НЕ як reply)
"""

import os

from src.llm_api.mistral_api import MistralAPI
from src.llm_api.config import SYSTEM_PROMPTS_DIR, SYSTEM_PROMPT_NAME
from src.telegram_api.telegram_api import TelegramAPI
from src.history.history_manager import HistoryManager


class LLMRouter:
    def __init__(
        self,
        telegram_api: TelegramAPI,
        llm_api: MistralAPI,
        history_manager: HistoryManager,
    ):
        self.telegram = telegram_api
        self.llm = llm_api
        self.history = history_manager

        # Завантажуємо system prompt з файлу
        self.system_prompt = self._load_system_prompt()

    def _load_system_prompt(self) -> str:
        """
        Читає файл з системним промптом із папки system_prompts.
        Ім'я файлу береться з SYSTEM_PROMPT_NAME (без .txt).
        """
        filename = f"{SYSTEM_PROMPT_NAME}.txt"
        path = os.path.join(SYSTEM_PROMPTS_DIR, filename)

        try:
            with open(path, "r", encoding="utf-8") as f:
                prompt = f.read().strip()
                print(f"📄 Завантажено system prompt: {filename}")
                return prompt
        except FileNotFoundError:
            print(f"⚠️ Файл системного промпта не знайдено: {path}")
            # fallback — простий дефолт
            return "Ти асистент. Відповідай коротко і зрозуміло."

    async def handle_incoming_message(self, user_id: int, chat_id: int, text: str) -> None:
        """
        Головний метод:
        - додає user-повідомлення в історію
        - дістає "хвіст" історії
        - формує messages (system + історія)
        - викликає LLM
        - додає assistant-повідомлення в історію
        - надсилає відповідь у Telegram
        """
        print(f"🧠 Обробляю повідомлення від {user_id}: {text}")

        # 1) Зберігаємо вхідне повідомлення користувача
        self.history.append_message(
            user_id=user_id,
            role="user",
            content=text,
        )

        # 2) Беремо "хвіст" історії
        history_messages = self.history.get_recent_context(user_id)

        # 3) Формуємо messages для LLM
        messages_for_llm: list[dict] = []

        # system
        messages_for_llm.append({
            "role": "system",
            "content": self.system_prompt,
        })

        # історія user/assistant
        for m in history_messages:
            role = m.get("role")
            content = m.get("content")
            if not role or not content:
                continue
            messages_for_llm.append({
                "role": role,
                "content": content,
            })

        # 4) Викликаємо LLM
        try:
            answer = self.llm.generate(messages_for_llm)
        except Exception as e:
            print(f"❌ Помилка при зверненні до LLM: {e}")
            answer = "Вибач, зараз я не можу відповісти 😔."

        # 5) Зберігаємо відповідь асистента в історію
        self.history.append_message(
            user_id=user_id,
            role="assistant",
            content=answer,
        )

        # 6) Надсилаємо відповідь у той самий чат (без reply)
        await self.telegram.send_message(chat_id, answer)
