"""
vision.py — модуль для работы с Vision LLM.

Отвечает за одну задачу: получить изображение (в формате base64) и
системный промпт, отправить их в Vision-модель, вернуть текстовый ответ.

Сейчас работает через OpenRouter API (формат совместим с OpenAI).
Модель по умолчанию: Gemini 2.5 Flash — оптимальное соотношение цена/качество.
Переключение на Claude Sonnet — замена одной переменной MODEL.
"""

import os
import time
import requests
from dotenv import load_dotenv

load_dotenv()

# ─── Настройки ────────────────────────────────────────────────────
# API-ключ OpenRouter — единая точка доступа ко всем моделям
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

# URL эндпоинта OpenRouter (совместим с форматом OpenAI)
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

# Модель для анализа. Чтобы переключиться на Claude — замени строку:
# MODEL = "anthropic/claude-sonnet-4"
MODEL = "google/gemini-2.5-flash"

# ─── Системный промпт ────────────────────────────────────────────
# Это «служебная инструкция» для модели. Пользователь её не видит.
# Определяет поведение, тон, формат ответа и правила анализа.
# Полная версия будет доработана на Этапе 3 (промпт-инжиниринг).

SYSTEM_PROMPT = """Ты — нутрициологический анализатор состава продуктов питания для русскоязычной аудитории.

ПЕРВЫЙ ШАГ: оцени качество фото.
Если список ингредиентов нечитаем, обрезан, закрыт бликом или отсутствует — верни строго JSON:
{"readable": false, "issue": "описание проблемы"}
Не пытайся анализировать нечитаемое фото.

ЕСЛИ ФОТО ЧИТАЕМО — проведи полный анализ.

ЗАДАЧА: объективно разобрать список ингредиентов с этикетки.

НОРМАТИВНАЯ БАЗА:
- Классификация переработки: NOVA 1–4 (Монтейру)
- Оценка добавок: стандарты EFSA
- Допустимые добавки в РФ/ЕАЭС: СанПиН 2.3.2.1293-03
- Нормы питания: рекомендации ВОЗ

ОБЯЗАТЕЛЬНЫЕ ПРАВИЛА:
1. Если ингредиент нечётко распознан → пиши «возможно: [название]»
2. Не делай медицинских выводов о конкретном человеке
3. Оценивай состав — не бренд, не упаковку, не цену
4. Псевдонимы сахара — выявлять все: декстроза, мальтодекстрин, фруктоза, кукурузный сироп, инвертный сироп, патока, концентрат фруктового сока, тростниковый сахар, рисовый сироп, ячменный солод
5. Маркетинговые манипуляции СНГ — выявлять расхождение между заявлениями и составом
6. Е-добавки: извлеки все Е-номера из состава и перечисли их отдельным блоком
7. В конце каждого ответа: «⚠️ Информационный анализ, не медицинская рекомендация.»
8. Тон: доступный, как объяснение другу с нутрициологическим образованием
9. Итоговый ответ не должен превышать 3500 символов

ФОРМАТ ОТВЕТА:

[Название продукта если читается на фото]

━━ ИНДИКАТОРЫ ━━
NOVA [1–4]: [однострочное пояснение]
Скрытый сахар: [N псевдонимов] 🟢/🟡/🔴
Качество жиров: [нейтрально / насыщенные / трансжиры] 🟢/🟡/🔴
Состав: [короткий до 5 / средний 6–15 / длинный 16+] 🟢/🟡/🔴

━━ РАЗБОР ━━
🔴 Стоп: [максимум 3 пункта — только реальные проблемы]
🟡 Внимание: [неочевидные вещи]
🟢 Норм: [если есть что отметить, иначе пропустить]

⚗️ Е-добавки: E[XXX] 🟢 E[YYY] 🟡 E[ZZZ] 🔴

[Блок маркетинговых манипуляций — если найдены]
🎭 Маркетинг vs реальность: [конкретное расхождение]

━━ ВЫВОД ━━
💬 [Брать или нет — 1–2 предложения с обоснованием]
📚 Знал ли ты: [один образовательный факт про найденный ингредиент]

⚠️ Информационный анализ, не медицинская рекомендация.

Язык вывода: русский всегда.
"""


def analyze_image(image_base64: str, mime_type: str = "image/jpeg") -> dict:
    """
    Отправляет изображение в Vision LLM и возвращает результат анализа.

    Параметры:
        image_base64 — изображение, закодированное в строку base64
        mime_type    — тип изображения: "image/jpeg", "image/png" и т.д.

    Возвращает словарь:
        {"success": True, "text": "ответ модели", "model": "...", "usage": {...}}
        или
        {"success": False, "error": "описание ошибки"}
    """

    if not OPENROUTER_API_KEY:
        return {"success": False, "error": "OPENROUTER_API_KEY не найден в .env"}

    # Формируем data URI — строку, которую API поймёт как «вот картинка»
    # Формат: data:image/jpeg;base64,/9j/4AAQSkZJRg...
    image_data_uri = f"data:{mime_type};base64,{image_base64}"

    # Тело запроса к OpenRouter (формат OpenAI-совместимый)
    payload = {
        "model": MODEL,
        "messages": [
            {
                "role": "system",
                "content": SYSTEM_PROMPT
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": "Проанализируй состав продукта на этом фото этикетки."
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": image_data_uri
                        }
                    }
                ]
            }
        ]
    }

    # Заголовки запроса
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        # HTTP-Referer и X-Title — идентификация приложения для OpenRouter
        "HTTP-Referer": "https://github.com/Lex-Alkhar/nutricius-bot",
        "X-Title": "Nutricius Bot"
    }

    try:
        # Засекаем время — нужно для метрики «< 15 секунд»
        start_time = time.time()

        # Отправляем POST-запрос к API
        response = requests.post(
            OPENROUTER_URL,
            headers=headers,
            json=payload,
            timeout=60  # Максимальное ожидание — 60 секунд
        )

        elapsed = round(time.time() - start_time, 1)

        # Проверяем HTTP-статус ответа
        # 200 = всё хорошо, 4xx = ошибка клиента, 5xx = ошибка сервера
        if response.status_code != 200:
            return {
                "success": False,
                "error": f"API вернул статус {response.status_code}: {response.text[:500]}"
            }

        data = response.json()

        # Извлекаем текст ответа из структуры OpenAI-формата
        text = data["choices"][0]["message"]["content"]

        # Собираем метаданные для логирования (Этап 6)
        usage = data.get("usage", {})

        return {
            "success": True,
            "text": text,
            "model": data.get("model", MODEL),
            "elapsed_seconds": elapsed,
            "usage": {
                "input_tokens": usage.get("prompt_tokens", 0),
                "output_tokens": usage.get("completion_tokens", 0),
                "total_tokens": usage.get("total_tokens", 0)
            }
        }

    except requests.exceptions.Timeout:
        return {"success": False, "error": "Таймаут: модель не ответила за 60 секунд"}
    except requests.exceptions.ConnectionError:
        return {"success": False, "error": "Ошибка соединения с OpenRouter API"}
    except Exception as e:
        return {"success": False, "error": f"Неожиданная ошибка: {str(e)}"}
