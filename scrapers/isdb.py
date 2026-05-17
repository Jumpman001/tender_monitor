"""
IsDB Scraper v2 — исправленная версия.

ПРОБЛЕМА оригинала:
1. isdb.org/procurement — JS-рендеринг → BeautifulSoup получает пустой HTML
2. Фильтр по "tajikistan" слишком строгий — отсеивает если страна в другом поле
3. URL https://www.isdb.org/procurement?country=Tajikistan — параметр не работает

РЕШЕНИЕ:
- Используем IsDB Business Gateway (BGATE) — отдельный портал закупок IsDB
  URL: https://bgate.isdb.org — имеет публичный поиск без JS
- Парсим страницу проектов IsDB по Таджикистану (статичная HTML)
- Используем DevelopmentAid как резервный источник для IsDB тендеров
"""

import re
import feedparser
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlencode

from scrapers.base import BaseScraper
from utils.logger import logger


class IsDBScraper(BaseScraper):

    def __init__(self):
        super().__init__("IsDB")

    async def scrape(self) -> list[dict]:
        results = []

        # 1. IsDB BGATE — бизнес-портал закупок IsDB (без JS)
        bgate = await self._scrape_bgate()
        results.extend(bgate)
        logger.info("[IsDB] BGATE: %d", len(bgate))
        await self.delay()

        # 2. IsDB Projects страница по Таджикистану (статичный HTML)
        projects = await self._scrape_isdb_projects()
        results.extend(projects)
        logger.info("[IsDB] Projects: %d", len(projects))
        await self.delay()

        # 3. Поиск IsDB тендеров через DevelopmentAid RSS (агрегатор)
        da = await self._scrape_via_developmentaid()
        results.extend(da)
        logger.info("[IsDB] via DevelopmentAid: %d", len(da))

        logger.info("[IsDB] ИТОГО: %d", len(results))
        return results

    # ──────────────────────────────────────────────────────────────────────────
    # 1. IsDB BGATE — бизнес-портал закупок
    # ──────────────────────────────────────────────────────────────────────────
    async def _scrape_bgate(self) -> list[dict]:
        """
        IsDB Business Gateway — отдельный портал закупок.
        https://bgate.isdb.org/CPP/EN/home.aspx
        Форма поиска тендеров по стране.
        """
        results = []

        # Поиск по Tajikistan через параметры формы
        search_urls = [
            "https://bgate.isdb.org/CPP/EN/SearchTender.aspx?country=TJ",
            "https://bgate.isdb.org/CPP/EN/SearchTender.aspx",
        ]

        for url in search_urls:
            html = await self.fetch(url)
            if not html:
                continue

            try:
                soup = BeautifulSoup(html, "lxml")

                # Таблица тендеров на BGATE
                table = soup.select_one(
                    "table#dgTenders, table.GridView, table[id*='Grid'], "
                    "table[id*='Tender'], table[id*='tender']"
                )
                if not table:
                    # Попробуем любую таблицу с данными
                    tables = soup.select("table")
                    for t in tables:
                        rows = t.select("tr")
                        if len(rows) > 2:  # Больше 2 строк = есть данные
                            table = t
                            break

                if not table:
                    logger.debug("[IsDB] BGATE: таблица не найдена на %s", url[:50])
                    continue

                rows = table.select("tr")
                for row in rows[1:]:  # Пропускаем заголовок
                    try:
                        cells = row.select("td")
                        if len(cells) < 2:
                            continue

                        # Обычно: [Project, Country, Description, Deadline, Status]
                        title = cells[0].get_text(strip=True)
                        if not title or len(title) < 5:
                            continue

                        link_el = cells[0].select_one("a") or cells[1].select_one("a")
                        link = ""
                        if link_el:
                            link = link_el.get("href", "")
                            if link and not link.startswith("http"):
                                link = urljoin("https://bgate.isdb.org", link)

                        country = cells[1].get_text(strip=True) if len(cells) > 1 else ""
                        deadline = cells[-2].get_text(strip=True) if len(cells) > 2 else ""
                        status = cells[-1].get_text(strip=True) if len(cells) > 1 else "Active"

                        # Фильтр по Tajikistan — ищем в любой ячейке строки
                        row_text = row.get_text().lower()
                        if "tajikistan" not in row_text and "TJ" not in row.get_text():
                            # Если URL уже содержит ?country=TJ — берём все строки
                            if "country=TJ" not in url:
                                continue

                        results.append({
                            "source": "IsDB BGATE",
                            "title": title,
                            "url": link or url,
                            "donor": "Islamic Development Bank",
                            "tender_deadline": deadline if deadline else None,
                            "region": country or "Tajikistan",
                            "status": status if status else "Active",
                        })
                    except Exception as e:
                        logger.debug("[IsDB] BGATE row error: %s", e)
                        continue

                if results:
                    break  # Нашли данные — второй URL не нужен

            except Exception as e:
                logger.error("[IsDB] BGATE error: %s", e)

        return results

    # ──────────────────────────────────────────────────────────────────────────
    # 2. IsDB PROJECTS PAGE — статичный HTML список проектов
    # ──────────────────────────────────────────────────────────────────────────
    async def _scrape_isdb_projects(self) -> list[dict]:
        """
        IsDB Projects страница по Таджикистану.
        Это статичный HTML (не приложение) — парсится нормально.
        Показывает одобренные проекты = потенциальные будущие тендеры.
        """
        # Страница проектов IsDB по стране
        url = "https://www.isdb.org/tajikistan"
        results = []

        html = await self.fetch(url)
        if not html:
            # Попробуем через поиск
            url = "https://www.isdb.org/en/projects?country=Tajikistan"
            html = await self.fetch(url)

        if not html:
            logger.warning("[IsDB] Projects страница недоступна")
            return results

        try:
            soup = BeautifulSoup(html, "lxml")

            # Ищем карточки или строки проектов
            items = soup.select(
                ".project-card, .views-row, article, "
                ".field--name-title, .project-item, li.project"
            )

            if not items:
                # Fallback: ищем все ссылки в main content
                main = soup.select_one("main, #main-content, .main-content, article")
                if main:
                    items = main.select("a[href*='/project'], a[href*='/projects']")

            for item in items:
                try:
                    if item.name == "a":
                        title = item.get_text(strip=True)
                        link = item.get("href", "")
                    else:
                        title_el = item.select_one(
                            "h2 a, h3 a, h4 a, .title a, a[href*='/project']"
                        )
                        if not title_el:
                            continue
                        title = title_el.get_text(strip=True)
                        link = title_el.get("href", "")

                    if not title or len(title) < 5:
                        continue

                    if not link.startswith("http"):
                        link = urljoin("https://www.isdb.org", link)

                    # Сектор / описание
                    desc_el = item.select_one(".description, .summary, p, .field--name-body")
                    description = desc_el.get_text(strip=True)[:300] if desc_el else ""

                    # Бюджет
                    amount_el = item.select_one(".amount, .budget, .cost, [class*='amount']")
                    budget = amount_el.get_text(strip=True) if amount_el else ""

                    results.append({
                        "source": "IsDB Projects",
                        "title": title,
                        "url": link,
                        "description": description,
                        "donor": "Islamic Development Bank",
                        "budget": budget if budget else None,
                        "region": "Tajikistan",
                        # Одобренный проект = будущий тендер
                        "status": "Planned",
                    })
                except Exception as e:
                    logger.debug("[IsDB] Project item error: %s", e)
                    continue

            logger.info("[IsDB] Projects: нашли %d", len(results))

        except Exception as e:
            logger.error("[IsDB] Projects parse error: %s", e)

        return results

    # ──────────────────────────────────────────────────────────────────────────
    # 3. DEVELOPMENTAID — агрегатор включает IsDB тендеры
    # ──────────────────────────────────────────────────────────────────────────
    async def _scrape_via_developmentaid(self) -> list[dict]:
        """
        DevelopmentAid агрегирует тендеры IsDB.
        Используем их публичный поиск.
        """
        results = []

        # DevelopmentAid поиск IsDB + Tajikistan
        url = (
            "https://developmentaid.org/tenders/search"
            "?country=tajikistan&donor=IsDB"
        )

        html = await self.fetch(url)
        if not html:
            return results

        try:
            soup = BeautifulSoup(html, "lxml")

            items = soup.select(
                ".tender-card, .tender-item, article, "
                ".search-result, .listing-item"
            )

            for item in items:
                try:
                    title_el = item.select_one("h2 a, h3 a, h4 a, .title a")
                    if not title_el:
                        continue

                    title = title_el.get_text(strip=True)
                    link = title_el.get("href", "")
                    if not link.startswith("http"):
                        link = urljoin("https://developmentaid.org", link)

                    deadline_el = item.select_one(".deadline, .date, time")
                    deadline = deadline_el.get_text(strip=True) if deadline_el else ""

                    results.append({
                        "source": "IsDB (via DevelopmentAid)",
                        "title": title,
                        "url": link,
                        "donor": "Islamic Development Bank",
                        "tender_deadline": deadline if deadline else None,
                        "region": "Tajikistan",
                        "status": "Active",
                    })
                except Exception:
                    continue

        except Exception as e:
            logger.debug("[IsDB] DevelopmentAid error: %s", e)

        return results
