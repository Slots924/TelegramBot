"""Логіка LLMRouter — керування станами користувачів та виклики LLM."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List

from src.config.settings import DEBOUNCE_SECONDS, get_typing_duration
from src.history.history_manager import HistoryManager
from src.llm_api.llm_api import LLMAPI
from src.telegram_api.telegram_api import TelegramAPI


@dataclass
class UserState:
    """Стан одного користувача всередині роутера."""

    inbox: List[str] = field(default_factory=list)
    busy: bool = False
    last_activity: datetime | None = None
    debounce_task: asyncio.Task | None = None
    last_chat_id: int | None = None


class LLMRouter:
    """Роутер, який пов'язує Telegram, історію та LLM (Grok 4 Fast)."""

    def __init__(
        self,
        telegram_api: TelegramAPI,
        llm_api: LLMAPI,
        history_manager: HistoryManager,
        system_prompt: str,
    ) -> None:
        """Зберігає залежності й готує словник станів користувачів."""

        self.telegram = telegram_api
        self.llm = llm_api
        self.history = history_manager
        self.system_prompt = system_prompt

        self._state: Dict[int, UserState] = {}

    async def handle_incoming_message(self, user_id: int, chat_id: int, text: str) -> None:
        """Реєструє нове повідомлення та за потреби запускає debounce."""

        state = self._get_state(user_id)
        state.inbox.append(text)
        state.last_activity = datetime.now(timezone.utc)
        state.last_chat_id = chat_id
        print(f"🧠 Додано повідомлення від {user_id}: {text}")

        if state.busy:
            print(f"⏳ Користувач {user_id} вже обробляється. Чекаємо завершення поточного циклу.")
            return

        if state.debounce_task and not state.debounce_task.done():
            print(f"⌚ Debounce вже запущений для {user_id} — новий не стартує.")
            return

        self._start_debounce(user_id, chat_id)

    def _get_state(self, user_id: int) -> UserState:
        """Повертає (або створює) стан користувача."""

        if user_id not in self._state:
            self._state[user_id] = UserState()
        return self._state[user_id]

    def _start_debounce(self, user_id: int, chat_id: int) -> None:
        """Створює asyncio-задачу debounce для конкретного користувача."""

        state = self._get_state(user_id)
        if state.debounce_task and not state.debounce_task.done():
            return

        state.debounce_task = asyncio.create_task(
            self._debounce_and_start_cycle(user_id, chat_id)
        )

    async def _debounce_and_start_cycle(self, user_id: int, chat_id: int) -> None:
        """Чекає DEBOUNCE_SECONDS, потім запускає цикл діалогу."""

        try:
            await asyncio.sleep(DEBOUNCE_SECONDS)
            state = self._get_state(user_id)
            state.debounce_task = None
            target_chat_id = state.last_chat_id or chat_id
            if not target_chat_id:
                print(f"⚠️ Немає chat_id для користувача {user_id}. Пропускаю цикл.")
                return
            await self._run_dialog_cycle(user_id, target_chat_id)
        except asyncio.CancelledError:
            print(f"🛑 Debounce скасовано для користувача {user_id}.")
            raise
        except Exception as exc:
            print(f"❌ Помилка у debounce для {user_id}: {exc}")

    async def _run_dialog_cycle(self, user_id: int, chat_id: int) -> None:
        """Основний цикл: історія → Grok → typing → відправка відповіді."""

        state = self._get_state(user_id)
        if not state.inbox:
            print(f"📭 Inbox порожній для {user_id}, нічого обробляти.")
            state.busy = False
            return

        state.busy = True
        try:
            batch_messages = list(state.inbox)
            state.inbox.clear()
            print(f"📦 Пакет із {len(batch_messages)} повідомлень для користувача {user_id}.")

            for message in batch_messages:
                self.history.append_message(user_id=user_id, role="user", content=message)

            history_messages = self.history.get_recent_context(user_id)
            messages_for_llm: List[dict] = [
                {"role": "system", "content": self.system_prompt}
            ]
            for item in history_messages:
                role = item.get("role")
                content = item.get("content")
                if not role or content is None:
                    continue
                messages_for_llm.append({"role": role, "content": content})

            try:
                answer = await asyncio.to_thread(self.llm.generate, messages_for_llm)
            except Exception as exc:
                print(f"❌ Помилка при виклику LLM для {user_id}: {exc}")
                answer = "Вибач, зараз я не можу відповісти. Спробуй пізніше."

            self.history.append_message(user_id=user_id, role="assistant", content=answer)

            typing_duration = get_typing_duration(answer)
            print(f"⌨️ Імітую набір {typing_duration} с для користувача {user_id}.")
            await self.telegram.send_typing(chat_id, typing_duration)

            try:
                await self.telegram.send_message(chat_id, answer)
                print(f"✅ Відповідь відправлена користувачу {user_id}.")
            except Exception as exc:
                print(f"❌ Не вдалося відправити повідомлення користувачу {user_id}: {exc}")
        finally:
            state.busy = False
        if state.inbox:
            print(
                f"🔁 Після відповіді у {user_id} залишилися нові повідомлення. Запускаю новий debounce."
            )
            next_chat_id = state.last_chat_id or chat_id
            if next_chat_id:
                self._start_debounce(user_id, next_chat_id)
            else:
                print(
                    f"⚠️ Не вдалося визначити chat_id для нового циклу користувача {user_id}."
                )
        else:
            print(f"🟢 Цикл завершено для {user_id}.")
