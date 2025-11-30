"""Основний цикл адмін-консолі: читає команди та викликає хендлери."""

from __future__ import annotations

import asyncio

from src.admin_console import parser
from src.admin_console.commands import (
    AppendSystemPromptCommand,
    DeleteDialogCommand,
    ExitCommand,
    HelpCommand,
    ListDialogsCommand,
    PruneHistoryCommand,
    SendMessageCommand,
    ShowHistoryCommand,
)
from src.admin_console.handlers import (
    handle_append_system_prompt,
    handle_delete_dialog,
    handle_list_dialogs,
    handle_prune_history,
    handle_send_message,
    handle_show_history,
)
from src.history.history_manager import HistoryManager
from src.router.llm_router import LLMRouter
from src.telegram_api.telegram_api import TelegramAPI


async def _read_input(prompt: str = "> ") -> str:
    """Читає рядок із консолі в окремому потоці, щоб не блокувати event loop."""

    return await asyncio.to_thread(input, prompt)


def _print_help() -> None:
    """Показує список доступних команд та короткий синтаксис."""

    print(
        """
Доступні команди:
  send <user_id|@username> [текст]   — відправити повідомлення або запустити LLM без тексту
  append_sys <target> <текст>         — додати системний промпт у кінець історії
  list_dialogs                        — показати всі діалоги (user_id | username | first_name | last_name)
  show_history <target> [limit]       — показати останні N повідомлень (дефолт 10)
  prune_history <target> [keep]       — залишити лише N останніх чанків (дефолт 5)
  delete_dialog <target>              — повністю видалити діалог
  help                                — показати цю підказку
  exit                                — завершити роботу консолі
"""
    )


async def run_admin_console(
    telegram: TelegramAPI, history: HistoryManager, router: LLMRouter
) -> None:
    """Запускає нескінченний цикл читання команд та делегує їх у відповідні хендлери."""

    print("🛠️ Адмін-консоль запущена. Введіть 'help' для списку команд.")

    while True:
        try:
            line = await _read_input()
        except (EOFError, KeyboardInterrupt):
            print("\n🛑 Вихід з адмін-консолі.")
            break

        if not line.strip():
            continue

        try:
            command = parser.parse_command(line)
        except ValueError as exc:
            print(f"❌ Помилка парсингу: {exc}")
            continue

        try:
            if isinstance(command, ExitCommand):
                print("👋 Завершую роботу адмін-консолі.")
                break
            if isinstance(command, HelpCommand):
                _print_help()
            elif isinstance(command, SendMessageCommand):
                await handle_send_message(command, telegram=telegram, history=history, router=router)
            elif isinstance(command, AppendSystemPromptCommand):
                await handle_append_system_prompt(command, history=history, telegram=telegram)
            elif isinstance(command, ListDialogsCommand):
                await handle_list_dialogs(command)
            elif isinstance(command, ShowHistoryCommand):
                await handle_show_history(command, history=history, telegram=telegram)
            elif isinstance(command, PruneHistoryCommand):
                await handle_prune_history(command, telegram=telegram)
            elif isinstance(command, DeleteDialogCommand):
                await handle_delete_dialog(command, telegram=telegram)
            else:
                print("⚠️ Невідома команда після парсингу.")
        except Exception as exc:
            print(f"❌ Помилка при виконанні команди: {exc}")

    print("✅ Адмін-консоль завершилася.")
