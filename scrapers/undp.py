"""
UNDP Scraper v2 — проверенная версия.

Тестировано:
- procurement-notices.undp.org/ ✅ 200 (1MB HTML)
- procurement-notices.undp.org/search.cfm?q=tajikistan ✅ 200 (1.7MB HTML)
Не работает: /view_notices.cfm?Country=TJK → 404
"""

from bs4 import BeautifulSoup
from urllib.parse import urljoin, quote

from scrapers.base import BaseScraper
from utils.logger import logger


class UNDPScraper(BaseScraper):

    def __init__(self):
        super().__init__("UNDP")

    async def scrape(self) -> list[dict]:
        results = []

        # Используем search endpoint (работает!)
        searches = [
            ("tajikistan water", "https://procurement-notices.undp.org/search.cfm?q=tajikistan+water"),
            ("tajikistan pipe", "https://procurement-notices.undp.org/search.cfm?q=tajikistan+pipe"),
            ("tajikistan irrigation", "https://procurement-notices.undp.org/search.cfm?q=tajikistan+irrigation"),
            ("tajikistan", "https://procurement-notices.undp.org/search.cfm?q=tajikistan"),
        ]

        seen_urls = set()

        for query_name, url in searches:
            html = await self.fetch(url)
            if not html:
                logger.warning("[UNDP] Не удалось загрузить: %s", query_name)
                await self.delay()
                continue

            try:
                soup = BeautifulSoup(html, "lxml")

                # UNDP показывает таблицу результатов
                tables = soup.select("table")
                for table in tables:
                    rows = table.select("tbody tr, tr")
                    for row in rows:
                        try:
                            cells = row.select("td")
                            if len(cells) < 2:
                                continue

                            # Ищем ссылку в ячейках
                            title_el = None
                            for cell in cells:
                                a = cell.select_one("a[href]")
                                if a and len(a.get_text(strip=True)) > 10:
                                    title_el = a
                                    break

                            if not title_el:
                                continue

                            title = title_el.get_text(strip=True)
                            link = title_el.get("href", "")
                            if link and not link.startswith("http"):
                                link = urljoin("https://procurement-notices.undp.org", link)

                            if link in seen_urls:
                                continue
                            seen_urls.add(link)

                            # Дедлайн — ячейка с датой
                            deadline = ""
                            for cell in reversed(cells):
                                text = cell.get_text(strip=True)
                                if any(c.isdigit() for c in text) and (
                                    "/" in text or "-" in text or "20" in text
                                ):
                                    deadline = text
                                    break

                            # Категория
                            category = ""
                            if len(cells) > 1:
                                for cell in cells:
                                    text = cell.get_text(strip=True)
                                    if text != title and len(text) > 3 and not any(c.isdigit() for c in text[:3]):
                                        category = text
                                        break

                            results.append({
                                "source": "UNDP",
                                "title": title,
                                "url": link or url,
                                "description": f"Category: {category}" if category else "",
                                "donor": "UNDP",
                                "tender_deadline": deadline if deadline else None,
                                "status": "Active",
                            })
                        except Exception as e:
                            logger.debug("[UNDP] Row error: %s", str(e))
                            continue

                # Если нет таблицы — ищем карточки
                if not results:
                    items = soup.select(
                        ".notice-item, .views-row, article, .card, "
                        ".list-item, .search-result, .result"
                    )
                    for item in items:
                        try:
                            title_el = item.select_one("a[href], h3 a, h4 a")
                            if not title_el:
                                continue
                            title = title_el.get_text(strip=True)
                            if not title or len(title) < 5:
                                continue

                            link = title_el.get("href", "")
                            if link and not link.startswith("http"):
                                link = urljoin("https://procurement-notices.undp.org", link)

                            if link in seen_urls:
                                continue
                            seen_urls.add(link)

                            results.append({
                                "source": "UNDP",
                                "title": title,
                                "url": link or url,
                                "donor": "UNDP",
                                "status": "Active",
                            })
                        except Exception:
                            continue

            except Exception as e:
                logger.error("[UNDP] Parse error: %s", str(e))

            await self.delay()

            if len(results) >= 20:
                break  # Достаточно результатов

        logger.info("[UNDP] Найдено тендеров: %d", len(results))
        return results
