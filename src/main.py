import asyncio

from src.telegram_api.telegram_api import TelegramAPI
from src.llm_api.mistral_api import MistralAPI
from src.router.llm_router import LLMRouter


async def main():
    # 1️⃣ Створюємо Telegram і LLM
    telegram_api = TelegramAPI()
    llm_api = MistralAPI()

    # 2️⃣ Створюємо роутер, який їх зв'язує
    router = LLMRouter(telegram_api=telegram_api, llm_api=llm_api)

    # 3️⃣ Передаємо роутер у TelegramAPI
    telegram_api.set_router(router)

    # 4️⃣ Підключаємося до Telegram
    await telegram_api.connect()

    # 5️⃣ Запускаємо нескінченне прослуховування
    await telegram_api.run()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 Зупинено вручну.")