# import asyncio
# from src.telegram_api.telegram_api import TelegramAPI

# async def main():
#     tg = TelegramAPI()
#     await tg.connect()

#     # Можна протестити відправку перед стартом прослуховування
#     await tg.send_message("me", "👋 Привіт! Я тепер слухаю всі повідомлення.")

#     # Запускаємо нескінченне прослуховування
#     await tg.run()




# if __name__ == "__main__":
#     try:
#         asyncio.run(main())
#     except KeyboardInterrupt:
#         print("\n🛑 Зупинено вручну.")








from src.llm_api.mistral_api import MistralAPI

def main():
    llm = MistralAPI()

    user_text = "Привіт! Поясни коротко, що таке LLM простою мовою."
    system_prompt = "Ти дружній асистент, який відповідає коротко і зрозуміло."

    print("👤 Користувач:", user_text)
    answer = llm.send_message(user_text, system_prompt=system_prompt)
    print("🤖 Відповідь LLM:")
    print(answer)

if __name__ == "__main__":
    main()