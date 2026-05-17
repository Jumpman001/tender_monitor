"""
AI Card Generator — генерация структурированных карточек проектов через Google Gemini.
Фокус: водоснабжение, водоотведение, ирригация, канализация, замена труб в Таджикистане.
"""

import json
from typing import Optional

import google.generativeai as genai

from config import GEMINI_API_KEY, GEMINI_MODEL, GEMINI_MAX_TOKENS
from utils.logger import logger


SYSTEM_PROMPT = """
Ты — аналитик проектов водоснабжения и ирригации в Таджикистане.
Тебе дан текст страницы проекта, тендера или закупки.

Твоя задача — извлечь максимум информации о проекте и определить его текущую стадию.

Верни ТОЛЬКО JSON без markdown:

{
  "title": "краткое название проекта",
  "project_id": "номер лота, проекта или контракта",
  "project_type": "одно из: Водоснабжение | Водоотведение | Ирригация | Канализация | Замена труб | Насосные станции | Водохранилище | Комплексный проект | Иное",
  "donor": "название донора/банка (World Bank, ADB, IsDB, EBRD, UNDP, GIZ, USAID и т.д.)",
  "implementing_agency": "организация-исполнитель (PMU, министерство, компания)",
  "budget": "сумма в валюте",
  
  "project_stage": "одно из: 🔵 Подготовка | 🟡 Тендер объявлен | 🟠 Оценка заявок | 🔴 Контракт подписан | 🏗 Строительство | ✅ Завершён | ⏸ Приостановлен",
  "stage_detail": "подробности стадии (например: 'Приём заявок до 30.06.2026', 'Идёт оценка 5 заявок', 'Подрядчик мобилизован на площадке' и т.д.)",
  "tender_deadline": "дата дедлайна подачи заявок (YYYY-MM-DD) или null",
  "contract_start": "дата начала контракта или null",
  "contract_completion": "дата завершения или null",
  
  "pipe_diameter": "диаметр труб (DN XXX мм) или null",
  "pipe_type": "тип труб (ПЭ/ПВХ/сталь/ВЧШГ/чугун/стеклопластик) или null",
  "pipe_length_km": "протяжённость трубопровода в км или null",
  
  "contractor": "подрядчик если известен или null",
  "status": "Active|Signed|Planned|Completed|Cancelled",
  
  "contact_name": "контактное лицо (ФИО) или null",
  "contact_position": "должность контактного лица или null",
  "contact_email": "email или null",
  "contact_phone": "телефон или null",
  "contact_organization": "организация контактного лица или null",
  "contact_address": "адрес для подачи заявок или null",
  
  "region": "район/город Таджикистана (Душанбе, Хатлон, Согд, ГБАО, РРП и т.д.) или null",
  "beneficiaries": "число или описание бенефициаров (например: '50,000 жителей Яванского района') или null",
  
  "urgency": "HIGH|MEDIUM|LOW",
  "summary_ru": "3-4 предложения: что за проект, на какой стадии, когда дедлайн, с кем связаться"
}

ВАЖНО:
- project_stage определяй по контексту: если есть дедлайн подачи в будущем → 'Тендер объявлен'
- Если контракт подписан → 'Контракт подписан' или 'Строительство'
- Если проект одобрен но тендера ещё нет → 'Подготовка'
- summary_ru должен быть максимально полезным для бизнесмена, который хочет продать трубы
""".strip()


async def generate_ai_card(
    title: str,
    description: str,
    source: str,
    url: str,
) -> Optional[dict]:
    """
    Генерирует AI-карточку проекта через Google Gemini.

    Вызывается ТОЛЬКО для новых записей (не повторно).
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
        "project_type": "🏗 Тип проекта",
        "donor": "🏦 Донор",
        "implementing_agency": "🏛 Исполнитель",
        "budget": "💰 Бюджет",
        "project_stage": "📊 Стадия",
        "stage_detail": "📋 Детали стадии",
        "pipe_diameter": "🔩 Диаметр труб",
        "pipe_type": "🔧 Тип труб",
        "pipe_length_km": "📏 Протяжённость",
        "contractor": "🔨 Подрядчик",
        "tender_deadline": "📅 Дедлайн подачи",
        "contract_start": "🚀 Начало контракта",
        "contract_completion": "✅ Завершение",
        "status": "⚡ Статус",
        "contact_name": "👤 Контакт",
        "contact_position": "💼 Должность",
        "contact_email": "📧 Email",
        "contact_phone": "📞 Телефон",
        "contact_organization": "🏢 Организация",
        "contact_address": "📮 Адрес подачи",
        "region": "📍 Регион",
        "beneficiaries": "👥 Бенефициары",
        "urgency": "🚨 Срочность",
        "summary_ru": "📝 Описание",
    }

    for key, label in mapping.items():
        value = data.get(key)
        if value and value != "null" and str(value).lower() != "none":
            lines.append(f"{label}: {value}")

    return "\n".join(lines)
