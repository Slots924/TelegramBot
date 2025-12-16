import asyncio
import json
import os
from datetime import datetime, timezone

from telethon import TelegramClient, events, functions, types, utils
from telethon.tl.types import Channel, Chat, User

from settings import ANSWER_TO_TELEGRAM_BOTS, HISTORY_BASE_DIR, USER_INFO_FILENAME
from .config import SESSION_DIR, SESSION_NAME, TELEGRAM_API_HASH, TELEGRAM_API_ID

class TelegramAPI:
    """Клас-обгортка для Telegram-клієнта (Telethon)."""

    def __init__(self, session_name: str | None = None, enable_incoming: bool = True):
        """Готує клієнт Telethon з обраним .session файлом.

        Параметри
        ----------
        session_name: str | None
            Назва .session файлу без розширення. Якщо не передано — береться
            значення з .env для основного користувача або окремо для адмін-консолі.
        enable_incoming: bool
            Дозволяє або забороняє підписуватися на вхідні події.
            Якщо False — клієнт працює лише на вихідні команди/читання історії,
            нові апдейти не слухаємо.
        """

        # Папка для зберігання .session (створюємо один раз на старті)
        os.makedirs(SESSION_DIR, exist_ok=True)

        # Вибір конкретного .session файлу залежно від сценарію використання
        target_session = session_name or SESSION_NAME
        session_path = os.path.join(SESSION_DIR, target_session)

        # Ініціалізуємо клієнт
        self.client = TelegramClient(session_path, TELEGRAM_API_ID, TELEGRAM_API_HASH)

        # Зберігаємо прапорець, чи потрібно слухати вхідні події
        self._enable_incoming = enable_incoming

        # Роутер ми підставимо пізніше через set_router()
        self._router = None

        # Реєструємо обробники тільки якщо вхідний потік дозволено
        if self._enable_incoming:
            # incoming=True — ловимо тільки повідомлення від інших користувачів
            self.client.add_event_handler(
                self._on_new_message,
                events.NewMessage(incoming=True)
            )
            # Ловимо оновлення по реакціях, щоб фіксувати, як користувачі реагують на наші відповіді.
            self.client.add_event_handler(self._on_message_reaction, events.Raw())

    def set_router(self, router) -> None:
        """Прив'язуємо роутер, який буде обробляти вхідні повідомлення."""
        self._router = router

    async def connect(self) -> None:
        """Підключається до Telegram, авторизує користувача при першому запуску."""
        await self.client.start()
        me = await self.client.get_me()
        print(f"✅ Авторизовано як: {me.first_name} (id: {me.id})")

    async def run(self) -> None:
        """Запускає нескінченне прослуховування повідомлень."""
        print("👂 Слухаю вхідні повідомлення... (Ctrl+C щоб вийти)")
        await self.client.run_until_disconnected()

    async def send_message(self, chat_id: int | str, text: str):
        """Надсилає повідомлення у вказаний чат (без reply) і повертає Message."""

        message = await self.client.send_message(chat_id, text)
        print(f"📨 Відправлено повідомлення в чат {chat_id}: {text}")
        return message

    async def download_voice_bytes(
        self, chat_id: int | str, message_id: int | None, file_id: int | None = None
    ) -> bytes | None:
        """Завантажує voice-повідомлення у байтах через Telethon.

        Параметри
        ----------
        chat_id: int | str
            Ідентифікатор чату, з якого потрібно забрати голосове повідомлення.
        message_id: int | None
            ID конкретного повідомлення з voice. Без нього завантаження неможливе.
        file_id: int | None
            ID файлу з метаданих (для логування та дебагу, не обов'язковий).
        
        Повертає
        --------
        bytes | None
            Байти voice-файлу або None у разі помилки/відсутності файлу.
        """

        if message_id is None:
            print(
                f"⚠️ Не вдалося завантажити voice: відсутній message_id (file_id={file_id})."
            )
            return None

        try:
            # Отримуємо саме те повідомлення, яке містить голосове медіа.
            message = await self.client.get_messages(chat_id, ids=message_id)
            print(
                "📨 Отримано повідомлення для voice",
                f"chat_id={chat_id}",
                f"message_id={message_id}",
                f"file_id={file_id}",
                f"payload_type={type(message)}",
            )
        except Exception as exc:
            print(
                f"⚠️ Не вдалося отримати повідомлення {message_id} для завантаження voice: {exc}"
            )
            return None

        # Якщо Telethon повернув список, витягаємо перший елемент.
        if isinstance(message, list):
            message = message[0] if message else None

        if message is None:
            print(
                f"⚠️ Не знайдено повідомлення (message_id={message_id}, file_id={file_id}) для voice."
            )
            return None

        try:
            # Використовуємо file=bytes, щоб одразу отримати байтовий вміст без збереження на диск.
            raw_bytes = await self.client.download_media(message, file=bytes)
            print(
                "⬇️ Спроба завантажити voice",
                f"chat_id={chat_id}",
                f"message_id={message_id}",
                f"file_id={file_id}",
            )

            # Telethon може повернути шлях до файлу, тому підстрахуємося і дочитаємо байти вручну.
            if isinstance(raw_bytes, str):
                raw_path = raw_bytes
                try:
                    with open(raw_path, "rb") as file:
                        raw_bytes = file.read()
                    print(
                        "📖 Дочитали voice з файлу",
                        f"path={raw_path}",
                        f"size={len(raw_bytes) if isinstance(raw_bytes, (bytes, bytearray)) else 'unknown'}",
                    )
                except Exception as exc:
                    print(
                        f"⚠️ Файл voice збережено у {raw_path}, але не вдалося прочитати: {exc}"
                    )
                    return None

            if not raw_bytes:
                print(
                    f"⚠️ Порожній результат при завантаженні voice (message_id={message_id}, file_id={file_id})."
                )
                return None

            print(
                "✅ Voice успішно завантажено",
                f"size={len(raw_bytes)} байт",
                f"first_32_bytes={raw_bytes[:32]!r}",
            )
            return raw_bytes
        except Exception as exc:
            print(
                f"⚠️ Помилка завантаження voice (message_id={message_id}, file_id={file_id}): {exc}"
            )
            return None

    async def fetch_unread_messages(self, chat_id: int | str) -> list[dict]:
        """Повертає всі непрочитані вхідні повідомлення у вигляді простих словників.

        Ми проходимося по повідомленнях з кінця діалогу (новіші першими) і
        зупиняємося, щойно натрапляємо на перше прочитане повідомлення.
        Це дозволяє не сканувати всю історію, якщо непрочитані лежать блоком.

        Відразу описуємо тип повідомлення через _detect_message_type, щоб
        отримати такий самий prepared_content, як під час онлайн-обробки.
        """

        unread_messages: list[dict] = []
        found_unread_block = False

        async for message in self.client.iter_messages(chat_id, limit=None):
            if getattr(message, "out", False):
                # Пропускаємо наші власні повідомлення, нас цікавлять тільки вхідні.
                continue

            if getattr(message, "unread", False):
                found_unread_block = True
                msg_type, prepared_content, media_meta = self._detect_message_type(message)
                unread_messages.append(
                    {
                        "id": getattr(message, "id", None),
                        "text": prepared_content,
                        "date": getattr(message, "date", None) or datetime.now(timezone.utc),
                        "msg_type": msg_type,
                        "media_meta": media_meta,
                    }
                )
            elif found_unread_block:
                # Якщо ми вже назбирали непрочитані та дійшли до прочитаного,
                # вважаємо, що блок непрочитаних завершився.
                break

        # Сортуємо за id, щоб у історії повідомлення збереглись у правильному порядку (від старого до нового).
        unread_messages.sort(key=lambda item: item.get("id") or 0)
        return unread_messages

    async def fetch_messages_after(
        self, chat_id: int | str, last_message_id: int, limit: int | None = None
    ) -> list[dict]:
        """Повертає всі вхідні повідомлення після last_message_id включно.

        Використовується для догрузки пропущених повідомлень навіть якщо вони вже
        позначені прочитаними. Якщо limit передано, зрізаємо результат до цього
        розміру з кінця (щоб залишились найновіші).
        """

        collected: list[dict] = []

        async for message in self.client.iter_messages(chat_id, min_id=last_message_id):
            if getattr(message, "out", False):
                continue

            msg_type, prepared_content, media_meta = self._detect_message_type(message)
            collected.append(
                {
                    "id": getattr(message, "id", None),
                    "text": prepared_content,
                    "date": getattr(message, "date", None) or datetime.now(timezone.utc),
                    "msg_type": msg_type,
                    "media_meta": media_meta,
                }
            )

        collected.sort(key=lambda item: item.get("id") or 0)

        if limit is not None and len(collected) > limit:
            collected = collected[-limit:]

        return collected

    async def fetch_dialog_messages_after(
        self, chat_id: int | str, last_message_id: int, limit: int = 50
    ) -> list[dict]:
        """Повертає як вхідні, так і вихідні повідомлення після last_message_id.

        Потрібно для синхронізації історії, коли потрібно підтягнути пропущені
        меседжі обох ролей. Обмежуємо результат максимально `limit` елементами,
        щоб не перевантажувати диск і пам'ять.
        """

        collected: list[dict] = []

        async for message in self.client.iter_messages(chat_id, min_id=last_message_id):
            msg_type, prepared_content, media_meta = self._detect_message_type(message)
            collected.append(
                {
                    "id": getattr(message, "id", None),
                    "text": prepared_content,
                    "date": getattr(message, "date", None) or datetime.now(timezone.utc),
                    "msg_type": msg_type,
                    "media_meta": media_meta,
                    "out": getattr(message, "out", False),
                }
            )

        collected.sort(key=lambda item: item.get("id") or 0)

        if len(collected) > limit:
            collected = collected[-limit:]

        return collected

    async def fetch_recent_incoming_messages(
        self, chat_id: int | str, limit: int = 20
    ) -> list[dict]:
        """Повертає останні N вхідних повідомлень користувача.

        Фільтруємо лише не наші повідомлення (out=False), щоб зібрати чисту
        історію користувача для ініціалізації діалогу.
        """

        collected: list[dict] = []

        async for message in self.client.iter_messages(chat_id, limit=limit):
            if getattr(message, "out", False):
                continue

            msg_type, prepared_content, media_meta = self._detect_message_type(message)
            collected.append(
                {
                    "id": getattr(message, "id", None),
                    "text": prepared_content,
                    "date": getattr(message, "date", None) or datetime.now(timezone.utc),
                    "msg_type": msg_type,
                    "media_meta": media_meta,
                }
            )

        collected.sort(key=lambda item: item.get("id") or 0)
        return collected

    async def mark_messages_read(self, chat_id: int | str, max_message_id: int) -> None:
        """Позначає повідомлення у чаті як прочитані до вказаного message_id включно."""

        try:
            await self.client.send_read_acknowledge(chat_id, max_id=max_message_id)
            print(
                f"👁 Позначено прочитаним чат {chat_id} до message_id={max_message_id}."
            )
        except Exception as exc:
            print(f"⚠️ Не вдалося позначити повідомлення прочитаними: {exc}")

    async def _on_new_message(self, event) -> None:
        """
        Внутрішній обробник Telethon.
        Викликається щоразу, коли приходить нове вхідне повідомлення.
        """
        # Якщо вхідні вимкнені (наприклад, адмін-консоль), одразу виходимо.
        if not self._enable_incoming:
            return

        # Обробляємо тільки приватні діалоги, групи та канали пропускаємо без логів.
        if not event.is_private:
            return

        if self._router is None:
            print("⚠️ Отримано повідомлення, але роутер не налаштований.")
            return

        sender = await event.get_sender()

        # Ігноруємо телеграм-ботів, якщо це заборонено налаштуванням.
        if not ANSWER_TO_TELEGRAM_BOTS and isinstance(sender, User) and getattr(sender, "bot", False):
            return

        # Безпечний витяг ID відправника: беремо з sender або з самого event
        # (наприклад, якщо sender == None для анонімних адмінів чи каналів).
        user_id = getattr(sender, "id", None) or getattr(event, "sender_id", None)
        if user_id is None:
            print("⚠️ Не вдалося визначити user_id для повідомлення, пропускаю обробку.")
            return

        chat_id = event.chat_id      # ID чату (для приватного = user_id)
        text = event.message.message # текст повідомлення або підпис до медіа
        message_date = event.message.date or datetime.now(timezone.utc)

        # Визначаємо тип повідомлення і будуємо стислий опис для LLM.
        # Використовуємо спільний детектор типів повідомлень, щоб однаково
        # описувати медіа як для онлайн-потоку, так і для ручної синхронізації.
        msg_type, prepared_content, media_meta = self._detect_message_type(event.message)

        print(
            "\n💬 Нове повідомлення від {user_id} в чаті {chat_id}: {text} | тип: {msg_type}".format(
                user_id=user_id,
                chat_id=chat_id,
                text=text,
                msg_type=msg_type,
            )
        )

        # Перевіряємо та зберігаємо user_info.txt, якщо його ще немає
        chat_title = getattr(event.chat, "title", None)
        self._ensure_user_info_file(
            user_id=user_id,
            sender=sender,
            chat_title=chat_title,
            is_private_chat=event.is_private,
        )

        try:
            # Позначаємо повідомлення як прочитане, щоби Telegram не показував "непрочитано".
            await event.mark_read()
        except Exception as exc:
            # Якщо не вдалось — просто лог, бо це не критично для подальшої логіки.
            print(f"⚠️ Не вдалося позначити повідомлення прочитаним: {exc}")

        # Передаємо в роутер для обробки (LLM, логіка, відповідь)
        await self._router.handle_incoming_message(
            user_id=user_id,
            chat_id=chat_id,
            content=prepared_content,
            msg_type=msg_type,
            media_meta=media_meta,
            message_time=message_date,
            message_id=getattr(event.message, "id", None),
        )

    def _detect_message_type(self, message) -> tuple[str, str, dict]:
        """Визначає тип повідомлення та повертає опис для історії/LLM.

        Параметри
        ----------
        message: telethon.tl.custom.message.Message
            Об'єкт повідомлення з Telethon (може прийти як із події, так і з iter_messages).

        Повертає
        --------
        tuple[str, str, dict]
            msg_type — назва типу (text, voice, audio, video_note, video, document, photo).
            content — короткий опис для історії/LLM.
            media_meta — словник із базовими метаданими.
        """

        if message.voice:
            media_meta = self._extract_audio_meta(message.voice, message)
            content = self._render_voice_description(media_meta)
            return "voice", content, media_meta

        if message.audio:
            media_meta = self._extract_audio_meta(message.audio, message)
            content = self._render_audio_description(media_meta)
            return "audio", content, media_meta

        if message.video_note:
            media_meta = self._extract_video_meta(message.video_note, message)
            content = self._render_video_note_description(media_meta)
            return "video_note", content, media_meta

        if message.video:
            media_meta = self._extract_video_meta(message.video, message)
            content = self._render_video_description(media_meta)
            return "video", content, media_meta

        if message.document:
            media_meta = self._extract_document_meta(message.document, message)
            content = self._render_document_description(media_meta)
            return "document", content, media_meta

        if message.photo:
            media_meta = self._extract_photo_meta(message.photo, message)
            content = self._render_photo_description(media_meta)
            return "photo", content, media_meta

        # Якщо медіа немає, вважаємо звичайним текстом.
        media_meta = {"caption": message.message or ""}
        return "text", message.message or "", media_meta

    @staticmethod
    def _extract_audio_meta(document, message) -> dict:
        """Дістає базові метадані для voice/audio файлів."""

        duration = None
        title = None
        performer = None
        file_name = None
        mime_type = getattr(document, "mime_type", None)

        for attribute in getattr(document, "attributes", []) or []:
            if isinstance(attribute, types.DocumentAttributeAudio):
                duration = getattr(attribute, "duration", None)
                title = getattr(attribute, "title", None)
                performer = getattr(attribute, "performer", None)
            if isinstance(attribute, types.DocumentAttributeFilename):
                file_name = getattr(attribute, "file_name", None)

        return {
            "file_id": getattr(document, "id", None),
            "duration": duration,
            "mime_type": mime_type,
            "file_name": file_name,
            "performer": performer,
            "title": title,
            "size": getattr(document, "size", None),
            "caption": message.message or "",
        }

    @staticmethod
    def _extract_video_meta(document, message) -> dict:
        """Дістає базові метадані для відео та video_note."""

        duration = None
        width = None
        height = None
        file_name = None
        mime_type = getattr(document, "mime_type", None)

        for attribute in getattr(document, "attributes", []) or []:
            if isinstance(attribute, types.DocumentAttributeVideo):
                duration = getattr(attribute, "duration", None)
                width = getattr(attribute, "w", None)
                height = getattr(attribute, "h", None)
            if isinstance(attribute, types.DocumentAttributeFilename):
                file_name = getattr(attribute, "file_name", None)

        return {
            "file_id": getattr(document, "id", None),
            "duration": duration,
            "mime_type": mime_type,
            "file_name": file_name,
            "width": width,
            "height": height,
            "size": getattr(document, "size", None),
            "caption": message.message or "",
        }

    @staticmethod
    def _extract_document_meta(document, message) -> dict:
        """Дістає базові метадані для документів (PDF, DOC тощо)."""

        file_name = None
        for attribute in getattr(document, "attributes", []) or []:
            if isinstance(attribute, types.DocumentAttributeFilename):
                file_name = getattr(attribute, "file_name", None)

        return {
            "file_id": getattr(document, "id", None),
            "file_name": file_name,
            "mime_type": getattr(document, "mime_type", None),
            "size": getattr(document, "size", None),
            "caption": message.message or "",
        }

    @staticmethod
    def _extract_photo_meta(photo, message) -> dict:
        """Дістає базові метадані для фотографій (приблизна роздільна здатність)."""

        width = None
        height = None
        # Беремо найбільший доступний розмір, щоб оцінити роздільну здатність.
        best_size = None
        for size in getattr(photo, "sizes", []) or []:
            if hasattr(size, "w") and hasattr(size, "h"):
                if best_size is None:
                    best_size = size
                else:
                    best_area = getattr(best_size, "w", 0) * getattr(best_size, "h", 0)
                    current_area = getattr(size, "w", 0) * getattr(size, "h", 0)
                    if current_area > best_area:
                        best_size = size

        if best_size:
            width = getattr(best_size, "w", None)
            height = getattr(best_size, "h", None)

        return {
            "file_id": getattr(photo, "id", None),
            "width": width,
            "height": height,
            "caption": message.message or "",
        }

    @staticmethod
    def _render_voice_description(media_meta: dict) -> str:
        """Формує текстовий опис для voice-повідомлення."""

        duration = media_meta.get("duration") or "unknown"
        return f"[VOICE_MESSAGE duration={duration}s]"

    @staticmethod
    def _render_audio_description(media_meta: dict) -> str:
        """Формує текстовий опис для аудіотреку."""

        duration = media_meta.get("duration") or "unknown"
        title = media_meta.get("title") or ""
        performer = media_meta.get("performer") or ""
        parts: list[str] = [f"[AUDIO_TRACK duration={duration}s"]
        if title:
            parts.append(f"title=\"{title}\"")
        if performer:
            parts.append(f"performer=\"{performer}\"")
        return " ".join(parts) + "]"

    @staticmethod
    def _render_video_note_description(media_meta: dict) -> str:
        """Формує текстовий опис для video note."""

        duration = media_meta.get("duration") or "unknown"
        return f"[VIDEO_NOTE duration={duration}s]"

    @staticmethod
    def _render_video_description(media_meta: dict) -> str:
        """Формує текстовий опис для відеофайлу."""

        duration = media_meta.get("duration") or "unknown"
        width = media_meta.get("width") or "?"
        height = media_meta.get("height") or "?"
        file_name = media_meta.get("file_name")
        file_part = f' file_name="{file_name}"' if file_name else ""
        return f"[VIDEO duration={duration}s resolution={width}x{height}{file_part}]"

    def _render_document_description(self, media_meta: dict) -> str:
        """Формує текстовий опис для документа."""

        file_name = media_meta.get("file_name") or "unknown"
        mime_type = media_meta.get("mime_type") or "unknown"
        size_str = self._format_size(media_meta.get("size"))
        caption = media_meta.get("caption")
        caption_part = f' caption="{caption}"' if caption else ""
        return (
            f"[DOCUMENT file_name=\"{file_name}\" mime_type=\"{mime_type}\" "
            f"size≈{size_str}{caption_part}]"
        )

    def _render_photo_description(self, media_meta: dict) -> str:
        """Формує текстовий опис для фотографії."""

        width = media_meta.get("width") or "?"
        height = media_meta.get("height") or "?"
        caption = media_meta.get("caption")
        caption_part = f' caption="{caption}"' if caption else ""
        return f"[PHOTO resolution≈{width}x{height}{caption_part}]"

    @staticmethod
    def _format_size(size_in_bytes: int | None) -> str:
        """Перетворює розмір у байтах у читабельний вигляд (KB/MB)."""

        if not size_in_bytes:
            return "unknown"

        try:
            kb_size = size_in_bytes / 1024
            if kb_size < 1024:
                return f"{kb_size:.0f}KB"
            mb_size = kb_size / 1024
            return f"{mb_size:.1f}MB"
        except Exception:
            return "unknown"

    async def send_typing(self, chat_id: int | str, duration: float) -> None:
        """Надсилає статус "typing" та чекає потрібний час.

        Parameters
        ----------
        chat_id: int | str
            Чат, у якому потрібно показати, що "бот" набирає текст.
        duration: float
            Скільки секунд підтримувати статус typing.
        """

        if duration <= 0:
            return

        try:
            # context manager Telethon сам зніме статус typing після виходу з блоку
            async with self.client.action(chat_id, "typing"):
                await asyncio.sleep(duration)
        except Exception as exc:
            print(f"⚠️ Не вдалося показати статус typing у чаті {chat_id}: {exc}")

    async def send_reaction(self, chat_id: int | str, message_id: int | str, emoji: str) -> None:
        """Ставитиме реакцію на конкретне повідомлення у чаті.

        Параметри
        ----------
        chat_id: int | str
            Ідентифікатор чату. Має бути додатнім цілим числом, інакше Telethon не зможе
            знайти потрібний діалог для реакції.
        message_id: int | str
            Ідентифікатор повідомлення, на яке ставимо реакцію.
        emoji: str
            Емодзі, яке потрібно додати як реакцію.
        """

        try:
            # Перетворюємо chat_id на додатнє число, оскільки Telethon очікує саме такий формат.
            prepared_chat_id = abs(int(chat_id))
            prepared_message_id = int(message_id)
        except (TypeError, ValueError) as exc:
            print(f"⚠️ Неможливо підготувати ідентифікатори для реакції: {exc}")
            return

        try:
            # Використовуємо низькорівневий запит, який стабільно працює із збереженими сесіями.
            await self.client(
                functions.messages.SendReactionRequest(
                    peer=prepared_chat_id,
                    msg_id=prepared_message_id,
                    reaction=[types.ReactionEmoji(emoticon=emoji)],
                    big=False,
                    add_to_recent=False,
                )
            )

            print(
                f"✅ Додано реакцію '{emoji}' у чаті {prepared_chat_id} для message_id={prepared_message_id}."
            )
        except Exception as exc:
            print(f"⚠️ Не вдалося поставити реакцію в чаті {chat_id}: {exc}")

    async def _on_message_reaction(self, update) -> None:
        """Реагує на оновлення реакцій і записує їх в історію діалогу.

        Запускається для сирих апдейтів Telethon. Ми відфільтровуємо лише UpdateMessageReactions,
        витягуємо користувача та емодзі, після чого зберігаємо факт реакції в історії.
        """

        if self._router is None:
            return

        if not isinstance(update, types.UpdateMessageReactions):
            return

        if not update.reactions or not update.reactions.recent_reactions:
            return

        chat_id = utils.get_peer_id(update.peer)
        message_id = getattr(update, "msg_id", None)
        message_time_iso = (
            update.date.astimezone(timezone.utc).isoformat()
            if getattr(update, "date", None)
            else datetime.now(timezone.utc).isoformat()
        )

        for recent_reaction in update.reactions.recent_reactions:
            user_id = utils.get_peer_id(recent_reaction.peer_id)
            emoji = getattr(recent_reaction.reaction, "emoticon", None) or "(unknown)"

            # Фіксуємо простановку реакції у історії з чітким форматом, який читається як людьми, так і LLM.
            self._router.history.append_message(
                user_id=user_id,
                role="user",
                content=f"[REACTION] '{emoji}' on message_id = {message_id}",
                message_time_iso=message_time_iso,
                # Зберігаємо ID повідомлення, на яке поставили реакцію, щоб
                # у контексті можна було зв'язати реакцію з конкретним меседжем.
                message_id=message_id,
            )

    def _ensure_user_info_file(
        self, user_id: int, sender, chat_title: str | None, is_private_chat: bool
    ) -> None:
        """Створює user_info.txt з профільними даними, якщо його ще немає.

        Якщо відправник невідомий або файл не вдалося записати, виводимо лог, але
        не зупиняємо роботу застосунку.
        """

        # Шлях до файлу з інформацією про користувача
        user_dir = os.path.join(HISTORY_BASE_DIR, f"user_{user_id}")
        os.makedirs(user_dir, exist_ok=True)
        user_info_path = os.path.join(user_dir, USER_INFO_FILENAME)

        if os.path.exists(user_info_path):
            return

        profile_data = self._build_profile_data(
            sender=sender,
            fallback_user_id=user_id,
            chat_title=chat_title if not is_private_chat else None,
        )

        try:
            with open(user_info_path, "w", encoding="utf-8") as file:
                file.write(self._render_user_info_block(profile_data))
            print(f"💾 Збережено user_info для {user_id} у {user_info_path}")
        except Exception as exc:
            print(f"⚠️ Не вдалося зберегти user_info.txt для {user_id}: {exc}")

    @staticmethod
    def _build_profile_data(
        sender, fallback_user_id: int, chat_title: str | None
    ) -> dict:
        """Збирає профільні дані користувача або групи в єдину структуру."""

        if sender is None:
            print("⚪ Відправник невідомий (None), заповнюю тільки наявні поля.")

        profile_data = {
            "id": getattr(sender, "id", None) if sender else fallback_user_id,
            "first_name": getattr(sender, "first_name", None) if sender else None,
            "last_name": getattr(sender, "last_name", None) if sender else None,
            "username": getattr(sender, "username", None) if sender else None,
            "bio": getattr(sender, "about", None) if sender else None,
            "chat_title": chat_title,
        }

        if isinstance(sender, (Channel, Chat)) and not profile_data["first_name"]:
            # Для групових чатів first_name/last_name зазвичай відсутні, тому підхоплюємо title
            profile_data["first_name"] = getattr(sender, "title", None)

        return profile_data

    @staticmethod
    def _render_user_info_block(profile_data: dict) -> str:
        """Формує текстовий блок USER_INFO для передачі в LLM."""

        # Текстовий опис про те, як використовувати метадані, додаємо перед JSON.
        header_lines = [
            "USER_INFO_BLOCK_START",
            "Це структуровані метадані про користувача Telegram, з яким ти зараз ведеш діалог.",
            "Використовуй їх лише для контексту (ім'я, стиль спілкування тощо), але НЕ показуй їх у відповідях дослівно.",
            "",
            f"USER_INFO = {json.dumps(profile_data, ensure_ascii=False, indent=2)}",
            "",
            "USER_INFO_BLOCK_END",
        ]
        return "\n".join(header_lines)
