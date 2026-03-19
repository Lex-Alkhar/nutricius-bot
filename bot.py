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
        "📸 Сфотографируй состав (не штрихкод, не лицевую сторону)\n"
        "📐 Подноси ближе — текст должен занимать большую часть кадра\n"
        "💡 Убери тени и блики\n"
        "📎 Лучше отправить как файл (скрепка), а не обычное фото — так качество выше\n"
        "\n"
        "Мы не храним твои фото и не используем их для обучения моделей.\n"
        "\n"
        "Просто пришли фото — начнём."
    )
    bot.reply_to(message, welcome_text)


@bot.message_handler(commands=["help"])
def handle_help(message):
    """Обработчик команды /help — краткая справка."""
    help_text = (
        "📸 Отправь фото состава продукта — я разберу его.\n"
        "\n"
        "Команды:\n"
        "/start — начало работы\n"
        "/help — эта справка\n"
        "\n"
        "Совет: отправляй фото как файл (📎) для лучшего качества."
    )
    bot.reply_to(message, help_text)


@bot.message_handler(content_types=["photo"])
def handle_photo(message):
    """Обработчик фото — заглушка для Этапа 0."""
    bot.reply_to(message, "📸 Фото получено! Анализ будет доступен на следующем этапе.")


@bot.message_handler(content_types=["document"])
def handle_document(message):
    """Обработчик документов (файлов) — заглушка для Этапа 0."""
    bot.reply_to(message, "📎 Файл получен! Анализ будет доступен на следующем этапе.")


@bot.message_handler(func=lambda message: True)
def handle_other(message):
    """Обработчик всех остальных сообщений."""
    bot.reply_to(message, "Пришли фото состава продукта — я разберу его для тебя.")


if __name__ == "__main__":
    print("Бот запущен...")
    bot.infinity_polling()
