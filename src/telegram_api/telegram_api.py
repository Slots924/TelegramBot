"""
telegram_api.py — клас для роботи з Telegram User API через Telethon.
Містить базові методи:
- підключення
- відправлення повідомлення будь-якому користувачу
"""

from telethon import TelegramClient, events
from .config import TELEGRAM_API_ID, TELEGRAM_API_HASH, SESSION_NAME
import os


class TelegramAPI:
    """Клас-обгортка для роботи з Telegram через Telethon."""

    def __init__(self):
        # Створюємо шлях до сесії у src/telegram_api/sessions/
        session_dir = os.path.join(os.path.dirname(__file__), "sessions")
        os.makedirs(session_dir, exist_ok=True)

        session_path = os.path.join(session_dir, SESSION_NAME)

        # Ініціалізуємо клієнт
        self.client = TelegramClient(session_path, TELEGRAM_API_ID, TELEGRAM_API_HASH)

        # Регіструємо обробник вхідних повідомлень
        self.client.add_event_handler(self._on_new_message, events.NewMessage())

    async def connect(self):
        """Підключається до Telegram (з логіном, якщо треба)."""
        await self.client.start()
        me = await self.client.get_me()
        print(f"✅ Авторизовано як: {me.first_name} ({me.id})")

    async def send_message(self, recipient, text: str):
        """Надсилає повідомлення будь-кому (ID, username, номер, 'me')."""
        await self.client.send_message(recipient, text)
        print(f"📨 Надіслано повідомлення '{text}' користувачу: {recipient}")

    async def _on_new_message(self, event):
        """
        Внутрішній callback для кожного вхідного повідомлення.
        Викликається автоматично при отриманні нового меседжу.
        """
        sender = await event.get_sender()
        sender_name = sender.username or sender.first_name or "невідомий"
        text = event.message.message

        print(f"\n💬 Нове повідомлення від {sender_name}: {text}")

        # Тут можна вставити будь-яку логіку:
        # наприклад, авто-відповідь, фільтри, обробку команд тощо.
        # await event.reply("Дякую за повідомлення!")

    async def run(self):
        """
        Запускає клієнт і слухає повідомлення, доки не зупиниш вручну.
        """
        print("👂 Прослуховування вхідних повідомлень... (Ctrl+C щоб вийти)")
        await self.client.run_until_disconnected()

    async def disconnect(self):
        """Закриває клієнт."""
        await self.client.disconnect()