"""Опис структур команд для адмін-консолі."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class BaseCommand:
    """Базовий тип команди. Містить лише ім'я для простого логування."""

    name: str


@dataclass
class SendMessageCommand(BaseCommand):
    """Надсилання повідомлення конкретному користувачу."""

    raw_target: str
    user_id: Optional[int]
    username: Optional[str]
    text: Optional[str]


@dataclass
class AppendSystemPromptCommand(BaseCommand):
    """Додавання системного промпта в історію користувача."""

    raw_target: str
    user_id: Optional[int]
    username: Optional[str]
    content: str


@dataclass
class ListDialogsCommand(BaseCommand):
    """Вивід усіх доступних діалогів із файлової системи."""


@dataclass
class ShowHistoryCommand(BaseCommand):
    """Показ останніх повідомлень конкретного користувача."""

    raw_target: str
    user_id: Optional[int]
    username: Optional[str]
    limit: int


@dataclass
class PruneHistoryCommand(BaseCommand):
    """Обрізання історії, залишаючи тільки потрібну кількість чанків."""

    raw_target: str
    user_id: Optional[int]
    username: Optional[str]
    keep_chunks: int


@dataclass
class DeleteDialogCommand(BaseCommand):
    """Повне видалення директорії з діалогом користувача."""

    raw_target: str
    user_id: Optional[int]
    username: Optional[str]


@dataclass
class HelpCommand(BaseCommand):
    """Вивід довідки щодо доступних команд."""


@dataclass
class ExitCommand(BaseCommand):
    """Коректне завершення роботи адмін-консолі."""

