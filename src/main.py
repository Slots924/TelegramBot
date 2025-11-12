import asyncio
from src.telegram_api.telegram_api import TelegramAPI

async def main():
    tg = TelegramAPI()
    await tg.connect()

    # 🔸 Приклади використання:

    # 1️⃣ Відправити повідомлення собі (у "Saved Messages")
    await tg.send_message("me", "Привіт собі 👋")

    # 2️⃣ Відправити повідомлення іншому користувачу по username
    # await tg.send_message("@username_іншого", "Привіт!")

    # 3️⃣ Відправити по user_id (наприклад 123456789)
    # await tg.send_message(123456789, "Привіт за ID!")

    # 4️⃣ Відправити за номером телефону
    # await tg.send_message("+380501234567", "Привіт по номеру!")

    await tg.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
