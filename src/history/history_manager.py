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
from typing import List, Dict, Any, Tuple

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
                "meta": self._build_default_meta(),
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
                "meta": self._build_default_meta(),
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
        content: str | None,
        message_time_iso: str | None = None,
        message_id: int | None = None,
    ) -> None:
        """
        Додає нове повідомлення користувача або асистента в історію.

        role: "user" або "assistant"
        content: текст повідомлення (для сирих LLM-відповідей може бути None)
        message_time_iso: час, коли повідомлення надійшло/було відправлено (ISO UTC),
            збережеться у форматі YYYY-MM-DDTHH:MM:SS
        message_id: ідентифікатор повідомлення у Telegram (якщо він відомий)
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
                "meta": self._build_default_meta(),
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
                "meta": self._build_default_meta(),
            }

        # Додаємо нове повідомлення
        message = {
            "role": role,
            "content": content,
            # Коли точно було відправлено/отримано повідомлення (UTC без інформації про часовий пояс).
            "created_at": self._normalize_created_at(message_time_iso),
            "message_id": message_id,
        }
        chunk_data["messages"].append(message)
        self._ensure_meta(chunk_data)
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

    def get_last_user_message_id(self, user_id: int) -> int:
        """Повертає message_id останнього користувацького повідомлення з історії.

        Якщо чанків немає або у них відсутні коректні дані — повертає 0.
        Метод потрібен для синхронізації історії з Telegram.
        """

        last_chunk_path = self._get_last_chunk_path(user_id)
        if last_chunk_path is None:
            return 0

        try:
            chunk_data = self._load_chunk(last_chunk_path)
            self._ensure_meta(chunk_data)
            last_user_id = chunk_data.get("meta", {}).get("last_user_message_id")
            return int(last_user_id) if last_user_id else 0
        except Exception:
            # Якщо трапилась будь-яка проблема — повертаємо 0, щоб вище рівні могли зробити fallback.
            return 0

    def refresh_all_chunk_meta(self) -> Tuple[int, int]:
        """Перебудовує метадані для всіх існуючих чанків у файловій системі.

        Повертає кортеж (оновлено, всього), щоб хендлер міг вивести статистику.
        """

        updated = 0
        total = 0

        for root, _, files in os.walk(HISTORY_BASE_DIR):
            for filename in files:
                if not filename.startswith("chunk_") or not filename.endswith(".json"):
                    continue

                total += 1
                chunk_path = os.path.join(root, filename)
                chunk_data = self._load_chunk(chunk_path)
                before_meta = json.dumps(chunk_data.get("meta") or {}, sort_keys=True)

                self._ensure_meta(chunk_data)
                after_meta = json.dumps(chunk_data.get("meta") or {}, sort_keys=True)

                if before_meta != after_meta:
                    updated += 1
                    self._save_chunk(chunk_path, chunk_data)

        return updated, total

    # =====================
    # Статичні утиліти
    # =====================

    @staticmethod
    def _now_iso() -> str:
        """Повертає поточний час у форматі YYYY-MM-DDTHH:MM:SS (UTC)."""
        return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")

    @staticmethod
    def _normalize_created_at(message_time_iso: str | None) -> str:
        """
        Приводить довільний ISO-час до формату без мікросекунд і таймзони.

        Якщо парсинг не вдався — повертає поточний момент у правильному форматі.
        """

        if not message_time_iso:
            return HistoryManager._now_iso()

        try:
            prepared_value = message_time_iso.replace("Z", "+00:00")
            parsed = datetime.fromisoformat(prepared_value)
            if parsed.tzinfo is not None:
                parsed = parsed.astimezone(timezone.utc)
            return parsed.strftime("%Y-%m-%dT%H:%M:%S")
        except Exception:
            return HistoryManager._now_iso()

    def _build_default_meta(self) -> Dict[str, Any]:
        """Створює базову структуру meta з усіма необхідними полями."""

        return {
            "created_at": self._now_iso(),
            "updated_at": self._now_iso(),
            "last_user_message_id": None,
            "last_assistant_message_id": None,
        }

    def _ensure_meta(self, chunk_data: Dict[str, Any]) -> None:
        """Гарантує наявність і коректність полів meta для конкретного чанка."""

        meta = chunk_data.get("meta") or {}
        messages = chunk_data.get("messages") or []

        # Визначаємо часи створення та оновлення на основі наявних даних.
        meta_created = meta.get("created_at") or self._extract_first_timestamp(messages)
        meta_updated = meta.get("updated_at") or self._extract_last_timestamp(messages)

        meta["created_at"] = self._normalize_created_at(meta_created)
        meta["updated_at"] = self._normalize_created_at(meta_updated)

        # Рахуємо останні message_id для кожної ролі.
        last_user_id, last_assistant_id = self._calculate_last_message_ids(messages)
        meta["last_user_message_id"] = last_user_id
        meta["last_assistant_message_id"] = last_assistant_id

        chunk_data["meta"] = meta

    def _calculate_last_message_ids(self, messages: List[Dict[str, Any]]) -> Tuple[int | None, int | None]:
        """Шукає останні message_id для ролей user та assistant серед переданих повідомлень."""

        last_user_id = None
        last_assistant_id = None

        for message in messages:
            role = message.get("role")
            msg_id = message.get("message_id")
            if msg_id is None:
                continue

            if role == "user":
                last_user_id = msg_id
            elif role == "assistant":
                last_assistant_id = msg_id

        return last_user_id, last_assistant_id

    def _extract_first_timestamp(self, messages: List[Dict[str, Any]]) -> str:
        """Знаходить найстарішу дату серед повідомлень або повертає поточний час."""

        if not messages:
            return self._now_iso()

        created_values = [msg.get("created_at") for msg in messages if msg.get("created_at")]
        if not created_values:
            return self._now_iso()

        try:
            parsed = [self._normalize_created_at(value) for value in created_values]
            return min(parsed)
        except Exception:
            return self._now_iso()

    def _extract_last_timestamp(self, messages: List[Dict[str, Any]]) -> str:
        """Знаходить найновішу дату серед повідомлень або повертає поточний час."""

        if not messages:
            return self._now_iso()

        created_values = [msg.get("created_at") for msg in messages if msg.get("created_at")]
        if not created_values:
            return self._now_iso()

        try:
            parsed = [self._normalize_created_at(value) for value in created_values]
            return max(parsed)
        except Exception:
            return self._now_iso()
