import os
import base64
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


def process_image(message, file_id: str):
    """
    Общая функция обработки изображения — и для фото, и для документов.

    Пайплайн:
    1. Отправляем индикатор загрузки (чтобы пользователь не думал, что бот завис)
    2. Скачиваем файл из Telegram по file_id
    3. Кодируем в base64 (текстовый формат, понятный Vision API)
    4. Отправляем в Vision LLM через vision.py
    5. Возвращаем результат пользователю
    """

    # Шаг 1: Индикатор загрузки — критически важен для UX
    # Без него пользователь 10–15 секунд смотрит в пустоту
    loading_msg = bot.reply_to(message, "⏳ Анализирую состав...")

    try:
        # Шаг 2: Скачиваем файл из Telegram
        # file_id — это «номерок в гардеробе», по нему получаем информацию о файле
        file_info = bot.get_file(file_id)

        # download_file() скачивает содержимое файла как массив байтов
        file_bytes = bot.download_file(file_info.file_path)

        # Шаг 3: Кодируем в base64
        # base64 превращает бинарные данные (фото) в текстовую строку
        # Это нужно, потому что JSON (формат API-запроса) не умеет хранить бинарные данные
        image_base64 = base64.b64encode(file_bytes).decode("utf-8")

        # Определяем MIME-тип по расширению файла
        # MIME-тип — это «этикетка» файла: image/jpeg, image/png и т.д.
        file_path = file_info.file_path.lower()
        if file_path.endswith(".png"):
            mime_type = "image/png"
        elif file_path.endswith(".webp"):
            mime_type = "image/webp"
        else:
            mime_type = "image/jpeg"  # По умолчанию — JPEG (самый частый)

        # Шаг 4: Отправляем в Vision LLM
        result = analyze_image(image_base64, mime_type)

        # Шаг 5: Обрабатываем результат
        if result["success"]:
            # Удаляем сообщение «Анализирую...» — оно больше не нужно
            bot.delete_message(message.chat.id, loading_msg.message_id)

            # Отправляем анализ
            # Если текст длиннее 4096 символов (лимит Telegram), обрезаем
            response_text = result["text"]
            if len(response_text) > 4096:
                response_text = response_text[:4090] + "\n(...)"

            bot.send_message(message.chat.id, response_text)

            # Логируем метрики в консоль (позже — в Supabase)
            usage = result.get("usage", {})
            print(
                f"✅ Скан: модель={result.get('model', '?')}, "
                f"время={result.get('elapsed_seconds', '?')}с, "
                f"токены_вход={usage.get('input_tokens', 0)}, "
                f"токены_выход={usage.get('output_tokens', 0)}"
            )
        else:
            # Если API вернул ошибку — сообщаем пользователю
            bot.edit_message_text(
                f"Не удалось проанализировать фото. Попробуйте ещё раз через минуту.",
                chat_id=message.chat.id,
                message_id=loading_msg.message_id
            )
            print(f"❌ Ошибка Vision API: {result['error']}")

    except Exception as e:
        # Ловим любую непредвиденную ошибку — бот не должен «молча умереть»
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
    Telegram присылает массив photo — несколько версий разного размера.
    Берём последнюю ([-1]) — она самая большая и качественная.
    """
    file_id = message.photo[-1].file_id
    process_image(message, file_id)


@bot.message_handler(content_types=["document"])
def handle_document(message):
    """
    Обработчик документов (файлов, отправленных через «скрепку»).
    Файлы приходят в оригинальном качестве — без сжатия Telegram.
    """
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
    """Обработчик всех остальных сообщений (текст и прочее)."""
    bot.reply_to(message, "Пришлите фото состава продукта — я разберу его для вас.")


if __name__ == "__main__":
    print("Бот запущен...")
    bot.infinity_polling()
