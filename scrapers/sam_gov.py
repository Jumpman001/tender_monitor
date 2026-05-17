"""
SAM.gov Scraper — агрегатор всех американских тендеров, включая USAID.
Поиск по "tajikistan water".
"""

from bs4 import BeautifulSoup
from urllib.parse import urljoin, quote

from scrapers.base import BaseScraper
from utils.logger import logger


class SAMGovScraper(BaseScraper):
    """Скрапер для SAM.gov — US federal procurement (USAID и др.)."""

    def __init__(self):
        super().__init__("SAM.gov")

    async def scrape(self) -> list[dict]:
        """Парсит тендеры SAM.gov по Таджикистану."""
        results = []

        # SAM.gov API endpoint для поиска opportunities
        search_queries = [
            "tajikistan water",
            "tajikistan irrigation",
            "tajikistan pipeline",
        ]

        for query in search_queries:
            # SAM.gov предоставляет API
            api_url = (
                f"https://api.sam.gov/opportunities/v2/search?"
                f"api_key=DEMO_KEY&"  # демо-ключ для тестирования
                f"q={quote(query)}&"
                f"limit=25&"
                f"postedFrom=01/01/2025&"
                f"status=active"
            )

            # Пробуем API
            data = await self.fetch_json(api_url)
            if data and isinstance(data, dict):
                opportunities = data.get("opportunitiesData", [])
                for opp in opportunities:
                    try:
                        title = opp.get("title", "")
                        notice_id = opp.get("noticeId", "")
                        sol_number = opp.get("solicitationNumber", "")
                        department = opp.get("department", "")
                        description = opp.get("description", "")[:500] if opp.get("description") else ""
                        deadline = opp.get("responseDeadLine", "")
                        url = f"https://sam.gov/opp/{notice_id}/view" if notice_id else "https://sam.gov"

                        results.append({
                            "source": "SAM.gov",
                            "title": title,
                            "url": url,
                            "description": description,
                            "project_id": sol_number,
                            "donor": f"US Government ({department})" if department else "US Government / USAID",
                            "tender_deadline": deadline[:10] if deadline else None,
                            "status": "Active",
                        })
                    except Exception as e:
                        logger.debug("[SAM.gov] Ошибка парсинга записи API: %s", str(e))
                        continue

                logger.info("[SAM.gov] API query '%s': найдено %d", query, len(opportunities))

            else:
                # Fallback: парсим HTML
                html_url = f"https://sam.gov/search/?index=opp&q={quote(query)}&sort=-modifiedDate&page=1"
                html = await self.fetch(html_url)
                if html:
                    try:
                        soup = BeautifulSoup(html, "lxml")
                        items = soup.select(
                            ".result-item, .opportunity-item, article, .card, "
                            ".list-item, .search-result"
                        )
                        for item in items:
                            try:
                                title_el = item.select_one("a[href], h3 a, .title a")
                                if not title_el:
                                    continue
                                title = title_el.get_text(strip=True)
                                if not title or len(title) < 5:
                                    continue

                                link = title_el.get("href", "")
                                if link and not link.startswith("http"):
                                    link = urljoin("https://sam.gov", link)

                                desc_el = item.select_one("p, .description, .summary")
                                description = desc_el.get_text(strip=True)[:500] if desc_el else ""

                                results.append({
                                    "source": "SAM.gov",
                                    "title": title,
                                    "url": link or html_url,
                                    "description": description,
                                    "donor": "US Government / USAID",
                                    "status": "Active",
                                })
                            except Exception:
                                continue
                    except Exception as e:
                        logger.error("[SAM.gov] Ошибка парсинга HTML: %s", str(e))

            await self.delay()

        logger.info("[SAM.gov] Всего найдено тендеров: %d", len(results))
        return results
