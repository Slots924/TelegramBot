import os
from google.cloud import speech
from google.protobuf.json_format import MessageToJson

# === НАЛАШТУВАННЯ ===

# Шлях до JSON з гуглівським Service Account ключем
GOOGLE_CREDENTIALS_PATH = r"C:\Users\Darkness\Documents\Projects\TelegramBot\speach_to_text_credential.json"

# Файл з Telegram .ogg (Opus)
audio_file_path = r"C:\Users\Darkness\Documents\Projects\TelegramBot\audio.mp3"

# Мови (імітація автодетекту)
PRIMARY_LANGUAGE = "uk-UA"
ALT_LANGUAGES = ["ru-RU", "en-US"]


# === Перевірка файлів ===

if not os.path.exists(GOOGLE_CREDENTIALS_PATH):
    print(f"⚠️ Файл креденшіалів не знайдено: {GOOGLE_CREDENTIALS_PATH}")
    exit(1)

if not os.path.exists(audio_file_path):
    print(f"⚠️ Аудіофайл не знайдено: {audio_file_path}")
    exit(1)

os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = GOOGLE_CREDENTIALS_PATH


# === Читаємо аудіо ===

with open(audio_file_path, "rb") as f:
    content = f.read()

audio = speech.RecognitionAudio(content=content)


# === Налаштування для OGG/OPUS ===
# Telegram voice = OPUS @ 48000Hz

config = speech.RecognitionConfig(
    encoding=speech.RecognitionConfig.AudioEncoding.OGG_OPUS,
    sample_rate_hertz=48000,  # ГОЛОВНЕ! Telegram = 48kHz
    language_code=PRIMARY_LANGUAGE,
    alternative_language_codes=ALT_LANGUAGES,
)


print("=== НАЛАШТУВАННЯ ===")
print(f"Файл: {audio_file_path}")
print("Encoding: OGG_OPUS")
print("sample_rate_hertz: 48000")
print(f"Основна мова: {PRIMARY_LANGUAGE}")
print(f"Альтернативні: {ALT_LANGUAGES}")
print("=====================\n")


# === Відправляємо у Google Speech-to-Text ===

client = speech.SpeechClient()

print("Відправляю файл до Google Speech-to-Text v1...\n")

try:
    response = client.recognize(config=config, audio=audio)
except Exception as e:
    print("❌ Помилка при виклику Speech-to-Text API:")
    print(repr(e))
    exit(1)


# === RAW JSON для відладки ===

print("=== RAW RESPONSE (JSON) ===")
try:
    raw_json = MessageToJson(response)
    print(raw_json)
except Exception as e:
    print("⚠️ Не вдалося конвертувати у JSON:", repr(e))
    print("repr(response):")
    print(repr(response))
print("=== END RAW RESPONSE ===\n")


# === Фінальний текст ===

print("=== РЕЗУЛЬТАТ РОЗПІЗНУВАННЯ ===")
if not response.results:
    print("Нічого не розпізнано 🥲")
else:
    for i, result in enumerate(response.results, start=1):
        alt = result.alternatives[0]
        print(f"[Фрагмент #{i}]")
        print("Текст:", alt.transcript)
        print("Впевненість:", f"{alt.confidence:.2%}")
        print("-" * 40)

print("Готово!")
