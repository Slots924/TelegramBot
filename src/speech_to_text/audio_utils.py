"""Утиліти для обрізки та конвертації аудіо у формат, який приймає Google."""

import os
import shutil
import uuid
from typing import Iterable

from pydub import AudioSegment

from .config import STT_MAX_SECONDS, STT_TMP_DIR


def save_temp_copy(audio_input: bytes | str) -> str:
    """
    Зберігає аудіо (байти або файл) у тимчасову директорію.

    :param audio_input: сирі байти або шлях до файлу з аудіо.
    :return: шлях до тимчасового файлу у STT_TMP_DIR.
    """

    os.makedirs(STT_TMP_DIR, exist_ok=True)
    temp_path = os.path.join(STT_TMP_DIR, f"raw_{uuid.uuid4().hex}.ogg")

    if isinstance(audio_input, bytes):
        # Якщо прийшли байти, просто записуємо їх у файл
        with open(temp_path, "wb") as file:
            file.write(audio_input)
    else:
        # Якщо прийшов шлях, копіюємо його у тимчасове місце, щоб можна було легко прибрати
        shutil.copy(audio_input, temp_path)

    return temp_path


def load_audio_segment(file_path: str) -> AudioSegment:
    """
    Завантажує аудіо у AudioSegment для подальшої обробки.

    :param file_path: шлях до файлу, який треба прочитати.
    :return: AudioSegment з даними аудіо.
    """

    return AudioSegment.from_file(file_path)


def trim_audio(segment: AudioSegment, duration_seconds: float) -> AudioSegment:
    """
    Обрізає аудіо до потрібної довжини за секундами.

    :param segment: AudioSegment з оригінальним аудіо.
    :param duration_seconds: фактична тривалість вхідного аудіо.
    :return: AudioSegment, обрізаний до STT_MAX_SECONDS.
    """

    max_seconds = min(duration_seconds, STT_MAX_SECONDS)
    max_ms = int(max_seconds * 1000)
    return segment[:max_ms]


def convert_to_ogg_opus(segment: AudioSegment) -> tuple[bytes, str]:
    """
    Конвертує аудіо у формат OGG_OPUS 48000Hz.

    :param segment: AudioSegment після обрізки.
    :return: кортеж з байтами готового файлу та шляхом до тимчасового файлу.
    """

    prepared_segment = segment.set_frame_rate(48000).set_channels(1)

    output_path = os.path.join(STT_TMP_DIR, f"prepared_{uuid.uuid4().hex}.ogg")
    # Експортуємо у файл, щоб можна було підчистити після використання
    prepared_segment.export(output_path, format="ogg", codec="opus")

    # Читаємо у пам'ять, щоб віддати у Google API
    with open(output_path, "rb") as file:
        audio_bytes = file.read()

    return audio_bytes, output_path


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


def prepare_audio_bytes(audio_input: bytes | str, duration_seconds: float) -> tuple[bytes, list[str]]:
    """
    Повний цикл підготовки аудіо: зберегти, обрізати, сконвертувати.

    :param audio_input: байти або шлях до файлу з вхідним аудіо.
    :param duration_seconds: тривалість оригінального аудіо, щоб обрізати до ліміту.
    :return: байти готового файлу та список створених шляхів (для прибирання).
    """

    temp_files: list[str] = []

    # 1. Зберігаємо копію у тимчасову директорію
    temp_raw_path = save_temp_copy(audio_input)
    temp_files.append(temp_raw_path)

    # 2. Завантажуємо у AudioSegment для обрізки
    segment = load_audio_segment(temp_raw_path)

    # 3. Обрізаємо до ліміту
    trimmed_segment = trim_audio(segment, duration_seconds)

    # 4. Конвертуємо у потрібний формат
    audio_bytes, prepared_path = convert_to_ogg_opus(trimmed_segment)
    temp_files.append(prepared_path)

    return audio_bytes, temp_files

