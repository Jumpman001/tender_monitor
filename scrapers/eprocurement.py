"""
eprocurement.gov.tj Scraper — государственный портал закупок Таджикистана.
"""

from bs4 import BeautifulSoup
from urllib.parse import urljoin

from scrapers.base import BaseScraper
from utils.logger import logger


class EProcurementScraper(BaseScraper):
    """Скрапер для eprocurement.gov.tj (если доступен без авторизации)."""

    def __init__(self):
        super().__init__("eprocurement.gov.tj")

    async def scrape(self) -> list[dict]:
        """Парсит тендеры с eprocurement.gov.tj."""
        base_url = "https://eprocurement.gov.tj/"
        results = []

        html = await self.fetch(base_url)
        if not html:
            logger.warning(
                "[eprocurement] Сайт недоступен или требует авторизацию"
            )
            return results

        try:
            soup = BeautifulSoup(html, "lxml")

            # Ищем доступные тендеры
            items = soup.select(
                "table tbody tr, .tender-item, .procurement-item, "
                ".list-group-item, article, .card"
            )

            for item in items:
                try:
                    title_el = item.select_one("a[href], h3 a, .title a")
                    if not title_el:
                        cells = item.select("td")
                        if cells and len(cells) >= 2:
                            title_el = cells[0].select_one("a")
                        if not title_el:
                            continue

                    title = title_el.get_text(strip=True)
                    if not title or len(title) < 5:
                        continue

                    link = title_el.get("href", "")
                    if link and not link.startswith("http"):
                        link = urljoin(base_url, link)

                    desc_el = item.select_one("p, .description, .summary")
                    description = desc_el.get_text(strip=True)[:500] if desc_el else ""

                    date_el = item.select_one(".date, time, .deadline")
                    deadline = date_el.get_text(strip=True) if date_el else ""

                    results.append({
                        "source": "eprocurement.gov.tj",
                        "title": title,
                        "url": link or base_url,
                        "description": description,
                        "tender_deadline": deadline if deadline else None,
                        "status": "Active",
                    })
                except Exception as e:
                    logger.debug("[eprocurement] Ошибка парсинга: %s", str(e))
                    continue

            logger.info("[eprocurement] Найдено тендеров: %d", len(results))

        except Exception as e:
            logger.error("[eprocurement] Ошибка парсинга: %s", str(e))

        return results
