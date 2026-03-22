import os
import telebot
from dotenv import load_dotenv

# Загружаем переменные из .env файла
load_dotenv()

# Читаем токен бота из переменной окружения
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")

if not TELEGRAM_TOKEN:
    raise ValueError("TELEGRAM_TOKEN не найден. Проверь файл .env")

# Создаём экземпляр бота
bot = telebot.TeleBot(TELEGRAM_TOKEN)


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


@bot.message_handler(content_types=["photo"])
def handle_photo(message):
    """Обработчик фото — заглушка для Этапа 1."""
    bot.reply_to(message, "📸 Фото получено! Анализ будет доступен на следующем этапе.")


@bot.message_handler(content_types=["document"])
def handle_document(message):
    """Обработчик документов (файлов) — заглушка для Этапа 1."""
    # Проверяем, что это изображение, а не произвольный файл
    mime = message.document.mime_type or ""
    if mime.startswith("image/"):
        bot.reply_to(message, "📎 Фото получено как файл — отличное качество! Анализ будет доступен на следующем этапе.")
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
