"""
AI Card Generator — генерация структурированных карточек тендеров через Google Gemini.
"""

import json
from typing import Optional

import google.generativeai as genai

from config import GEMINI_API_KEY, GEMINI_MODEL, GEMINI_MAX_TOKENS
from utils.logger import logger


SYSTEM_PROMPT = """
Ты — аналитик закупок. Тебе дан текст страницы тендера или проекта.
Извлеки структурированную информацию и верни ТОЛЬКО JSON без markdown:

{
  "title": "краткое название",
  "project_id": "номер лота или проекта",
  "donor": "название донора/банка",
  "budget": "сумма в валюте",
  "pipe_diameter": "диаметр труб или null",
  "pipe_type": "тип труб (ПЭ/ПВХ/сталь/ВЧШГ) или null",
  "pipe_length_km": "протяжённость в км или null",
  "contractor": "подрядчик если известен или null",
  "tender_deadline": "дата дедлайна или null",
  "contract_completion": "дата завершения или null",
  "status": "Active|Signed|Planned|Unknown",
  "contact_email": "email или null",
  "contact_name": "контактное лицо или null",
  "region": "регион Таджикистана или null",
  "urgency": "HIGH|MEDIUM|LOW",
  "summary_ru": "2-3 предложения описания на русском"
}
""".strip()


async def generate_ai_card(
    title: str,
    description: str,
    source: str,
    url: str,
) -> Optional[dict]:
    """
    Генерирует AI-карточку тендера через Google Gemini.

    Вызывается ТОЛЬКО для новых тендеров (не повторно).
    Возвращает dict с извлечёнными данными или None при ошибке.
    """
    if not GEMINI_API_KEY:
        logger.warning("[AI] GEMINI_API_KEY не установлен — пропускаем генерацию карточки")
        return None

    user_message = f"""
Источник: {source}
Название: {title}
URL: {url}

Описание/текст страницы:
{description[:2000]}
""".strip()

    try:
        genai.configure(api_key=GEMINI_API_KEY)

        model = genai.GenerativeModel(
            model_name=GEMINI_MODEL,
            system_instruction=SYSTEM_PROMPT,
            generation_config=genai.GenerationConfig(
                max_output_tokens=GEMINI_MAX_TOKENS,
                temperature=0.1,
            ),
        )

        response = model.generate_content(user_message)
        response_text = response.text.strip()

        # Очищаем от возможных markdown-обёрток
        if response_text.startswith("```"):
            lines = response_text.split("\n")
            # Убираем первую и последнюю строки с ```
            lines = [l for l in lines if not l.strip().startswith("```")]
            response_text = "\n".join(lines)

        # Парсим JSON
        data = json.loads(response_text)
        logger.info("[AI] Карточка сгенерирована для: %s", title[:60])
        return data

    except json.JSONDecodeError as e:
        logger.error("[AI] Ошибка парсинга JSON ответа: %s", str(e))
        return None
    except Exception as e:
        error_msg = str(e).lower()
        if "quota" in error_msg or "rate" in error_msg or "429" in error_msg:
            logger.warning("[AI] Rate limit Gemini API: %s", str(e))
        elif "api_key" in error_msg or "401" in error_msg or "403" in error_msg:
            logger.error("[AI] Ошибка авторизации Gemini API: %s", str(e))
        else:
            logger.error("[AI] Неожиданная ошибка генерации карточки: %s", str(e))
        return None


def format_ai_card_markdown(data: dict) -> str:
    """Форматирует AI-карточку в Markdown для сохранения в БД."""
    lines = []
    mapping = {
        "title": "📌 Название",
        "project_id": "🔢 ID проекта",
        "donor": "🏦 Донор",
        "budget": "💰 Бюджет",
        "pipe_diameter": "🔩 Диаметр труб",
        "pipe_type": "🔧 Тип труб",
        "pipe_length_km": "📏 Протяжённость",
        "contractor": "🔨 Подрядчик",
        "tender_deadline": "📅 Дедлайн",
        "contract_completion": "✅ Завершение",
        "status": "📊 Статус",
        "contact_email": "📧 Email",
        "contact_name": "👤 Контакт",
        "region": "📍 Регион",
        "urgency": "⚡ Срочность",
        "summary_ru": "📝 Описание",
    }

    for key, label in mapping.items():
        value = data.get(key)
        if value and value != "null" and str(value).lower() != "none":
            lines.append(f"{label}: {value}")

    return "\n".join(lines)
