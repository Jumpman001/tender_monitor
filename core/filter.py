"""
Фильтр проектов:
1. Только Таджикистан (отсеиваем Армению, Кыргызстан и др.)
2. Ключевые слова водоснабжения/ирригации
3. Диаметр труб DN ≥ 400 мм (если указан)
4. Исключаем завершённые проекты
"""

import re
from typing import Optional
from utils.logger import logger
from config import MIN_PIPE_DIAMETER_MM


# ─── УРОВЕНЬ 1: Ключевые слова (русский + английский + таджикский) ──
KEYWORDS_INCLUDE = [
    # Английский
    "water supply", "irrigation", "sewage", "sanitation", "pipeline",
    "pipe", "drainage", "wastewater", "water main", "aqueduct",
    "pumping station", "reservoir", "water distribution",
    "water infrastructure", "water treatment", "water network",
    "transmission main", "trunk main", "ductile iron",
    "hdpe pipe", "steel pipe", "pvc pipe",
    # Русский
    "водоснабжение", "ирригация", "канализация", "трубопровод",
    "труба", "водовод", "дренаж", "мелиорация", "насосная станция",
    "распределительная сеть", "магистральный", "водоотведение",
    "водопровод", "напорная труба", "чугунная труба",
    "полиэтиленовая труба", "стальная труба",
    # Таджикский
    "обёрешикии об", "ирригатсия", "лӯлакашӣ",
]

# ─── УРОВЕНЬ 2: Паттерны для извлечения DN ──────────────────────────
DN_PATTERNS = [
    r"DN[\s\-]?(\d{3,})",                       # DN400, DN-560, DN 930
    r"[dD]iameter[\s:]?\s?(\d{3,})",             # diameter 400, Diameter: 560
    r"(\d{3,4})\s?мм",                           # 930 мм, 560мм
    r"PN[\s\-]?\d+.*DN[\s\-]?(\d{3,})",          # PN10 DN400
    r"(\d{3,4})\s?mm",                           # 930 mm, 560mm
    r"Ø\s?(\d{3,})",                             # Ø 400, Ø560
    r"(?:диаметр|диаметром)[\s:]?\s?(\d{3,})",   # диаметр 400
]


# ─── Страны, которые НЕ являются Таджикистаном ────────────────────────
OTHER_COUNTRIES = [
    # Соседи и частые ложные срабатывания
    "armenia", "армени", "kyrgyzstan", "кыргыз", "кыргызстан",
    "uzbekistan", "узбекистан", "kazakhstan", "казахстан",
    "turkmenistan", "туркменистан", "afghanistan", "афганистан",
    "pakistan", "пакистан", "georgia", "грузи",
    # Другие страны
    "bangladesh", "nepal", "sri lanka", "mongolia", "myanmar",
    "vietnam", "cambodia", "laos", "philippines",
    "indonesia", "india", "kenya", "nigeria", "ethiopia",
    "mozambique", "tanzania", "uganda", "senegal",
]

# ─── Статусы завершённых проектов ─────────────────────────────────────
COMPLETED_STATUSES = [
    "completed", "closed", "завершён", "завершен", "cancelled",
    "отменён", "отменен", "expired", "withdrawn",
]


def _extract_diameters(text: str) -> list[int]:
    """Извлекает все найденные диаметры из текста."""
    diameters = []
    for pattern in DN_PATTERNS:
        matches = re.findall(pattern, text, re.IGNORECASE)
        for m in matches:
            try:
                d = int(m)
                if 100 <= d <= 5000:  # разумный диапазон
                    diameters.append(d)
            except ValueError:
                continue
    return diameters


def _has_keywords(text: str) -> bool:
    """Проверяет наличие ключевых слов в тексте."""
    text_lower = text.lower()
    return any(kw.lower() in text_lower for kw in KEYWORDS_INCLUDE)


def _is_other_country(text: str) -> bool:
    """
    Проверяет, относится ли проект к ДРУГОЙ стране (не Таджикистан).
    Возвращает True если проект НЕ про Таджикистан.
    """
    text_lower = text.lower()

    # Если явно упомянут Таджикистан — ОК
    if "tajikistan" in text_lower or "таджикистан" in text_lower:
        return False

    # Если упомянута другая страна без Таджикистана — отфильтровываем
    for country in OTHER_COUNTRIES:
        if country in text_lower:
            return True

    # Нет явного указания страны — пропускаем (определим позже)
    return False


def _is_completed(status: str) -> bool:
    """Проверяет, завершён ли проект."""
    if not status:
        return False
    status_lower = status.lower().strip()
    return any(s in status_lower for s in COMPLETED_STATUSES)


def extract_pipe_diameter(text: str) -> Optional[str]:
    """Извлекает строку описания диаметра из текста."""
    diameters = _extract_diameters(text)
    if not diameters:
        return None
    max_dn = max(diameters)
    if max_dn >= MIN_PIPE_DIAMETER_MM:
        return f"DN {max_dn} мм"
    return f"DN {max_dn} мм"


def passes_filter(
    title: str,
    description: str = "",
    status: str = "",
    region: str = "",
) -> bool:
    """
    Трёхуровневая фильтрация проекта.

    УРОВЕНЬ 0: Страна — только Таджикистан.
    УРОВЕНЬ 0.5: Статус — исключаем завершённые.
    УРОВЕНЬ 1: Ключевые слова водоснабжения/ирригации.
    УРОВЕНЬ 2: Диаметр труб (если указан — DN ≥ 400).

    Returns:
        True если проект проходит фильтр.
    """
    combined_text = f"{title} {description} {region}"

    # УРОВЕНЬ 0: Страна — только Таджикистан
    if _is_other_country(combined_text):
        logger.debug("Фильтр: другая страна → %s", title[:60])
        return False

    # УРОВЕНЬ 0.5: Исключаем завершённые проекты
    if _is_completed(status):
        logger.debug("Фильтр: завершённый проект → %s", title[:60])
        return False

    # УРОВЕНЬ 1: ключевые слова
    if not _has_keywords(combined_text):
        logger.debug("Фильтр: нет ключевых слов → %s", title[:60])
        return False

    # УРОВЕНЬ 2: диаметр
    diameters = _extract_diameters(combined_text)

    if diameters:
        max_dn = max(diameters)
        if max_dn < MIN_PIPE_DIAMETER_MM:
            logger.debug(
                "Фильтр: DN %d < %d → %s", max_dn, MIN_PIPE_DIAMETER_MM, title[:60]
            )
            return False
        logger.info("Фильтр PASS: DN %d ≥ %d → %s", max_dn, MIN_PIPE_DIAMETER_MM, title[:60])
    else:
        # Диаметр не упомянут, но ключевые слова есть — ВКЛЮЧАЕМ (уточним через AI)
        logger.info("Фильтр PASS (без DN, есть keywords) → %s", title[:60])

    return True
