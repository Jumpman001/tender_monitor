"""
DevelopmentAid Scraper — агрегатор ВСЕХ донорских тендеров мира.
Платный, но есть бесплатный уровень доступа.
"""

from bs4 import BeautifulSoup
from urllib.parse import urljoin, quote

from scrapers.base import BaseScraper
from utils.logger import logger


class DevelopmentAidScraper(BaseScraper):
    """Скрапер для DevelopmentAid.org — агрегатор донорских тендеров."""

    def __init__(self):
        super().__init__("DevelopmentAid")

    async def scrape(self) -> list[dict]:
        """Парсит тендеры DevelopmentAid для Таджикистана."""
        results = []

        # Поиск по Таджикистану + вода/трубы
        search_queries = [
            "tajikistan water supply",
            "tajikistan irrigation pipeline",
            "tajikistan sanitation",
        ]

        for query in search_queries:
            url = (
                f"https://www.developmentaid.org/tenders/search?"
                f"q={quote(query)}&country=Tajikistan"
            )

            html = await self.fetch(url)
            if not html:
                logger.warning("[DevelopmentAid] Не удалось загрузить: %s", url[:60])
                await self.delay()
                continue

            try:
                soup = BeautifulSoup(html, "lxml")

                items = soup.select(
                    ".tender-item, .search-result, .result-item, "
                    "article, .card, .list-item, .views-row, "
                    "table tbody tr, .notice-item"
                )

                for item in items:
                    try:
                        title_el = item.select_one(
                            "a[href], h3 a, h4 a, .title a, .heading a"
                        )
                        if not title_el:
                            cells = item.select("td")
                            if cells:
                                title_el = cells[0].select_one("a")
                            if not title_el:
                                continue

                        title = title_el.get_text(strip=True)
                        if not title or len(title) < 5:
                            continue

                        link = title_el.get("href", "")
                        if link and not link.startswith("http"):
                            link = urljoin("https://www.developmentaid.org", link)

                        # Описание
                        desc_el = item.select_one(
                            ".description, .summary, p, .snippet, .teaser"
                        )
                        description = desc_el.get_text(strip=True)[:500] if desc_el else ""

                        # Дедлайн
                        date_el = item.select_one(
                            ".date, time, .deadline, .closing-date"
                        )
                        deadline = date_el.get_text(strip=True) if date_el else ""

                        # Донор/источник
                        donor_el = item.select_one(
                            ".donor, .source, .funder, .organization"
                        )
                        donor = donor_el.get_text(strip=True) if donor_el else "International Donor"

                        # Бюджет
                        budget_el = item.select_one(
                            ".budget, .amount, .value, .price"
                        )
                        budget = budget_el.get_text(strip=True) if budget_el else ""

                        # Страна
                        country_el = item.select_one(
                            ".country, .location, .region"
                        )
                        country = country_el.get_text(strip=True) if country_el else ""

                        results.append({
                            "source": "DevelopmentAid",
                            "title": title,
                            "url": link or url,
                            "description": description,
                            "donor": donor,
                            "budget": budget if budget else None,
                            "tender_deadline": deadline if deadline else None,
                            "region": country if country else None,
                            "status": "Active",
                        })
                    except Exception as e:
                        logger.debug("[DevelopmentAid] Ошибка парсинга: %s", str(e))
                        continue

            except Exception as e:
                logger.error("[DevelopmentAid] Ошибка парсинга: %s", str(e))

            await self.delay()

        logger.info("[DevelopmentAid] Найдено тендеров: %d", len(results))
        return results
