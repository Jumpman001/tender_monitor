"""
Фильтр тендеров по ключевым словам и диаметру труб DN ≥ 400 мм.
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


def extract_pipe_diameter(text: str) -> Optional[str]:
    """Извлекает строку описания диаметра из текста."""
    diameters = _extract_diameters(text)
    if not diameters:
        return None
    max_dn = max(diameters)
    if max_dn >= MIN_PIPE_DIAMETER_MM:
        return f"DN {max_dn} мм"
    return f"DN {max_dn} мм"


def passes_filter(title: str, description: str = "") -> bool:
    """
    Двухуровневая фильтрация тендера.

    УРОВЕНЬ 1: Проверка ключевых слов — если нет, сразу отфильтровываем.
    УРОВЕНЬ 2: Если упомянут диаметр < 400 — отфильтровываем.
               Если диаметр ≥ 400 или не упомянут — ВКЛЮЧАЕМ.

    Returns:
        True если тендер проходит фильтр.
    """
    combined_text = f"{title} {description}"

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
