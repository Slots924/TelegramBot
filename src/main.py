import os
import asyncio
from dotenv import load_dotenv
from telethon import TelegramClient


# 1) Завантажуємо змінні оточення з .env у процес
#    (.env не потрапляє у git, якщо він у .gitignore)
load_dotenv()

# 2) Зчитуємо конфіг із ENV (ніколи не хардкодимо секрети в коді)
API_ID = int(os.getenv("TELEGRAM_API_ID", "0"))            # числовий ID додатку Telegram
API_HASH = os.getenv("TELEGRAM_API_HASH", "")              # секретний хеш додатку Telegram
SESSION_NAME = os.getenv("TG_SESSION_NAME", "user")        # назва файлу .session (збережеться поруч із main.py)
TEST_MESSAGE = os.getenv("TEST_MESSAGE", "Test via Telethon ✅")

# 3) Маленька перевірка, щоб не запускати клієнт без ключів
if not API_ID or not API_HASH:
    raise RuntimeError(
        "TELEGRAM_API_ID / TELEGRAM_API_HASH відсутні. "
        "Заповни їх у файлі .env"
    )


async def main() -> None:
    """
    Головна асинхронна функція.
    Створює клієнт, авторизує користувача і надсилає повідомлення у 'Saved Messages'.
    """
    # 4) Створюємо TelegramClient.
    #    - SESSION_NAME: ім'я локального файлу сесії (напр., 'user.session')
    #    - API_ID / API_HASH: беруться з my.telegram.org
    #    'async with' гарантує коректне відкриття/закриття з'єднання.
    async with TelegramClient(SESSION_NAME, API_ID, API_HASH) as client:
        # 5) Перша авторизація:
        #    - при першому запуску Telethon запитає номер телефону у консолі,
        #      надішле код у Telegram, можливо — пароль (2FA), і збереже .session.
        #    - наступні запуски підуть без питань (використовується .session).
        me = await client.get_me()  # отримуємо об'єкт поточного юзера

        # 6) Надсилаємо повідомлення самому собі.
        #    Спец-адреса 'me' = чат "Saved Messages" (Збережені повідомлення)
        sent_msg = await client.send_message("me", TEST_MESSAGE)

        # 7) Виводимо базову інформацію у консоль — щоб бачити результат
        username = f"@{me.username}" if me.username else f"id:{me.id}"
        print("✅ Успіх!")
        print(f"   Кому: {username}")
        print(f"   Відправлено: {sent_msg.text}")
        print(f"   message_id: {sent_msg.id}")

# 8) Точка входу. asyncio.run запускає нашу асинхронну main()
if __name__ == "__main__":
    asyncio.run(main())