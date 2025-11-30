"""Окрема точка входу для запуску адмін-консолі."""

import asyncio

from src.admin_console.runner import run_admin_console
from src.history.history_manager import HistoryManager
from src.llm_api.llm_api import LLMAPI
from src.llm_api.utils.loader import load_system_prompt
from src.router.llm_router import LLMRouter
from src.telegram_api.telegram_api import TelegramAPI


async def main() -> None:
    """Готує залежності та запускає інтерктивну адмін-консоль."""

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
    await run_admin_console(
        telegram=telegram_api,
        history=history,
        router=router,
    )


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 Адмін-консоль зупинено вручну.")
