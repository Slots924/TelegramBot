"""Обробник дії send_message для LLMRouter."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict

from src.history.history_manager import HistoryManager
from src.telegram_api.telegram_api import TelegramAPI


async def handle_send_message(
    telegram: TelegramAPI,
    history: HistoryManager,
    chat_id: int,
    user_id: int,
    payload: Dict[str, Any],
    human_seconds: float,
) -> None:
    """Надсилає текстове повідомлення в чат і записує його в історію.

    Параметри:
    - telegram: інстанс TelegramAPI для реальної відправки.
    - history: менеджер історії, куди додаємо новий запис від бота.
    - chat_id: ідентифікатор чату, куди потрібно надіслати текст.
    - user_id: ідентифікатор користувача, якого стосується діалог.
    - payload: словник із полями дії, очікуємо payload["content"].
    - human_seconds: скільки секунд потрібно імітувати набір перед відправкою.
    """

    content = payload.get("content")
    if not content:
        return

    # Показуємо статус "typing" перед надсиланням, щоб виглядало природніше.
    await telegram.send_typing(chat_id, human_seconds)

    try:
        message = await telegram.send_message(chat_id, content)
        message_time_iso = (
            message.date.astimezone(timezone.utc).isoformat()
            if getattr(message, "date", None)
            else datetime.now(timezone.utc).isoformat()
        )
        # Додаємо відповідь бота до історії з метаданими про час.
        history.append_message(
            user_id=user_id,
            role="assistant",
            content=content,
            message_time_iso=message_time_iso,
        )
    except Exception as exc:
        # Не кидаємо помилку вище, щоб не зупинити сценарій інших дій.
        print(f"❌ Не вдалося відправити повідомлення користувачу {user_id}: {exc}")
