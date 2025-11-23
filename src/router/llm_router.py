"""Логіка LLMRouter — керування станами користувачів та виклики LLM."""

from __future__ import annotations

import asyncio
import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Awaitable, Callable, Dict, List, Optional, Sequence

from settings import (
    ACTIONS_SYSTEM_PROMPT,
    HISTORY_BASE_DIR,
    USER_INFO_FILENAME,
    USER_INFO_SYSTEM_PROMPT,
)
from src.config.settings import DEBOUNCE_SECONDS
from src.history.history_manager import HistoryManager
from src.llm_api.llm_api import LLMAPI
from src.llm_api.utils.loader import load_optional_prompt
from src.router.actions import (
    handle_add_reaction,
    handle_fake_typing,
    handle_ignore,
    handle_send_message,
)
from src.telegram_api.telegram_api import TelegramAPI


@dataclass
class UserState:
    """Стан одного користувача всередині роутера."""

    inbox: List["ReceivedMessage"] = field(default_factory=list)
    busy: bool = False
    last_activity: datetime | None = None
    debounce_task: asyncio.Task | None = None
    last_chat_id: int | None = None


@dataclass
class ReceivedMessage:
    """Описує вхідне повідомлення у внутрішній черзі."""

    text: str
    message_id: int | str | None
    message_time_iso: str | None


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
        self.actions_prompt: Optional[str] = None

        self._state: Dict[int, UserState] = {}
        # Реєстр доступних хендлерів для різних типів дій.
        self._action_handlers: Dict[
            str,
            Callable[
                [TelegramAPI, HistoryManager, int, int, dict, float],
                Awaitable[None],
            ],
        ] = {
            "send_message": handle_send_message,
            "add_reaction": handle_add_reaction,
            "fake_typing": handle_fake_typing,
            "ignore": handle_ignore,
        }

        # Завантажуємо додатковий промпт з інструкціями по екшенах (якщо він увімкнений).
        if ACTIONS_SYSTEM_PROMPT:
            self.actions_prompt = load_optional_prompt("actions")

    async def handle_incoming_message(
        self,
        user_id: int,
        chat_id: int,
        text: str,
        message_id: int | str | None,
        message_time: datetime,
    ) -> None:
        """Реєструє нове повідомлення та за потреби запускає debounce."""

        state = self._get_state(user_id)
        message_time_iso = message_time.astimezone(timezone.utc).isoformat()
        state.inbox.append(
            ReceivedMessage(
                text=text,
                message_id=message_id,
                message_time_iso=message_time_iso,
            )
        )
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
                self.history.append_message(
                    user_id=user_id,
                    role="user",
                    content=message.text,
                    message_id=message.message_id,
                    message_time_iso=message.message_time_iso,
                )

            messages_for_llm = self._build_llm_messages(user_id=user_id)

            try:
                answer_raw = await asyncio.to_thread(self.llm.generate, messages_for_llm)
            except Exception as exc:
                print(f"❌ Помилка при виклику LLM для {user_id}: {exc}")
                answer_raw = "[]"


                 # 🔍 Дебаг: подивитись сирий респонс від LLM у консолі
            print("\n================= RAW LLM RESPONSE =================")
            try:
                parsed = json.loads(answer_raw)
                pretty = json.dumps(parsed, ensure_ascii=False, indent=2)
                print(pretty)
            except Exception:
                # Якщо це не валідний JSON – просто друкуємо як є
                print(answer_raw)
            print("====================================================\n")
            

            actions = self._parse_actions(answer_raw)
            await self._execute_actions(chat_id=chat_id, user_id=user_id, actions=actions)
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

    def _build_llm_messages(self, user_id: int) -> List[dict]:
        """Формує список повідомлень для LLM з урахуванням системних промптів та історії."""

        messages_for_llm: List[dict] = [{"role": "system", "content": self.system_prompt}]

        # Додаємо інструкцію про actions, якщо вона увімкнена та файл існує.
        if ACTIONS_SYSTEM_PROMPT and self.actions_prompt:
            messages_for_llm.append({"role": "system", "content": self.actions_prompt})

        # Підхоплюємо user_info.txt як системний промпт, якщо цього вимагають налаштування.
        if USER_INFO_SYSTEM_PROMPT:
            user_info_content = self._load_user_info_prompt(user_id)
            if user_info_content:
                messages_for_llm.append({"role": "system", "content": user_info_content})

        history_messages = self.history.get_recent_context(user_id)
        for item in history_messages:
            role = item.get("role")
            content = item.get("content")
            if not role or content is None:
                continue

            formatted_content = self._format_history_content(
                content=content,
                created_at=item.get("created_at"),
                message_id=item.get("message_id"),
            )
            messages_for_llm.append({"role": role, "content": formatted_content})

        return messages_for_llm

    def _load_user_info_prompt(self, user_id: int) -> Optional[str]:
        """Читає user_info.txt і повертає його вміст як системний промпт."""

        user_dir = os.path.join(HISTORY_BASE_DIR, f"user_{user_id}")
        user_info_path = os.path.join(user_dir, USER_INFO_FILENAME)

        if not os.path.exists(user_info_path):
            return None

        try:
            with open(user_info_path, "r", encoding="utf-8") as file:
                data = json.load(file)
            # Передаємо LLM короткий системний блок із даними профілю.
            return f"USER_INFO\n{json.dumps(data, ensure_ascii=False, indent=2)}"
        except Exception as exc:
            print(f"⚠️ Не вдалося прочитати user_info.txt для {user_id}: {exc}")
            return None

    @staticmethod
    def _format_history_content(
        content: str,
        created_at: Optional[str],
        message_id: Optional[int | str],
    ) -> str:
        """Додає до тексту повідомлення метадані, щоб LLM бачила час та message_id."""

        meta_parts: List[str] = []
        if created_at:
            meta_parts.append(f"sent_at={created_at}")
        if message_id:
            meta_parts.append(f"message_id={message_id}")

        if not meta_parts:
            return content

        meta_header = " | ".join(meta_parts)
        return f"[{meta_header}]\n{content}"

    @staticmethod
    def _parse_actions(answer_raw: str) -> List[dict]:
        """Парсить відповідь LLM у список дій. Повертає send_message з текстом, якщо JSON некоректний."""

        try:
            data = json.loads(answer_raw)
            if isinstance(data, dict):
                data = [data]
            if not isinstance(data, Sequence):
                raise ValueError("Відповідь не є масивом дій")
            actions: List[dict] = []
            for raw_action in data:
                if isinstance(raw_action, dict):
                    actions.append(raw_action)
                else:
                    print(f"ℹ️ Пропускаю елемент відповіді, бо він не dict: {raw_action}")
            return actions
        except Exception as exc:
            print(f"⚠️ Не вдалося розпарсити дії LLM: {exc}. Використовую просте send_message.")
            return [
                {
                    "type": "send_message",
                    "wait_seconds": 0,
                    "human_seconds": 0,
                    "payload": {"content": answer_raw},
                }
            ]

    async def _execute_actions(
        self, chat_id: int, user_id: int, actions: Sequence[dict]
    ) -> None:
        """По черзі виконує екшени, які повернула LLM, враховуючи затримку wait_seconds."""

        for action in actions:
            action_type = action.get("type")
            payload = action.get("payload") or {}
            wait_seconds = float(action.get("wait_seconds", 0) or 0)
            human_seconds = float(action.get("human_seconds", 0) or 0)

            handler = self._action_handlers.get(action_type)

            if not handler:
                # Невідомий тип — просто пропускаємо, щоб не ламати сценарій.
                print(f"ℹ️ Невідомий тип дії від LLM: {action_type}. Пропускаю.")
                continue

            if wait_seconds > 0:
                # Перед виконанням будь-якої дії робимо просту паузу, якщо її вимагає LLM.
                await asyncio.sleep(wait_seconds)

            await handler(
                telegram=self.telegram,
                history=self.history,
                chat_id=chat_id,
                user_id=user_id,
                payload=payload,
                human_seconds=human_seconds,
            )
