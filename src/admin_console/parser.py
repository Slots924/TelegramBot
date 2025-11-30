"""Парсер текстових команд у структуровані об'єкти команд."""

from __future__ import annotations

from typing import Tuple

from src.admin_console.commands import (
    AppendSystemPromptCommand,
    BaseCommand,
    DeleteDialogCommand,
    ExitCommand,
    HelpCommand,
    ListDialogsCommand,
    PruneHistoryCommand,
    SendMessageCommand,
    ShowHistoryCommand,
)


def _parse_target(raw_target: str) -> Tuple[int | None, str | None]:
    """Розпізнає, чи ввели user_id або username."""

    stripped = raw_target.strip()
    if stripped.isdigit():
        return int(stripped), None
    # Якщо містить символи або починається з @ — трактуємо як username.
    return None, stripped.lstrip("@")


def parse_command(line: str) -> BaseCommand:
    """Розбирає сирий рядок з консолі та повертає конкретний Command-об'єкт."""

    parts = line.strip().split()
    if not parts:
        raise ValueError("Введіть хоча б одну команду або 'help'.")

    cmd = parts[0].lower()
    args = parts[1:]

    if cmd == "send":
        if not args:
            raise ValueError("Синтаксис: send <user_id|@username> [текст]")
        raw_target = args[0]
        user_id, username = _parse_target(raw_target)
        text = " ".join(args[1:]).strip()
        text_value = text if text else None
        return SendMessageCommand(
            name="send",
            raw_target=raw_target,
            user_id=user_id,
            username=username,
            text=text_value,
        )

    if cmd == "append_sys":
        if len(args) < 2:
            raise ValueError("Синтаксис: append_sys <user_id|@username> <текст>")
        raw_target = args[0]
        user_id, username = _parse_target(raw_target)
        content = " ".join(args[1:]).strip()
        if not content:
            raise ValueError("Текст системного промпта не може бути порожнім.")
        return AppendSystemPromptCommand(
            name="append_sys",
            raw_target=raw_target,
            user_id=user_id,
            username=username,
            content=content,
        )

    if cmd == "list_dialogs":
        return ListDialogsCommand(name="list_dialogs")

    if cmd == "show_history":
        if not args:
            raise ValueError("Синтаксис: show_history <user_id|@username> [limit]")
        raw_target = args[0]
        user_id, username = _parse_target(raw_target)
        limit = 10
        if len(args) >= 2:
            try:
                limit = int(args[1])
            except ValueError:
                raise ValueError("Параметр limit має бути числом.")
        return ShowHistoryCommand(
            name="show_history",
            raw_target=raw_target,
            user_id=user_id,
            username=username,
            limit=limit,
        )

    if cmd == "prune_history":
        if not args:
            raise ValueError("Синтаксис: prune_history <user_id|@username> [keep_chunks]")
        raw_target = args[0]
        user_id, username = _parse_target(raw_target)
        keep_chunks = 5
        if len(args) >= 2:
            try:
                keep_chunks = int(args[1])
            except ValueError:
                raise ValueError("Параметр keep_chunks має бути числом.")
        return PruneHistoryCommand(
            name="prune_history",
            raw_target=raw_target,
            user_id=user_id,
            username=username,
            keep_chunks=keep_chunks,
        )

    if cmd == "delete_dialog":
        if not args:
            raise ValueError("Синтаксис: delete_dialog <user_id|@username>")
        raw_target = args[0]
        user_id, username = _parse_target(raw_target)
        return DeleteDialogCommand(
            name="delete_dialog",
            raw_target=raw_target,
            user_id=user_id,
            username=username,
        )

    if cmd == "help":
        return HelpCommand(name="help")

    if cmd == "exit":
        return ExitCommand(name="exit")

    raise ValueError("Невідома команда. Спробуйте 'help' для списку команд.")
