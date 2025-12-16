"""Утиліти для збереження та обрізки аудіо у форматі OGG/OPUS."""

import os
import shutil
import subprocess
import uuid
from typing import Iterable

from .config import STT_MAX_SECONDS, STT_TMP_DIR


def _run_ffmpeg(arguments: list[str]) -> None:
    """
    Виконує команду ffmpeg та піднімає зрозумілу помилку у випадку невдачі.

    :param arguments: повний список аргументів для виклику ffmpeg.
    """

    print("🎬 Запускаємо ffmpeg з аргументами:", " ".join(arguments))
    process = subprocess.run(
        ["ffmpeg", *arguments],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    print("📄 ffmpeg STDOUT:")
    print(process.stdout)
    print("⚠️ ffmpeg STDERR:")
    print(process.stderr)

    if process.returncode != 0:
        error_message = (
            "Не вдалося виконати ffmpeg. "
            f"Код: {process.returncode}. STDOUT: {process.stdout}. STDERR: {process.stderr}"
        )
        raise RuntimeError(error_message)


def save_temp_copy(audio_input: bytes | str) -> str:
    """
    Зберігає аудіо (байти або файл) у тимчасову директорію для подальшої обробки.

    :param audio_input: сирі байти або шлях до файлу з аудіо.
    :return: шлях до тимчасового файлу у STT_TMP_DIR.
    """

    os.makedirs(STT_TMP_DIR, exist_ok=True)
    temp_path = os.path.join(STT_TMP_DIR, f"raw_{uuid.uuid4().hex}.ogg")

    if isinstance(audio_input, bytes):
        # Якщо прийшли байти, просто записуємо їх у файл
        with open(temp_path, "wb") as file:
            file.write(audio_input)
        print(
            "💾 Збережено сирі байти у тимчасовий файл",
            temp_path,
            f"(розмір={len(audio_input)} байт)",
        )
    else:
        # Якщо прийшов шлях, копіюємо його у тимчасове місце, щоб можна було легко прибрати
        shutil.copy(audio_input, temp_path)
        print(
            "📂 Скопійовано аудіо у тимчасовий файл",
            temp_path,
            f"з джерела={audio_input}",
        )

    return temp_path


def trim_audio(file_path: str, duration_seconds: float) -> str:
    """
    Обрізає аудіо до максимально допустимої довжини.

    :param file_path: шлях до вихідного аудіо.
    :param duration_seconds: фактична тривалість вхідного аудіо.
    :return: шлях до обрізаного файлу у тимчасовій директорії.
    """

    safe_duration = min(duration_seconds, STT_MAX_SECONDS)
    trimmed_path = os.path.join(STT_TMP_DIR, f"trimmed_{uuid.uuid4().hex}.ogg")

    # -t задає тривалість вихідного файлу у секундах
    print(
        "✂️ Обрізаємо аудіо",
        f"вхідний файл={file_path}",
        f"оголошена тривалість={duration_seconds}s",
        f"безпечна тривалість={safe_duration}s",
        f"вихідний файл={trimmed_path}",
    )

    _run_ffmpeg([
        "-y",  # перезаписати, якщо файл існує
        "-i",
        file_path,
        "-t",
        str(safe_duration),
        "-c",
        "copy",
        trimmed_path,
    ])

    return trimmed_path


def cleanup_temp_files(paths: Iterable[str]) -> None:
    """
    Видаляє тимчасові файли, які були створені під час обробки.

    :param paths: послідовність шляхів, що треба видалити.
    """

    for path in paths:
        if not path:
            continue
        if os.path.exists(path):
            os.remove(path)
            print(f"🗑️ Видалено тимчасовий файл {path}")
        else:
            print(f"ℹ️ Тимчасовий файл вже відсутній або не існує: {path}")


def prepare_audio_bytes(audio_input: bytes | str, duration_seconds: float) -> tuple[bytes, list[str]]:
    """
    Повний цикл підготовки аудіо: зберегти та за потреби обрізати OGG/OPUS.

    :param audio_input: байти або шлях до файлу з вхідним аудіо.
    :param duration_seconds: тривалість оригінального аудіо, щоб обрізати до ліміту.
    :return: байти готового файлу та список створених шляхів (для прибирання).
    """

    temp_files: list[str] = []

    # 1. Зберігаємо копію у тимчасову директорію
    temp_raw_path = save_temp_copy(audio_input)
    temp_files.append(temp_raw_path)

    # 2. Обрізаємо до ліміту через ffmpeg
    trimmed_path = trim_audio(temp_raw_path, duration_seconds)
    temp_files.append(trimmed_path)

    # 3. Читаємо байти готового OGG-файлу без додаткової конвертації
    with open(trimmed_path, "rb") as file:
        audio_bytes = file.read()

    print(
        "📦 Підготовка аудіо завершена",
        f"raw_file={temp_raw_path}",
        f"trimmed_file={trimmed_path}",
        f"фінальний розмір={len(audio_bytes)} байт",
    )

    return audio_bytes, temp_files
