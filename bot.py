import os
import base64
from datetime import datetime, timezone, timedelta
import telebot
from dotenv import load_dotenv
from vision import analyze_image

# Загружаем переменные из .env файла
load_dotenv()

# Читаем токен бота из переменной окружения
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")

if not TELEGRAM_TOKEN:
    raise ValueError("TELEGRAM_TOKEN не найден. Проверь файл .env")

# Создаём экземпляр бота
bot = telebot.TeleBot(TELEGRAM_TOKEN)


# ─── Rate Limiting (in-memory) ────────────────────────────────────
#
# Временное решение до подключения Supabase (Этап 6).
# Данные хранятся в оперативной памяти — при перезапуске бота
# (каждый деплой) счётчики сбрасываются.
#
# DAILY_LIMIT = 50 — тестовый режим (для бета-теста)
# Вернуть на 5 перед публичным запуском.

DAILY_LIMIT = 50  # ← ТЕСТОВЫЙ РЕЖИМ. Продакшен: 5
scan_counter = {}

# Часовой пояс Москвы (UTC+3)
MSK = timezone(timedelta(hours=3))


def check_rate_limit(user_id: int) -> dict:
    """Проверяет дневной лимит пользователя."""
    today = datetime.now(MSK).strftime("%Y-%m-%d")

    if user_id not in scan_counter:
        scan_counter[user_id] = {"date": today, "count": 0}

    user_data = scan_counter[user_id]

    if user_data["date"] != today:
        user_data["date"] = today
        user_data["count"] = 0

    remaining = DAILY_LIMIT - user_data["count"]

    if user_data["count"] >= DAILY_LIMIT:
        return {"allowed": False, "remaining": 0}

    return {"allowed": True, "remaining": remaining}


def increment_scan(user_id: int):
    """Увеличивает счётчик сканов для пользователя."""
    today = datetime.now(MSK).strftime("%Y-%m-%d")

    if user_id not in scan_counter:
        scan_counter[user_id] = {"date": today, "count": 0}

    scan_counter[user_id]["count"] += 1


# ─── Обработка изображения ────────────────────────────────────────

def process_image(message, file_id: str):
    """
    Общая функция обработки изображения — и для фото, и для документов.

    Пайплайн:
    1. Проверяем rate limit
    2. Отправляем индикатор загрузки
    3. Скачиваем файл из Telegram по file_id
    4. Кодируем в base64
    5. Отправляем в Vision LLM через vision.py
    6. Возвращаем результат пользователю
    7. Увеличиваем счётчик сканов
    """

    user_id = message.from_user.id

    # Шаг 1: Проверяем rate limit
    limit_check = check_rate_limit(user_id)
    if not limit_check["allowed"]:
        bot.reply_to(
            message,
            f"На сегодня лимит исчерпан ({DAILY_LIMIT} из {DAILY_LIMIT}). "
            f"Завтра счётчик сбросится."
        )
        return

    # Шаг 2: Индикатор загрузки
    loading_msg = bot.reply_to(message, "⏳ Анализирую состав...")

    try:
        # Шаг 3: Скачиваем файл из Telegram
        file_info = bot.get_file(file_id)
        file_bytes = bot.download_file(file_info.file_path)

        # Шаг 4: Кодируем в base64
        image_base64 = base64.b64encode(file_bytes).decode("utf-8")

        # Определяем MIME-тип по расширению файла
        file_path = file_info.file_path.lower()
        if file_path.endswith(".png"):
            mime_type = "image/png"
        elif file_path.endswith(".webp"):
            mime_type = "image/webp"
        else:
            mime_type = "image/jpeg"

        # Шаг 5: Отправляем в Vision LLM
        result = analyze_image(image_base64, mime_type)

        # Шаг 6: Обрабатываем результат
        if result["success"]:
            increment_scan(user_id)
            remaining = DAILY_LIMIT - scan_counter[user_id]["count"]

            # Удаляем «Анализирую...»
            bot.delete_message(message.chat.id, loading_msg.message_id)

            # Формируем ответ
            response_text = result["text"]

            # Лимит Telegram — 4096 символов
            if len(response_text) > 4096:
                response_text = response_text[:4090] + "\n(...)"

            bot.send_message(message.chat.id, response_text)

            # Логируем метрики
            usage = result.get("usage", {})
            print(
                f"✅ Скан: user={user_id}, модель={result.get('model', '?')}, "
                f"время={result.get('elapsed_seconds', '?')}с, "
                f"токены_вход={usage.get('input_tokens', 0)}, "
                f"токены_выход={usage.get('output_tokens', 0)}, "
                f"осталось={remaining}/{DAILY_LIMIT}"
            )
        else:
            bot.edit_message_text(
                "Не удалось проанализировать фото. Попробуйте ещё раз через минуту.",
                chat_id=message.chat.id,
                message_id=loading_msg.message_id
            )
            print(f"❌ Ошибка Vision API: {result['error']}")

    except Exception as e:
        bot.edit_message_text(
            "Что-то пошло не так. Попробуйте ещё раз.",
            chat_id=message.chat.id,
            message_id=loading_msg.message_id
        )
        print(f"❌ Ошибка обработки: {str(e)}")


# ─── Обработчики команд ──────────────────────────────────────────

@bot.message_handler(commands=["start"])
def handle_start(message):
    """Обработчик команды /start — онбординг нового пользователя."""
    welcome_text = (
        "Привет! Я анализирую составы продуктов по фото.\n"
        "\n"
        "Как получить лучший результат:\n"
        "📸 Сфотографируйте состав (не штрихкод, не лицевую сторону)\n"
        "📐 Поднесите ближе — текст должен занимать большую часть кадра\n"
        "💡 Уберите тени и блики\n"
        "📎 Лучше отправить как файл (скрепка), а не обычное фото — так качество выше\n"
        "\n"
        "Мы не храним ваши фото и не используем их для обучения моделей.\n"
        "\n"
        "Просто пришлите фото — начнём."
    )
    bot.reply_to(message, welcome_text)


@bot.message_handler(commands=["help"])
def handle_help(message):
    """Обработчик команды /help — краткая справка."""
    help_text = (
        "📸 Отправьте фото состава продукта — я разберу его.\n"
        "\n"
        "Команды:\n"
        "/start — начало работы\n"
        "/help — эта справка\n"
        "\n"
        "Совет: отправляйте фото как файл (📎) для лучшего качества."
    )
    bot.reply_to(message, help_text)


# ─── Обработчики контента ─────────────────────────────────────────

@bot.message_handler(content_types=["photo"])
def handle_photo(message):
    """
    Обработчик фото (сжатых Telegram).
    Берём последний элемент массива photo — самый качественный.
    """
    file_id = message.photo[-1].file_id
    process_image(message, file_id)


@bot.message_handler(content_types=["document"])
def handle_document(message):
    """Обработчик документов (файлов через «скрепку»)."""
    mime = message.document.mime_type or ""
    if mime.startswith("image/"):
        file_id = message.document.file_id
        process_image(message, file_id)
    else:
        bot.reply_to(message, "Я работаю только с фотографиями. Пришлите фото состава продукта.")


@bot.message_handler(content_types=["voice", "audio"])
def handle_voice(message):
    """Обработчик голосовых и аудио."""
    bot.reply_to(message, "Я не обрабатываю голосовые сообщения. Пришлите, пожалуйста, фото состава продукта.")


@bot.message_handler(content_types=["sticker"])
def handle_sticker(message):
    """Обработчик стикеров."""
    bot.reply_to(message, "Пришлите фото состава продукта — я разберу его для вас.")


@bot.message_handler(func=lambda message: True)
def handle_other(message):
    """Обработчик всех остальных сообщений."""
    bot.reply_to(message, "Пришлите фото состава продукта — я разберу его для вас.")


if __name__ == "__main__":
    print(f"Бот запущен. Лимит: {DAILY_LIMIT} сканов/день (ТЕСТОВЫЙ РЕЖИМ).")
    bot.infinity_polling()
