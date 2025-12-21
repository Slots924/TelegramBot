# AGENTS.md

> Інструкції для AI-асистентів / кодогенераторів, які працюють з цим репозиторієм.

## 1. Призначення проєкту

Telegram-клієнт на Python (User API через Telethon), який:

- приймає повідомлення від звичайних юзерів (НЕ бот),
- пересилає їх у LLM (Grok 4 Fast) через HTTP API,
- зберігає історію діалогів по користувачах,
- формує контекст (system prompt + історія) для кожного запиту,
- очікує від LLM JSON-список дій (send_message / send_messages / fake_typing / add_reaction / wait / ignore),
- відправляє результат назад у Telegram і логує помилки.

LLM зараз: **Grok 4 Fast** (через окремий `llm_api` модуль).

---

## 2. Важливо про автора

- Автор — **новачок** у Python / async / архітектурі.
- Будь-який згенерований код:

  - **коментувати українською**, максимально явно.
  - Докстрінг кожного класу/функції: що робить, які параметри, що повертає.
  - Пояснювати ключові змінні та нетривіальні місця (особливо async / стани / черги).
  - Не використовувати “магію” і надто компактні трюки, краще прості й читабельні рішення.

Ціль — щоб автор **зрозумів логіку**, а не просто “запустив”.

---

## 3. Структура проєкту

Орієнтовна структура (може розширюватися, але базова логіка така):

```text
project_root/
├── AGENTS.md                  # інструкції для AI-асистентів
├── .env                       # секрети та конфіг (Telegram, Grok, історія, промпти)
├── .gitignore
├── requirements.txt
├── data/                      # робочі дані, що не є кодом
│   ├── dialogs/               # user_<id>/chunk_XXXX.json (створюються під час роботи)
│   └── system_prompts/        # *.txt файли системних промптів
└── src/
    ├── main.py                # точка входу, збирає всі сервіси й запускає цикл
    │
    ├── telegram_api/          # робота з Telegram (Telethon, User API)
    │   ├── __init__.py
    │   ├── config.py          # TELEGRAM_API_ID, TELEGRAM_API_HASH, SESSION_NAME з .env
    │   ├── telegram_api.py    # клас TelegramAPI: конект, слухачі, надсилання повідомлень
    │   ├── sessions/          # .session файли Telethon (НЕ в git)
    │   └── handlers/          # (опціонально) додаткові Telegram-хендлери
    │
    ├── llm_api/               # робота з LLM (Grok 4 Fast)
    │   ├── __init__.py
    │   ├── config.py          # ключі LLM, параметри запиту, шлях до system prompt
    │   ├── llm_api.py         # клас LLMAPI: метод generate(messages: list[dict]) -> str
    │   ├── hendlers/          # місце під майбутні LLM-хендлери
    │   └── utils/             # допоміжні утиліти (завантаження system prompt тощо)
    │
    ├── history/               # зберігання історії діалогів
    │   ├── __init__.py
    │   ├── config.py          # HISTORY_BASE_DIR, MAX_MESSAGES_PER_CHUNK, MAX_CHUNKS_FOR_CONTEXT
    │   ├── history_manager.py # клас HistoryManager: append_message(), get_recent_context()
    │   ├── hendlers/          # місце під додаткові обробники історії
    │   └── utils/             # допоміжні утиліти для історії
    │
    ├── router/                # “мозок” — зв'язує Telegram, історію та LLM
    │   ├── __init__.py
    │   ├── llm_router.py      # клас LLMRouter: стани, debounce, виклики LLM, парсинг JSON-дiй
    │   ├── actions/           # окремі обробники дій (send_message, fake_typing, add_reaction тощо)
    │   ├── hendlers/          # місце під додаткові роутерні хендлери
    │   └── utils/             # допоміжні утиліти роутера
    │
    ├── speech_to_text/        # розпізнавання голосових повідомлень
    │   ├── service.py         # точка входу для STT
    │   └── google_client.py   # робота з Google Speech-to-Text
    │
    └── admin_console/         # CLI для адмінів (синхронізація, прокидка повідомлень)
```

---

## 4. Обов’язки модулів

### 4.1 `telegram_api`

**config.py**

- Зчитує з `.env`:
  - `TELEGRAM_API_ID`
  - `TELEGRAM_API_HASH`
  - `SESSION_NAME` (назва .session файлу)

**telegram_api.py / клас `TelegramAPI`**

- Методи (цільовий інтерфейс):

  - `async def connect()`: підключення до Telegram, старт сесії.
  - `async def run()`: `client.run_until_disconnected()`, постійне прослуховування.
  - `def set_router(router)`: зберегти посилання на `LLMRouter`.
  - `async def send_message(chat_id: int | str, text: str)`: відправити текст у чат (без reply).
  - `async def send_typing(chat_id: int, duration_seconds: float)`: показати статус набору.
  - `async def fetch_dialog_messages_after(...)`: службовий метод для адмін-консолі.

- В обробнику нових повідомлень (Telethon `events.NewMessage(incoming=True)`):

  - Дістати `user_id`, `chat_id`, текст або опис медіа.
  - Передати в роутер:
    - `await router.handle_incoming_message(user_id, chat_id, text, msg_type, media_meta, message_time, message_id)`.

- **Не містить** логіки LLM, історії, платних функцій — тільки транспорт + делегування в роутер.

---

### 4.2 `llm_api` (Grok 4 Fast)

**config.py**

- Зчитує з `.env`:

  - `LLM_API_KEY`
  - `LLM_BASE_URL`
  - `LLM_MODEL`

- Бере з `settings.py`:

  - `LLM_TEMPERATURE`, `LLM_MAX_TOKENS`, `LLM_TOP_P` (параметри запиту)
  - `LLM_PRESENCE_PENALTY`, `LLM_FREQUENCY_PENALTY` (поки не використовуються, але читаються)
  - `SYSTEM_PROMPTS_DIR` (дефолт: `data/system_prompts`)
  - `SYSTEM_PROMPT_NAME` (без `.txt`, напр. `default`)

**llm_api.py / клас `LLMAPI`**

- Єдиний публічний метод:

  - `def generate(self, messages: list[dict]) -> str`

- Формат `messages`:

  - список словників: `{"role": "system"|"user"|"assistant", "content": "..."}`

- Усередині:

  - Формування HTTP-запиту до API Grok,
  - відправка списку `messages`,
  - отримання відповіді,
  - повернення **чистого тексту** першого completion.

- **Клієнт не знає** про Telegram, історію або стейти — тільки LLM.

---

### 4.3 `history` (HistoryManager)

**config.py**

- Бере з `settings.py`:

  - `HISTORY_BASE_DIR` (дефолт: `data/dialogs`)
  - `HISTORY_MAX_MESSAGES_PER_CHUNK` (наприклад, 20 — це ~10 пар запит/відповідь)
  - `HISTORY_MAX_CHUNKS_FOR_CONTEXT` (наприклад, 5 — скільки останніх файлів брати в контекст)

**Структура на диску**

```text
data/dialogs/
  user_123456789/
    chunk_0001.json
    chunk_0002.json
  user_987654321/
    chunk_0001.json
```

**history_manager.py / клас `HistoryManager`**

- Основні методи:

  - `append_message(user_id: int, role: str, content: str, message_time_iso: str | None, message_id: int | None) -> None`  
    Додає запис виду:
    ```json
    {
      "role": "user" | "assistant",
      "content": "текст",
      "created_at": "ISO-час",
      "message_id": 123
    }
    ```
    у поточний чанк `chunk_XXXX.json` користувача `user_id`.  
    Якщо кількість повідомлень ≥ `HISTORY_MAX_MESSAGES_PER_CHUNK` — створює новий чанк.

  - `get_recent_context(user_id: int) -> list[dict]`  
    Повертає плоский список повідомлень з кількох останніх чанків (кількість = `HISTORY_MAX_CHUNKS_FOR_CONTEXT`).

  - Додатково є допоміжні методи для синхронізації (отримання останніх message_id).

- **Не знає** про Telegram, Grok, статуси, typing тощо. Працює тільки з файлами та user_id.

---

### 4.4 `router` (LLMRouter)

**Мета:**  
Головний “агент”, який:

- приймає сирі повідомлення від `TelegramAPI`,
- веде стани по користувачах,
- зберігає/читає історію,
- формує контекст для Grok,
- викликає Grok, який повертає **список JSON-дiй**,
- відправляє відповіді через `TelegramAPI`.

**Стан по кожному користувачу (в пам'яті):**

`state[user_id] = { inbox, busy, last_activity, debounce_handle? }`, де:

- `inbox: list[str]` — непрочитані/необроблені текстові повідомлення (буфер).
- `busy: bool` — чи йде зараз цикл відповіді (генерація/typing) для цього юзера.
- `last_activity: datetime` — час останнього вхідного повідомлення.
- `debounce` — механізм очікування 2–3 секунд “тиші” перед стартом відповіді.

**Логіка обробки (пер-юзер цикл):**

1. **Нове повідомлення від Telegram:**

   - Додати `text` (або транскрипцію voice) у `state[user_id].inbox`.
   - Оновити `last_activity`.
   - Якщо `busy == True` → нічого більше не робити (піде у наступний цикл).
   - Якщо `busy == False`:
     - якщо немає активного debounce → запустити debounce (2–3 секунди очікування).
     - якщо debounce вже є → оновити `inbox` і час, не стартувати новий.

2. **Debounce (2–3 с):**

   - Чекає певний час після останнього повідомлення.
   - Якщо за цей час не прийшло нових повідомлень → стартує цикл відповіді.
   - Якщо прийшло нове повідомлення → оновлюється `inbox`, відлік починається знову.

3. **Старт циклу відповіді для юзера:**

   - Встановити `busy[user_id] = True`.
   - Зробити snapshot `batch_messages` = все з `inbox[user_id]`, після чого `inbox[user_id]` очистити (нові меседжі підуть уже в наступний цикл).
   - Записати усі `batch_messages` в історію (`HistoryManager.append_message(role="user", ...)`).
   - Отримати контекст з історії: `history_messages = HistoryManager.get_recent_context(user_id)`.

4. **Формування LLM-контексту:**

   - Завантажити system prompt із `data/system_prompts` (ім'я задається у `SYSTEM_PROMPT_NAME` в `settings.py`).
   - За потреби додати `actions` промпт і `user_info.txt` для конкретного user_id.
   - Побудувати список `messages` для Grok:
     - `{"role": "system", "content": system_prompt}`
     - далі всі `history_messages` у форматі `{"role": "user"/"assistant", "content": "..."}` з датами та message_id.

5. **Виклик LLM:**

   - Викликати `GrokAPI.generate(messages)`.
   - Отримати `answer: str` із JSON-списком дій.
   - Якщо JSON не валідний — **лог** і **ніяких відправок у Telegram**.
   - Далі кожен action передається у відповідний хендлер з папки `router/actions`.

6. **Typing-імітація:**

   - `fake_typing` може прийти окремою дією.
   - Також перед `send_message` може викликатися `send_typing` з параметром human_seconds.

7. **Виконання екшенів:**

   - `send_message`/`send_messages` — надсилають текст(и) та пишуть в історію.
   - `fake_typing` — показує статус набору без відправки.
   - `add_reaction` — реакція на конкретний message_id.
   - `wait` — просто пауза між діями.
   - `ignore` — робимо нічого, але не падаємо.

8. **Завершення циклу:**

   - Якщо `inbox[user_id]` порожній → `busy[user_id] = False`.
   - Якщо у `inbox[user_id]` вже є нові повідомлення:
     - не викликати LLM відразу,
     - запустити новий debounce (2–3 секунди) і повторити з пункту 3.

**Додатково (для подальшої реалізації):**

- Ліміт одночасних викликів Grok (глобальний семафор / пул).
- Ліміт розміру `inbox[user_id]` і довжини контексту.
- Команди адмін-консолі можуть синхронізувати історію без виклику LLM.

---

### 4.5 `system_prompts/`

- `.txt` файли з текстом системних промптів.

  - `SYSTEM_PROMPTS_DIR` — шлях до папки (дефолт: `data/system_prompts`),
  - `SYSTEM_PROMPT_NAME` — ім’я файлу без `.txt`.

- Роутер при старті має:

  - прочитати файл `${SYSTEM_PROMPTS_DIR}/${SYSTEM_PROMPT_NAME}.txt`,
  - зберегти в змінну `system_prompt`,
  - використовувати його як перше повідомлення `role="system"` у кожному LLM-запиті.

---

## 5. Стиль коду

- Коментарі — **українською**, чіткі, по суті.
- Обов’язково:
  - докстрінг для кожного класу,
  - докстрінг для кожної публічної функції/методу.
- В асинхронному коді (`async/await`) пояснювати:
  - де і що саме “чекає”,
  - де можливе блокування,
  - де відбувається робота паралельно.
- Якщо LLM повертає невалідний JSON — не відправляти сирий текст користувачу, лише логувати.

- Не додавати зайвих сторонніх бібліотек без потреби.
- Не змішувати шари:
  - TelegramAPI ≠ LLM логіка,
  - LLM API ≠ історія,
  - HistoryManager ≠ транспорт.

Цей файл — орієнтир для будь-якого AI, який буде дописувати чи змінювати код у цьому проєкті.
