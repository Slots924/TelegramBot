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
    DEBOUNCE_SECONDS,
    HISTORY_BASE_DIR,
    USER_INFO_FILENAME,
    USER_INFO_SYSTEM_PROMPT,
)
from src.history.history_manager import HistoryManager
from src.llm_api.llm_api import LLMAPI
from src.llm_api.utils.loader import load_optional_prompt
from src.speech_to_text import SpeechResult, transcribe_voice
from src.router.actions import (
    handle_add_reaction,
    handle_fake_typing,
    handle_ignore,
    handle_send_messages,
    handle_send_message,
    handle_wait,
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
    """Описує вхідне повідомлення у внутрішній черзі з типом та метаданими."""

    content: str
    msg_type: str
    media_meta: dict | None
    message_time_iso: str | None
    message_id: int | None


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
            "send_messages": handle_send_messages,
            "add_reaction": handle_add_reaction,
            "react_to_message": handle_add_reaction,
            "fake_typing": handle_fake_typing,
            "ignore": handle_ignore,
            "wait": handle_wait,
        }

        # Завантажуємо додатковий промпт з інструкціями по екшенах (якщо він увімкнений).
        if ACTIONS_SYSTEM_PROMPT:
            self.actions_prompt = load_optional_prompt("actions")

    async def handle_incoming_message(
        self,
        user_id: int,
        chat_id: int,
        content: str,
        msg_type: str,
        media_meta: dict | None,
        message_time: datetime,
        message_id: int | None = None,
    ) -> None:
        """Реєструє нове повідомлення та за потреби запускає debounce.

        content вже містить стислий опис медіа (для не тексту), msg_type визначає
        тип повідомлення, а message_id передаємо, щоб зберегти у історії точний
        зв'язок із Telegram.
        """

        handlers_map = {
            "text": self._handle_text_message,
            "voice": self._handle_voice_message,
            "audio": self._handle_audio_message,
            "video_note": self._handle_video_note_message,
            "video": self._handle_video_message,
            "document": self._handle_document_message,
            "photo": self._handle_photo_message,
        }

        handler = handlers_map.get(msg_type, self._handle_text_message)
        await handler(
            user_id=user_id,
            chat_id=chat_id,
            content=content,
            media_meta=media_meta,
            message_time=message_time,
            message_id=message_id,
            msg_type=msg_type,
        )
        self._maybe_start_processing(user_id=user_id, chat_id=chat_id)

    async def _handle_text_message(
        self,
        user_id: int,
        chat_id: int,
        content: str,
        media_meta: dict | None,
        message_time: datetime,
        message_id: int | None,
        msg_type: str,
    ) -> None:
        """Обробляє текстове повідомлення і додає його у внутрішній буфер."""

        self._register_inbox_message(
            user_id=user_id,
            chat_id=chat_id,
            content=content,
            msg_type=msg_type,
            media_meta=media_meta,
            message_time=message_time,
            message_id=message_id,
        )

    async def _handle_voice_message(
        self,
        user_id: int,
        chat_id: int,
        content: str,
        media_meta: dict | None,
        message_time: datetime,
        message_id: int | None,
        msg_type: str,
    ) -> None:
        """Завантажує voice, пробує його розпізнати та кладе у буфер історії.

        Параметри
        ----------
        user_id: int
            Ідентифікатор користувача, для якого ведемо історію.
        chat_id: int
            Чат, з якого прийшло голосове повідомлення (потрібен для завантаження файла).
        content: str
            Початковий опис voice з TelegramAPI (потрібен лише для сумісності сигнатури).
        media_meta: dict | None
            Метадані voice (тривалість, file_id тощо), доповнюються інформацією про транскрипцію.
        message_time: datetime
            Час надходження повідомлення для збереження у історії.
        message_id: int | None
            ID повідомлення в Telegram (використовуємо, щоб завантажити файл).
        msg_type: str
            Тип повідомлення ("voice").
        """

        duration_seconds = (media_meta or {}).get("duration")
        duration_label = duration_seconds if duration_seconds is not None else "unknown"

        # Базовий текст на випадок помилок або відсутності транскрипції.
        prepared_text = (
            f"[VOICE_MESSAGE duration={duration_label}s transcribed=NO]\n"
            "Користувач надіслав голосове повідомлення, але розпізнати текст не вдалося."
        )

        # Копія метаданих, щоб додати інформацію про транскрипцію/помилки.
        safe_media_meta = dict(media_meta or {})

        try:
            voice_bytes = await self.telegram.download_voice_bytes(
                chat_id=chat_id,
                message_id=message_id,
                file_id=safe_media_meta.get("file_id"),
            )
        except Exception as exc:
            print(
                f"⚠️ Неочікувана помилка під час завантаження voice message_id={message_id}: {exc}"
            )
            voice_bytes = None

        if voice_bytes:
            try:
                # Виконуємо розпізнавання у окремому потоці, щоб не блокувати event-loop.
                speech_result: SpeechResult = await asyncio.to_thread(
                    transcribe_voice, voice_bytes, duration_seconds or 0
                )

                if speech_result and speech_result.text:
                    cleaned_text = speech_result.text.strip()
                    prepared_text = (
                        f"[VOICE_MESSAGE duration={duration_label}s transcribed=YES]\n"
                        f"Транскрипція:\n\"{cleaned_text}\""
                    )
                    safe_media_meta.update(
                        {
                            "transcription": cleaned_text,
                            "transcription_language": speech_result.language,
                            "transcription_confidence": speech_result.confidence,
                        }
                    )
                else:
                    safe_media_meta["transcription_error"] = "empty_text"
            except Exception as exc:
                # Логуємо, але залишаємо fallback-текст.
                print(
                    f"⚠️ Помилка розпізнавання voice message_id={message_id} у чаті {chat_id}: {exc}"
                )
                safe_media_meta["transcription_error"] = str(exc)
        else:
            safe_media_meta["download_error"] = "voice_download_failed"
            print(
                f"⚠️ Не вдалося завантажити голосове повідомлення message_id={message_id} у чаті {chat_id}."
            )

        self._register_inbox_message(
            user_id=user_id,
            chat_id=chat_id,
            content=prepared_text,
            msg_type=msg_type,
            media_meta=safe_media_meta,
            message_time=message_time,
            message_id=message_id,
        )

    async def _handle_audio_message(
        self,
        user_id: int,
        chat_id: int,
        content: str,
        media_meta: dict | None,
        message_time: datetime,
        message_id: int | None,
        msg_type: str,
    ) -> None:
        """Обробляє музичні файли/аудіотреки."""

        self._register_inbox_message(
            user_id=user_id,
            chat_id=chat_id,
            content=content,
            msg_type=msg_type,
            media_meta=media_meta,
            message_time=message_time,
            message_id=message_id,
        )

    async def _handle_video_note_message(
        self,
        user_id: int,
        chat_id: int,
        content: str,
        media_meta: dict | None,
        message_time: datetime,
        message_id: int | None,
        msg_type: str,
    ) -> None:
        """Обробляє круглі відео (video_note)."""

        self._register_inbox_message(
            user_id=user_id,
            chat_id=chat_id,
            content=content,
            msg_type=msg_type,
            media_meta=media_meta,
            message_time=message_time,
            message_id=message_id,
        )

    async def _handle_video_message(
        self,
        user_id: int,
        chat_id: int,
        content: str,
        media_meta: dict | None,
        message_time: datetime,
        message_id: int | None,
        msg_type: str,
    ) -> None:
        """Обробляє відеофайли, що прийшли від користувача."""

        self._register_inbox_message(
            user_id=user_id,
            chat_id=chat_id,
            content=content,
            msg_type=msg_type,
            media_meta=media_meta,
            message_time=message_time,
            message_id=message_id,
        )

    async def _handle_document_message(
        self,
        user_id: int,
        chat_id: int,
        content: str,
        media_meta: dict | None,
        message_time: datetime,
        message_id: int | None,
        msg_type: str,
    ) -> None:
        """Обробляє документи (PDF, DOC тощо)."""

        self._register_inbox_message(
            user_id=user_id,
            chat_id=chat_id,
            content=content,
            msg_type=msg_type,
            media_meta=media_meta,
            message_time=message_time,
            message_id=message_id,
        )

    async def _handle_photo_message(
        self,
        user_id: int,
        chat_id: int,
        content: str,
        media_meta: dict | None,
        message_time: datetime,
        message_id: int | None,
        msg_type: str,
    ) -> None:
        """Обробляє фотографії."""

        self._register_inbox_message(
            user_id=user_id,
            chat_id=chat_id,
            content=content,
            msg_type=msg_type,
            media_meta=media_meta,
            message_time=message_time,
            message_id=message_id,
        )

    def _register_inbox_message(
        self,
        user_id: int,
        chat_id: int,
        content: str,
        msg_type: str,
        media_meta: dict | None,
        message_time: datetime,
        message_id: int | None,
    ) -> None:
        """Зберігає вхідне повідомлення у черзі та оновлює стан."""

        state = self._get_state(user_id)
        message_time_iso = message_time.astimezone(timezone.utc).isoformat()
        state.inbox.append(
            ReceivedMessage(
                content=content,
                msg_type=msg_type,
                media_meta=media_meta or {},
                message_time_iso=message_time_iso,
                message_id=message_id,
            )
        )
        state.last_activity = datetime.now(timezone.utc)
        state.last_chat_id = chat_id
        print(f"🧠 Додано повідомлення від {user_id} ({msg_type}): {content}")

    def _maybe_start_processing(self, user_id: int, chat_id: int) -> None:
        """Приймає рішення, чи потрібно запускати debounce/цикл обробки."""

        state = self._get_state(user_id)

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
                    content=message.content,
                    message_time_iso=message.message_time_iso,
                    message_id=message.message_id,
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

    async def trigger_proactive_message(
        self, user_id: int, chat_id: int, instruction: str = "Напиши повідомлення цьому користувачу"
    ) -> None:
        """Запускає LLM без нового вхідного тексту, щоб модель сама згенерувала дії."""

        messages_for_llm = self._build_llm_messages(user_id=user_id)
        proactive_instruction = (
            "Система ініціює контакт із користувачем без нового повідомлення. "
            "Згенеруй список дій у JSON-форматі (send_message, send_messages, fake_typing, add_reaction, ignore), "
            "щоб написати релевантне повідомлення користувачу. "
            f"{instruction}"
        )
        messages_for_llm.append({"role": "system", "content": proactive_instruction})

        try:
            answer_raw = await asyncio.to_thread(self.llm.generate, messages_for_llm)
        except Exception as exc:
            print(f"❌ Помилка при виклику LLM (proactive) для {user_id}: {exc}")
            answer_raw = "[]"

        print("\n================= RAW LLM RESPONSE (proactive) =================")
        try:
            parsed = json.loads(answer_raw)
            pretty = json.dumps(parsed, ensure_ascii=False, indent=2)
            print(pretty)
        except Exception:
            print(answer_raw)
        print("==============================================================\n")

        actions = self._parse_actions(answer_raw)
        await self._execute_actions(chat_id=chat_id, user_id=user_id, actions=actions)

    async def send_single_message_proactively(
        self,
        user_id: int,
        chat_id: int,
        instruction: str = "Згенеруй одне дружнє повідомлення для користувача",
    ) -> None:
        """Просить LLM створити JSON із однією дією надсилання повідомлення і виконує її.

        Використовується в адмін-консолі, коли хочемо ініціювати діалог без нового
        вхідного тексту. Метод не чіпає внутрішній стан inbox/debounce, тому після
        виконання дій цикл слухання не запускається.
        """

        messages_for_llm = self._build_llm_messages(user_id=user_id)
        proactive_instruction = (
            "Система сама ініціює контакт із користувачем. Сформуй JSON-дії зі списку\n"
            "[send_message, send_messages, fake_typing] так, щоб у підсумку було відправлене\n"
            "хоча б одне текстове повідомлення. Не запускай очікування нових вхідних,\n"
            "не додавай інструкцій для нескінченного циклу. "
            f"{instruction}"
        )
        messages_for_llm.append({"role": "system", "content": proactive_instruction})

        try:
            answer_raw = await asyncio.to_thread(self.llm.generate, messages_for_llm)
        except Exception as exc:
            print(f"❌ Помилка при виклику LLM (admin proactive) для {user_id}: {exc}")
            answer_raw = "[]"

        print("\n================= RAW LLM RESPONSE (admin proactive) =================")
        try:
            parsed = json.loads(answer_raw)
            pretty = json.dumps(parsed, ensure_ascii=False, indent=2)
            print(pretty)
        except Exception:
            print(answer_raw)
        print("====================================================================\n")

        actions = self._parse_actions(answer_raw)
        await self._execute_actions(chat_id=chat_id, user_id=user_id, actions=actions)

    async def sync_unread_for_user(
        self, user_id: int, chat_id: int, trigger_llm: bool = False
    ) -> None:
        """Синхронізує непрочитані повідомлення користувача та за потреби запускає LLM."""

        unread_messages = await self.telegram.fetch_unread_messages(chat_id)
        if not unread_messages:
            print(
                f"ℹ️ Непрочитаних повідомлень не знайдено для користувача {user_id} у чаті {chat_id}."
            )
            return

        for message in unread_messages:
            content = message.get("text") or ""
            message_id = message.get("id")
            message_date = message.get("date")
            message_time_iso = (
                message_date.astimezone(timezone.utc).isoformat()
                if isinstance(message_date, datetime)
                else datetime.now(timezone.utc).isoformat()
            )
            self.history.append_message(
                user_id=user_id,
                role="user",
                content=content,
                message_time_iso=message_time_iso,
                message_id=message_id,
            )

        max_message_id = max((msg.get("id") or 0 for msg in unread_messages), default=0)
        if max_message_id:
            await self.telegram.mark_messages_read(chat_id, max_message_id)
        print(
            f"📥 Додано {len(unread_messages)} непрочитаних повідомлень у історію для користувача {user_id}."
        )

        if not trigger_llm:
            return

        messages_for_llm = self._build_llm_messages(user_id=user_id)
        try:
            answer_raw = await asyncio.to_thread(self.llm.generate, messages_for_llm)
        except Exception as exc:
            print(f"❌ Помилка при виклику LLM (sync_unread) для {user_id}: {exc}")
            answer_raw = "[]"

        print("\n================= RAW LLM RESPONSE (sync_unread) =================")
        try:
            parsed = json.loads(answer_raw)
            pretty = json.dumps(parsed, ensure_ascii=False, indent=2)
            print(pretty)
        except Exception:
            print(answer_raw)
        print("================================================================\n")

        actions = self._parse_actions(answer_raw)
        await self._execute_actions(chat_id=chat_id, user_id=user_id, actions=actions)

    def _build_llm_messages(self, user_id: int) -> List[dict]:
        """Формує список повідомлень для LLM з урахуванням системних промптів та історії."""

        messages_for_llm: List[dict] = []

        # Додаємо інструкцію про actions першою, щоб LLM одразу бачила формат очікуваних дій.
        if ACTIONS_SYSTEM_PROMPT and self.actions_prompt:
            messages_for_llm.append({"role": "system", "content": self.actions_prompt})

        # Базовий системний промпт завжди йде після інструкцій до дій.
        messages_for_llm.append({"role": "system", "content": self.system_prompt})

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
                content = file.read().strip()
            return content
        except Exception as exc:
            print(f"⚠️ Не вдалося прочитати user_info.txt для {user_id}: {exc}")
            return None

    @staticmethod
    def _format_history_content(
        content: str,
        created_at: Optional[str],
        message_id: Optional[int],
    ) -> str:
        """Готує рядок для LLM у форматі "date | message_id | message"."""

        # Навіть якщо якихось метаданих немає, все одно формуємо явний текст,
        # щоб модель бачила структуру і могла ліпше відновити контекст діалогу.
        date_value = created_at or "unknown"
        message_id_value = message_id if message_id is not None else "unknown"

        return (
            f"date: {date_value} | "
            f"message_id: {message_id_value} | "
            f"message: {content}"
        )

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
                    "content": answer_raw,
                }
            ]

    async def _execute_actions(
        self, chat_id: int, user_id: int, actions: Sequence[dict]
    ) -> None:
        """По черзі виконує екшени, які повернула LLM, враховуючи затримку wait_seconds."""

        for action in actions:
            action_type_raw = action.get("type")
            action_type = self._normalize_action_type(action_type_raw)
            wait_seconds = float(action.get("wait_seconds", 0) or 0)
            human_seconds = float(action.get("human_seconds", 0) or 0)

            if not action_type:
                print("ℹ️ Отримано дію без типу, пропускаю її.")
                continue

            payload = self._build_payload_for_action(
                action_type=action_type, action_body=action
            )
            handler = self._action_handlers.get(action_type)

            if not handler:
                # Невідомий тип — просто пропускаємо, щоб не ламати сценарій.
                print(f"ℹ️ Невідомий тип дії від LLM: {action_type_raw}. Пропускаю.")
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

    @staticmethod
    def _normalize_action_type(action_type: Optional[str]) -> Optional[str]:
        """Нормалізує назви дій, щоб підтримувати старий і новий формати від LLM."""

        if not action_type:
            return None
        aliases = {
            "react_to_message": "add_reaction",
            "fake_typping": "fake_typing",
        }
        return aliases.get(action_type, action_type)

    @staticmethod
    def _build_payload_for_action(action_type: str, action_body: dict) -> dict:
        """Готує payload для хендлера, враховуючи новий формат екшенів без вкладеного payload."""

        if action_body.get("payload"):
            # Старий формат вже має payload – повертаємо як є.
            return action_body.get("payload") or {}

        if action_type == "send_message":
            return {"content": action_body.get("content")}

        if action_type == "send_messages":
            return {"messages": action_body.get("messages")}

        if action_type == "add_reaction":
            return {
                "message_id": action_body.get("message_id"),
                "emoji": action_body.get("reaction") or action_body.get("emoji"),
            }

        # Для wait, fake_typing, ignore нічого додатково не потрібно.
        return {}


