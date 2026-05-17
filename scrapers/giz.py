"""
GIZ Scraper — Deutsche Gesellschaft für Internationale Zusammenarbeit.
Активно в ирригации Центральной Азии.
"""

from bs4 import BeautifulSoup
from urllib.parse import urljoin

from scrapers.base import BaseScraper
from utils.logger import logger


class GIZScraper(BaseScraper):
    """Скрапер для GIZ — немецкое агентство развития."""

    def __init__(self):
        super().__init__("GIZ")

    async def scrape(self) -> list[dict]:
        """Парсит тендеры и проекты GIZ в Таджикистане."""
        results = []

        urls = [
            # Тендеры GIZ
            "https://www.giz.de/en/workingwithgiz/tenders.html",
            # Проекты в Таджикистане
            "https://www.giz.de/en/worldwide/348.html",
        ]

        for base_url in urls:
            html = await self.fetch(base_url)
            if not html:
                logger.warning("[GIZ] Не удалось загрузить: %s", base_url[:60])
                continue

            try:
                soup = BeautifulSoup(html, "lxml")

                items = soup.select(
                    "table tbody tr, .tender-item, .views-row, "
                    ".teaser, article, .card, .list-item, "
                    ".content-item, .search-result"
                )

                for item in items:
                    try:
                        title_el = item.select_one(
                            "a[href], h3 a, h4 a, .title a, .heading a"
                        )
                        if not title_el:
                            cells = item.select("td")
                            if cells:
                                for cell in cells:
                                    a = cell.select_one("a")
                                    if a:
                                        title_el = a
                                        break
                            if not title_el:
                                continue

                        title = title_el.get_text(strip=True)
                        if not title or len(title) < 5:
                            continue

                        link = title_el.get("href", "")
                        if link and not link.startswith("http"):
                            link = urljoin("https://www.giz.de", link)

                        # Проверяем на релевантность к Таджикистану / ЦА / воде
                        item_text = item.get_text(strip=True).lower()
                        is_relevant = any(kw in item_text for kw in [
                            "tajikistan", "таджикистан", "central asia",
                            "zentralasien", "water", "irrigation", "wasser",
                        ])

                        # Для страницы тендеров — проверяем релевантность
                        if "tenders" in base_url and not is_relevant:
                            continue

                        desc_el = item.select_one(
                            ".description, .summary, p, .teaser-text"
                        )
                        description = desc_el.get_text(strip=True)[:500] if desc_el else ""

                        date_el = item.select_one(
                            ".date, time, .deadline"
                        )
                        deadline = date_el.get_text(strip=True) if date_el else ""

                        results.append({
                            "source": "GIZ",
                            "title": title,
                            "url": link or base_url,
                            "description": description,
                            "donor": "GIZ (Germany)",
                            "tender_deadline": deadline if deadline else None,
                            "status": "Active",
                        })
                    except Exception as e:
                        logger.debug("[GIZ] Ошибка парсинга элемента: %s", str(e))
                        continue

            except Exception as e:
                logger.error("[GIZ] Ошибка парсинга: %s", str(e))

            await self.delay()

        logger.info("[GIZ] Найдено тендеров: %d", len(results))
        return results
