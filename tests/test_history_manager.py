"""Тести для HistoryManager, які перевіряють пошук останніх message_id."""

import json
import os
import sys
from pathlib import Path

import pytest

# Додаємо шлях до кореня проєкту, щоб імпорт src працював під час тестів.
ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from settings import HISTORY_MAX_MESSAGES_PER_CHUNK
from src.history.history_manager import HistoryManager


@pytest.fixture()
def history(tmp_path) -> HistoryManager:
    """Створює інстанс HistoryManager із тимчасовою директорією."""

    base_dir = tmp_path / "dialogs"
    return HistoryManager(base_dir=str(base_dir))


def test_get_last_message_id_without_history_returns_zero(history: HistoryManager) -> None:
    """Якщо історії немає, методи повинні стабільно повертати 0."""

    assert history.get_last_user_message_id(user_id=1) == 0
    assert history.get_last_assistant_message_id(user_id=1) == 0


def test_get_last_message_id_reads_latest_per_role(history: HistoryManager) -> None:
    """Метод повертає останній message_id по кожній ролі з наявних чанків."""

    history.append_message(user_id=7, role="user", content="hi", message_id=101)
    history.append_message(user_id=7, role="assistant", content="hello", message_id=202)
    history.append_message(user_id=7, role="user", content="new", message_id=303)

    assert history.get_last_user_message_id(user_id=7) == 303
    assert history.get_last_assistant_message_id(user_id=7) == 202


def test_get_last_message_id_uses_meta_when_messages_missing(history: HistoryManager) -> None:
    """Якщо в останньому чанку немає повідомлень, метод читає meta."""

    # Створюємо попередній чанк із повідомленнями.
    history.append_message(user_id=9, role="user", content="first", message_id=11)

    # Створюємо новий чанк без messages, але з метаданими про останній id.
    user_dir = os.path.join(history.base_dir, "user_9")
    os.makedirs(user_dir, exist_ok=True)
    empty_chunk_path = os.path.join(user_dir, "chunk_0002.json")
    with open(empty_chunk_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "user_id": 9,
                "chunk_index": 2,
                "messages": [],
                "meta": {
                    "created_at": "2024-01-01T00:00:00",
                    "updated_at": "2024-01-01T00:00:00",
                    "last_user_message_id": 555,
                    "last_assistant_message_id": 777,
                },
            },
            f,
        )

    assert history.get_last_user_message_id(user_id=9) == 555
    assert history.get_last_assistant_message_id(user_id=9) == 777


def test_get_last_message_id_skips_broken_chunk(history: HistoryManager) -> None:
    """Пошкоджені файли не повинні ламати пошук message_id."""

    history.append_message(user_id=5, role="user", content="ok", message_id=41)
    user_dir = os.path.join(history.base_dir, "user_5")

    # Додаємо новіший чанк із битими даними.
    with open(os.path.join(user_dir, "chunk_0002.json"), "w", encoding="utf-8") as f:
        f.write("{this is not valid json}")

    assert history.get_last_user_message_id(user_id=5) == 41


def test_new_chunk_keeps_previous_meta_ids(history: HistoryManager) -> None:
    """При створенні нового чанка метадані мають зберегти попередні last_id."""

    # Заповнюємо перший чанк до межі, фіксуючи останній message_id користувача.
    for idx in range(HISTORY_MAX_MESSAGES_PER_CHUNK):
        history.append_message(
            user_id=12,
            role="user",
            content=f"msg {idx}",
            message_id=100 + idx,
        )

    # Наступний запис створює новий чанк. message_id None, але meta повинна
    # перенести останній ідентифікатор з попереднього чанка.
    history.append_message(
        user_id=12,
        role="assistant",
        content="assistant reply",
        message_id=None,
    )

    user_dir = os.path.join(history.base_dir, "user_12")
    second_chunk_path = os.path.join(user_dir, "chunk_0002.json")
    with open(second_chunk_path, "r", encoding="utf-8") as f:
        chunk_data = json.load(f)

    assert chunk_data.get("meta", {}).get("last_user_message_id") == 100 + HISTORY_MAX_MESSAGES_PER_CHUNK - 1
    # Оскільки message_id для асистента не передавали — зберігається попереднє значення (0).
    assert chunk_data.get("meta", {}).get("last_assistant_message_id") == 0

    # Пошук останніх message_id також повертає значення з метаданих нового чанка.
    assert history.get_last_user_message_id(user_id=12) == 100 + HISTORY_MAX_MESSAGES_PER_CHUNK - 1


def test_get_last_message_id_unknown_role_returns_zero(history: HistoryManager) -> None:
    """Невідома роль повинна безпечно повертати 0 без виключень."""

    history.append_message(user_id=42, role="user", content="msg", message_id=1)

    # Використовуємо приватний метод для перевірки поведінки без аварій.
    assert history.get_last_message_id(user_id=42, role="moderator") == 0
