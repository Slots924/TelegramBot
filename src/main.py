import asyncio
from src.telegram_api.telegram_api import TelegramAPI

async def main():
    tg = TelegramAPI()
    await tg.connect()

    # Можна протестити відправку перед стартом прослуховування
    await tg.send_message("me", "👋 Привіт! Я тепер слухаю всі повідомлення.")

    # Запускаємо нескінченне прослуховування
    await tg.run()


    

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 Зупинено вручну.")