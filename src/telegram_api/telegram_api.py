import os
from telethon import TelegramClient, events
from .config import TELEGRAM_API_ID, TELEGRAM_API_HASH, SESSION_NAME


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

    async def send_message(self, chat_id: int | str, text: str) -> None:
        """Надсилає повідомлення у вказаний чат (без reply)."""
        await self.client.send_message(chat_id, text)
        print(f"📨 Відправлено повідомлення в чат {chat_id}: {text}")

    async def _on_new_message(self, event) -> None:
        """
        Внутрішній обробник Telethon.
        Викликається щоразу, коли приходить нове вхідне повідомлення.
        """
        if self._router is None:
            # Якщо роутер не підключений — просто лог і вихід
            print("⚠️ Отримано повідомлення, але роутер не налаштований.")
            return

        sender = await event.get_sender()
        user_id = sender.id          # ID користувача, який написав
        chat_id = event.chat_id      # ID чату (для приватного = user_id)
        text = event.message.message # текст повідомлення

        print(f"\n💬 Нове повідомлення від {user_id} в чаті {chat_id}: {text}")

        # Передаємо в роутер для обробки (LLM, логіка, відповідь)
        await self._router.handle_incoming_message(
            user_id=user_id,
            chat_id=chat_id,
            text=text,
        )