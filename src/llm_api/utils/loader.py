"""Функції для завантаження системних промптів із файлів."""

from __future__ import annotations

import os
from typing import Optional

from src.llm_api.config import SYSTEM_PROMPTS_DIR, SYSTEM_PROMPT_NAME


def load_system_prompt(prompt_name: Optional[str] = None) -> str:
    """Повертає вміст системного промпта з текстового файлу.

    Args:
        prompt_name: назва файлу без суфікса .txt. Якщо не задано, береться
            значення з конфігурації `SYSTEM_PROMPT_NAME`.

    Returns:
        Рядок із текстом промпта. Якщо файл не знайдено — повертаємо простий
        запасний текст, щоби бот міг працювати далі.
    """

    name = prompt_name or SYSTEM_PROMPT_NAME
    filename = f"{name}.txt"
    path = os.path.join(SYSTEM_PROMPTS_DIR, filename)

    try:
        with open(path, "r", encoding="utf-8") as file:
            prompt = file.read().strip()
            print(f"📄 Завантажено system prompt: {filename}")
            return prompt
    except FileNotFoundError:
        print(f"⚠️ System prompt {filename} не знайдено в {SYSTEM_PROMPTS_DIR}. Використовую дефолт.")
        return "Ти асистент. Відповідай коротко і зрозуміло."
