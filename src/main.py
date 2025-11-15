import asyncio

from src.telegram_api.telegram_api import TelegramAPI
from src.llm_api.mistral_api import MistralAPI
from src.router.llm_router import LLMRouter
from src.history.history_manager import HistoryManager


async def main():
    telegram_api = TelegramAPI()
    llm_api = MistralAPI()
    history = HistoryManager()

    # Роутер тепер знає і про Telegram, і про LLM, і про історію
    router = LLMRouter(
        telegram_api=telegram_api,
        llm_api=llm_api,
        history_manager=history,
    )

    telegram_api.set_router(router)

    await telegram_api.connect()
    await telegram_api.run()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 Зупинено вручну.")