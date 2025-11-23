import asyncio

from telethon import TelegramClient, functions, types

# 🔧 КОНСТАНТИ ДЛЯ ТЕСТУ — ЗАМІНИ НА СВОЇ ЗНАЧЕННЯ

API_ID = 35934866                 # твій Telegram API ID
API_HASH = "a162b2f155166bc7a50a26bad642414f"  # твій Telegram API HASH

# ВИКОРИСТОВУЄМО ВЖЕ ГОТОВУ СЕСІЮ З ОСНОВНОГО ПРОЄКТУ
SESSION_PATH = r"C:\Users\Darkness\Documents\Projects\TelegramBot\src\telegram_api\sessions\user_session.session"

CHAT_ID = 380758126         # ID чата, де лежить повідомлення (int або @username)
MESSAGE_ID = 1935               # ID конкретного повідомлення в цьому чаті
EMOJI = "👍"                     # яку реакцію ставимо


async def main() -> None:
    # Ініціалізуємо клієнт з уже існуючою сесією
    client = TelegramClient(SESSION_PATH, API_ID, API_HASH)

    await client.start()
    me = await client.get_me()
    print(f"✅ Авторизовано як: {me.first_name} (id: {me.id})")

    try:
        msg_id = int(MESSAGE_ID)
        print(f"🟡 Ставлю реакцію '{EMOJI}' в чаті {CHAT_ID} на message_id={msg_id}...")

        await client(
            functions.messages.SendReactionRequest(
                peer=CHAT_ID,
                msg_id=msg_id,
                reaction=[types.ReactionEmoji(emoticon=EMOJI)],
                big=False,
                add_to_recent=False,
            )
        )

        print("✅ Реакцію успішно додано.")

    except Exception as exc:
        print(f"❌ Помилка при спробі поставити реакцію: {exc}")
    finally:
        await client.disconnect()
        print("👋 Клієнт відключено.")


if __name__ == "__main__":
    asyncio.run(main())
