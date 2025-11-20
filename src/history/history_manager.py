"""
history_manager.py — керування історією діалогів для LLM.

Ідея:
- Для кожного користувача є своя папка:  .../history/user_<user_id>/
- В ній лежать чанки: chunk_0001.json, chunk_0002.json, ...
- В кожному чанку — список messages[] (role, content, created_at, message_id).

HistoryManager:
- додає нові повідомлення в останній чанк (або створює новий)
- дістає "хвіст" історії (кілька останніх чанків) для LLM
"""

import json
import os
from datetime import datetime, timezone
from typing import List, Dict, Any

from .config import (
    HISTORY_BASE_DIR,
    HISTORY_MAX_MESSAGES_PER_CHUNK,
    HISTORY_MAX_CHUNKS_FOR_CONTEXT,
)


class HistoryManager:
    """Керує історією діалогів користувачів, зберігаючи її в JSON-файлах."""

    def __init__(self):
        # Переконуємось, що базова директорія існує
        os.makedirs(HISTORY_BASE_DIR, exist_ok=True)

    # =====================
    # Внутрішні допоміжні
    # =====================

    def _get_user_dir(self, user_id: int) -> str:
        """
        Повертає шлях до папки користувача.
        Створює її, якщо ще не існує.
        """
        user_dir = os.path.join(HISTORY_BASE_DIR, f"user_{user_id}")
        os.makedirs(user_dir, exist_ok=True)
        return user_dir

    def _list_user_chunks(self, user_id: int) -> List[str]:
        """
        Повертає список шляхів до всіх чанків користувача,
        відсортований по chunk_xxxx у зростаючому порядку.
        """
        user_dir = self._get_user_dir(user_id)
        files = [
            f for f in os.listdir(user_dir)
            if f.startswith("chunk_") and f.endswith(".json")
        ]
        files.sort()  # chunk_0001 < chunk_0002 < ...
        return [os.path.join(user_dir, f) for f in files]

    def _get_last_chunk_path(self, user_id: int) -> str | None:
        """
        Повертає шлях до останнього чанка користувача або None, якщо ще нема жодного.
        """
        chunks = self._list_user_chunks(user_id)
        if not chunks:
            return None
        return chunks[-1]

    def _create_new_chunk_path(self, user_id: int) -> str:
        """
        Створює шлях для нового чанка виду chunk_XXXX.json,
        де XXXX — наступний номер.
        """
        chunks = self._list_user_chunks(user_id)
        if not chunks:
            next_index = 1
        else:
            last_name = os.path.basename(chunks[-1])  # chunk_0007.json
            last_index = int(last_name.replace("chunk_", "").replace(".json", ""))
            next_index = last_index + 1

        user_dir = self._get_user_dir(user_id)
        filename = f"chunk_{next_index:04d}.json"
        return os.path.join(user_dir, filename)

    def _load_chunk(self, path: str) -> Dict[str, Any]:
        """Завантажує JSON-дані чанка з файлу. Якщо файл порожній/битий — повертає базову структуру."""
        if not os.path.exists(path):
            return {
                "user_id": None,
                "chunk_index": None,
                "messages": [],
                "meta": {},
            }

        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            # Якщо щось пішло не так із JSON — не ламаємося
            return {
                "user_id": None,
                "chunk_index": None,
                "messages": [],
                "meta": {},
            }

    def _save_chunk(self, path: str, data: Dict[str, Any]) -> None:
        """Зберігає JSON-дані чанка у файл."""
        # Переконуємось, що директорія існує
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    # =====================
    # Публічні методи
    # =====================

    def append_message(
        self,
        user_id: int,
        role: str,
        content: str,
        message_id: int | str | None = None,
        message_time_iso: str | None = None,
    ) -> None:
        """
        Додає нове повідомлення користувача або асистента в історію.

        role: "user" або "assistant"
        content: текст повідомлення
        message_id: Telegram message_id, якщо потрібно відслідковувати оригінал
        message_time_iso: час, коли повідомлення надійшло/було відправлено (ISO UTC)
        """
        # Визначаємо, куди писати — в останній чанк або створити новий
        last_chunk_path = self._get_last_chunk_path(user_id)

        if last_chunk_path is None:
            # Ще немає жодного чанка — створюємо перший
            chunk_path = self._create_new_chunk_path(user_id)
            chunk_data = {
                "user_id": user_id,
                "chunk_index": 1,
                "messages": [],
                "meta": {
                    "created_at": self._now_iso(),
                    "updated_at": self._now_iso(),
                },
            }
        else:
            chunk_path = last_chunk_path
            chunk_data = self._load_chunk(chunk_path)
            if chunk_data.get("messages") is None:
                chunk_data["messages"] = []

        # Якщо поточний чанк заповнений — створюємо новий
        if len(chunk_data["messages"]) >= HISTORY_MAX_MESSAGES_PER_CHUNK:
            chunk_path = self._create_new_chunk_path(user_id)
            chunk_index = int(os.path.basename(chunk_path).replace("chunk_", "").replace(".json", ""))
            chunk_data = {
                "user_id": user_id,
                "chunk_index": chunk_index,
                "messages": [],
                "meta": {
                    "created_at": self._now_iso(),
                    "updated_at": self._now_iso(),
                },
            }

        # Додаємо нове повідомлення
        message = {
            "role": role,
            "content": content,
            # Коли точно було відправлено/отримано повідомлення.
            "created_at": message_time_iso or self._now_iso(),
            # Telegram message_id допоможе LLM ставити реакції або робити реплаї.
            "message_id": message_id,
        }
        chunk_data["messages"].append(message)
        chunk_data["meta"]["updated_at"] = self._now_iso()

        # Зберігаємо чанк
        self._save_chunk(chunk_path, chunk_data)

    def get_recent_context(self, user_id: int) -> List[Dict[str, Any]]:
        """
        Повертає "хвіст" історії для користувача у вигляді списку повідомлень
        (role, content, created_at), взятих з кількох останніх чанків.

        Скільки саме чанків брати — визначається HISTORY_MAX_CHUNKS_FOR_CONTEXT.
        """
        chunks = self._list_user_chunks(user_id)
        if not chunks:
            return []

        # Беремо останні N чанків
        selected_chunks = chunks[-HISTORY_MAX_CHUNKS_FOR_CONTEXT :]

        messages: List[Dict[str, Any]] = []
        for path in selected_chunks:
            data = self._load_chunk(path)
            msgs = data.get("messages") or []
            messages.extend(msgs)

        return messages

    # =====================
    # Статичні утиліти
    # =====================

    @staticmethod
    def _now_iso() -> str:
        """Повертає поточний час у ISO-форматі (UTC)."""
        return datetime.now(timezone.utc).isoformat()
