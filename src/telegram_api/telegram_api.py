import asyncio
import json
import os
from datetime import datetime, timezone

from telethon import TelegramClient, events, functions, types
from telethon.tl.types import Channel, Chat, User

from settings import ANSWER_TO_TELEGRAM_BOTS, HISTORY_BASE_DIR, USER_INFO_FILENAME
from .config import TELEGRAM_API_HASH, TELEGRAM_API_ID, SESSION_NAME

class TelegramAPI:
    """Клас-обгортка для Telegram-клієнта (Telethon)."""

    def __init__(self):
        # Папка для зберігання .session
        session_dir = os.path.join(os.path.dirname(__file__), "sessions")
        os.makedirs(session_dir, exist_ok=True)

        session_path = os.path.join(session_dir, SESSION_NAME)

        # Ініціалізуємо клієнт
        self.client = TelegramClient(session_path, TELEGRAM_API_ID, TELEGRAM_API_HASH)

        # Роутер ми підставимо пізніше через set_router()
        self._router = None

        # Реєструємо обробник нових вхідних повідомлень
        # incoming=True — ловимо тільки повідомлення від інших користувачів
        self.client.add_event_handler(
            self._on_new_message,
            events.NewMessage(incoming=True)
        )

    def set_router(self, router) -> None:
        """Прив'язуємо роутер, який буде обробляти вхідні повідомлення."""
        self._router = router

    async def connect(self) -> None:
        """Підключається до Telegram, авторизує користувача при першому запуску."""
        await self.client.start()
        me = await self.client.get_me()
        print(f"✅ Авторизовано як: {me.first_name} (id: {me.id})")

    async def run(self) -> None:
        """Запускає нескінченне прослуховування повідомлень."""
        print("👂 Слухаю вхідні повідомлення... (Ctrl+C щоб вийти)")
        await self.client.run_until_disconnected()

    async def send_message(self, chat_id: int | str, text: str):
        """Надсилає повідомлення у вказаний чат (без reply) і повертає Message."""

        message = await self.client.send_message(chat_id, text)
        print(f"📨 Відправлено повідомлення в чат {chat_id}: {text}")
        return message

    async def _on_new_message(self, event) -> None:
        """
        Внутрішній обробник Telethon.
        Викликається щоразу, коли приходить нове вхідне повідомлення.
        """
        # Обробляємо тільки приватні діалоги, групи та канали пропускаємо без логів.
        if not event.is_private:
            return

        if self._router is None:
            print("⚠️ Отримано повідомлення, але роутер не налаштований.")
            return

        sender = await event.get_sender()

        # Ігноруємо телеграм-ботів, якщо це заборонено налаштуванням.
        if not ANSWER_TO_TELEGRAM_BOTS and isinstance(sender, User) and getattr(sender, "bot", False):
            return

        # Безпечний витяг ID відправника: беремо з sender або з самого event
        # (наприклад, якщо sender == None для анонімних адмінів чи каналів).
        user_id = getattr(sender, "id", None) or getattr(event, "sender_id", None)
        if user_id is None:
            print("⚠️ Не вдалося визначити user_id для повідомлення, пропускаю обробку.")
            return

        chat_id = event.chat_id      # ID чату (для приватного = user_id)
        text = event.message.message # текст повідомлення
        message_date = event.message.date or datetime.now(timezone.utc)

        print(f"\n💬 Нове повідомлення від {user_id} в чаті {chat_id}: {text}")

        # Перевіряємо та зберігаємо user_info.txt, якщо його ще немає
        chat_title = getattr(event.chat, "title", None)
        self._ensure_user_info_file(
            user_id=user_id,
            sender=sender,
            chat_title=chat_title,
            is_private_chat=event.is_private,
        )

        try:
            # Позначаємо повідомлення як прочитане, щоби Telegram не показував "непрочитано".
            await event.mark_read()
        except Exception as exc:
            # Якщо не вдалось — просто лог, бо це не критично для подальшої логіки.
            print(f"⚠️ Не вдалося позначити повідомлення прочитаним: {exc}")

        # Передаємо в роутер для обробки (LLM, логіка, відповідь)
        await self._router.handle_incoming_message(
            user_id=user_id,
            chat_id=chat_id,
            text=text,
            message_time=message_date,
            message_id=getattr(event.message, "id", None),
        )

    async def send_typing(self, chat_id: int | str, duration: float) -> None:
        """Надсилає статус "typing" та чекає потрібний час.

        Parameters
        ----------
        chat_id: int | str
            Чат, у якому потрібно показати, що "бот" набирає текст.
        duration: float
            Скільки секунд підтримувати статус typing.
        """

        if duration <= 0:
            return

        try:
            # context manager Telethon сам зніме статус typing після виходу з блоку
            async with self.client.action(chat_id, "typing"):
                await asyncio.sleep(duration)
        except Exception as exc:
            print(f"⚠️ Не вдалося показати статус typing у чаті {chat_id}: {exc}")

    async def send_reaction(self, chat_id: int | str, message_id: int | str, emoji: str) -> None:
        """Ставитиме реакцію на конкретне повідомлення у чаті.

        Параметри
        ----------
        chat_id: int | str
            Ідентифікатор чату. Має бути додатнім цілим числом, інакше Telethon не зможе
            знайти потрібний діалог для реакції.
        message_id: int | str
            Ідентифікатор повідомлення, на яке ставимо реакцію.
        emoji: str
            Емодзі, яке потрібно додати як реакцію.
        """

        try:
            # Telethon низькорівневий метод працює тільки з цілими числами, тому конвертуємо.
            prepared_chat_id = int(chat_id)
            prepared_message_id = int(message_id)

            # Якщо chat_id вийшов від'ємним (наприклад, для каналів/груп), реакція не
            # спрацює, тому одразу логуємо і завершуємо обробку.
            if prepared_chat_id <= 0:
                print(
                    "⚠️ chat_id має бути додатнім числом для надсилання реакції. "
                    f"Отримано: {prepared_chat_id}. Пропускаю запит."
                )
                return

            # Використовуємо functions.messages.SendReactionRequest, бо високорівневий
            # client.send_reaction у нас не спрацьовував для збережених сесій.
            await self.client(
                functions.messages.SendReactionRequest(
                    peer=prepared_chat_id,
                    msg_id=prepared_message_id,
                    reaction=[types.ReactionEmoji(emoticon=emoji)],
                    big=False,
                    add_to_recent=False,
                )
            )

            print(
                f"✅ Додано реакцію '{emoji}' у чаті {prepared_chat_id} для message_id={prepared_message_id}."
            )
        except Exception as exc:
            print(f"⚠️ Не вдалося поставити реакцію в чаті {chat_id}: {exc}")

    def _ensure_user_info_file(
        self, user_id: int, sender, chat_title: str | None, is_private_chat: bool
    ) -> None:
        """Створює user_info.txt з профільними даними, якщо його ще немає.

        Якщо відправник невідомий або файл не вдалося записати, виводимо лог, але
        не зупиняємо роботу застосунку.
        """

        # Шлях до файлу з інформацією про користувача
        user_dir = os.path.join(HISTORY_BASE_DIR, f"user_{user_id}")
        os.makedirs(user_dir, exist_ok=True)
        user_info_path = os.path.join(user_dir, USER_INFO_FILENAME)

        if os.path.exists(user_info_path):
            return

        profile_data = self._build_profile_data(
            sender=sender,
            fallback_user_id=user_id,
            chat_title=chat_title if not is_private_chat else None,
        )

        try:
            with open(user_info_path, "w", encoding="utf-8") as file:
                file.write(self._render_user_info_block(profile_data))
            print(f"💾 Збережено user_info для {user_id} у {user_info_path}")
        except Exception as exc:
            print(f"⚠️ Не вдалося зберегти user_info.txt для {user_id}: {exc}")

    @staticmethod
    def _build_profile_data(
        sender, fallback_user_id: int, chat_title: str | None
    ) -> dict:
        """Збирає профільні дані користувача або групи в єдину структуру."""

        if sender is None:
            print("⚪ Відправник невідомий (None), заповнюю тільки наявні поля.")

        profile_data = {
            "id": getattr(sender, "id", None) if sender else fallback_user_id,
            "first_name": getattr(sender, "first_name", None) if sender else None,
            "last_name": getattr(sender, "last_name", None) if sender else None,
            "username": getattr(sender, "username", None) if sender else None,
            "bio": getattr(sender, "about", None) if sender else None,
            "chat_title": chat_title,
        }

        if isinstance(sender, (Channel, Chat)) and not profile_data["first_name"]:
            # Для групових чатів first_name/last_name зазвичай відсутні, тому підхоплюємо title
            profile_data["first_name"] = getattr(sender, "title", None)

        return profile_data

    @staticmethod
    def _render_user_info_block(profile_data: dict) -> str:
        """Формує текстовий блок USER_INFO для передачі в LLM."""

        # Текстовий опис про те, як використовувати метадані, додаємо перед JSON.
        header_lines = [
            "USER_INFO_BLOCK_START",
            "Це структуровані метадані про користувача Telegram, з яким ти зараз ведеш діалог.",
            "Використовуй їх лише для контексту (ім'я, стиль спілкування тощо), але НЕ показуй їх у відповідях дослівно.",
            "",
            f"USER_INFO = {json.dumps(profile_data, ensure_ascii=False, indent=2)}",
            "",
            "USER_INFO_BLOCK_END",
        ]
        return "\n".join(header_lines)
