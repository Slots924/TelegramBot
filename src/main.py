import asyncio

from src.history.history_manager import HistoryManager
from src.llm_api.llm_api import LLMAPI
from src.llm_api.utils.loader import load_system_prompt
from src.router.llm_router import LLMRouter
from src.telegram_api.telegram_api import TelegramAPI


async def main() -> None:
    """Точка входу: збирає сервіси, підключає їх і запускає Telegram-клієнт."""

    telegram_api = TelegramAPI()
    llm_api = LLMAPI()
    history = HistoryManager()
    system_prompt = load_system_prompt()

    router = LLMRouter(
        telegram_api=telegram_api,
        llm_api=llm_api,
        history_manager=history,
        system_prompt=system_prompt,
    )

    telegram_api.set_router(router)

    await telegram_api.connect()
    await telegram_api.run()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 Зупинено вручну.")
