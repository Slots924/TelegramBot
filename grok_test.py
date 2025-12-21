import os
import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("LLM_API_KEY")
MODEL = os.getenv("LLM_MODEL")
BASE_URL = os.getenv("LLM_BASE_URL")

headers = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json",
}

messages = [
    {
        "role": "system",
        "content": "You are a test assistant. Respond normally."
    }
]

print("Grok console test. Напиши 'exit' щоб вийти.\n")

while True:
    user_input = input("YOU > ")
    if user_input.lower() in ("exit", "quit"):
        break

    messages.append({
        "role": "user",
        "content": user_input
    })

    payload = {
        "model": MODEL,
        "messages": messages,
        "temperature": 0.7,
        # можна додати якщо хочеш тестити зациклення
        # "frequency_penalty": 0.5,
        # "presence_penalty": 0.5,
    }

    try:
        response = requests.post(
            BASE_URL,
            headers=headers,
            json=payload,
            timeout=60
        )
        response.raise_for_status()
        data = response.json()

        # ВИВОДИМО ВСЕ — щоб подивитись reasoning / структуру
        print("\nRAW RESPONSE:")
        print(data)

        assistant_message = data["choices"][0]["message"]["content"]

        print("\nGROK >")
        print(assistant_message)
        print()

        messages.append({
            "role": "assistant",
            "content": assistant_message
        })

    except Exception as e:
        print("ERROR:", e)
