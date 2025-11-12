"""
telegram_api.py — клас для роботи з Telegram User API через Telethon.
Містить базові методи:
- підключення
- відправлення повідомлення будь-якому користувачу
"""

from telethon import TelegramClient
from .config import TELEGRAM_API_ID, TELEGRAM_API_HASH, SESSION_NAME
import os


class TelegramAPI:
    """Клас-обгортка для роботи з Telegram через Telethon."""

    def __init__(self):
        # Створюємо шлях до файлу сесії (у підпапці src/telegram_api/sessions/)
        session_dir = os.path.join(os.path.dirname(__file__), "sessions")
        os.makedirs(session_dir, exist_ok=True)

        session_path = os.path.join(session_dir, SESSION_NAME)

        # Ініціалізуємо клієнт Telethon
        self.client = TelegramClient(session_path, TELEGRAM_API_ID, TELEGRAM_API_HASH)

    async def connect(self):
        """Запускає клієнт і авторизує користувача, якщо ще не авторизований."""
        await self.client.start()
        me = await self.client.get_me()
        print(f"✅ Авторизовано як: {me.first_name} ({me.id})")

    async def send_message(self, recipient, text: str):
        """
        Надсилає повідомлення будь-кому.

        recipient — це може бути:
          - username (str), напр. "durov" або "@durov"
          - phone number (str), напр. "+380501234567"
          - user_id (int)
          - "me" — щоб надіслати самому собі
        """
        msg = await self.client.send_message(recipient, text)
        print(f"📨 Надіслано повідомлення '{text}' користувачу: {recipient}")
        return msg

    async def disconnect(self):
        """Закриває підключення до Telegram."""
        await self.client.disconnect()