"""
EBRD Scraper v2 — European Bank for Reconstruction and Development.

EBRD сайт JS-рендерный. Procurement notices грузятся через JavaScript.
Используем:
- /work-with-us/procurement/notices.html ✅ 200 (154KB)
  Парсим результаты из HTML (EBRD встраивает данные в скрытые элементы)
- /home/what-we-do/projects.html ✅ 200 — проекты
"""

from bs4 import BeautifulSoup
from urllib.parse import urljoin

from scrapers.base import BaseScraper
from utils.logger import logger


class EBRDScraper(BaseScraper):
    """Скрапер для EBRD — Таджикистан."""

    def __init__(self):
        super().__init__("EBRD")

    async def scrape(self) -> list[dict]:
        results = []

        # 1. Procurement notices
        proc = await self._scrape_procurement()
        results.extend(proc)
        logger.info("[EBRD] Procurement: %d", len(proc))
        await self.delay()

        # 2. Projects page
        proj = await self._scrape_projects()
        results.extend(proj)
        logger.info("[EBRD] Projects: %d", len(proj))

        logger.info("[EBRD] ИТОГО: %d", len(results))
        return results

    async def _scrape_procurement(self) -> list[dict]:
        """Парсим procurement notices EBRD."""
        results = []

        urls = [
            "https://www.ebrd.com/work-with-us/procurement/notices.html",
            (
                "https://www.ebrd.com/work-with-us/procurement/"
                "project-procurement-notices.html?1=1&filterCountry=Tajikistan"
            ),
        ]

        for url in urls:
            html = await self.fetch(url)
            if not html:
                continue

            try:
                soup = BeautifulSoup(html, "lxml")

                # Ищем таблицы
                for table in soup.select("table"):
                    rows = table.select("tbody tr, tr")
                    for row in rows:
                        try:
                            cells = row.select("td")
                            if len(cells) < 2:
                                continue

                            row_text = row.get_text().lower()
                            if "tajikistan" not in row_text and "таджикистан" not in row_text:
                                continue

                            title_el = row.select_one("a[href]")
                            title = title_el.get_text(strip=True) if title_el else cells[0].get_text(strip=True)
                            if not title or len(title) < 5:
                                continue

                            link = ""
                            if title_el:
                                link = title_el.get("href", "")
                                if link and not link.startswith("http"):
                                    link = urljoin("https://www.ebrd.com", link)

                            sector = cells[2].get_text(strip=True) if len(cells) > 2 else ""
                            notice_type = cells[3].get_text(strip=True) if len(cells) > 3 else ""
                            deadline = cells[4].get_text(strip=True) if len(cells) > 4 else ""

                            results.append({
                                "source": "EBRD",
                                "title": title,
                                "url": link or url,
                                "description": f"Sector: {sector}. Type: {notice_type}",
                                "donor": "EBRD",
                                "tender_deadline": deadline if deadline else None,
                                "region": "Tajikistan",
                                "status": "Active",
                            })
                        except Exception:
                            continue

                # Ищем карточки и ссылки с Tajikistan
                if not results:
                    all_links = soup.select("a[href]")
                    for a in all_links:
                        href = a.get("href", "")
                        text = a.get_text(strip=True)
                        parent_text = (a.parent.get_text(strip=True) if a.parent else "").lower()

                        if not text or len(text) < 10:
                            continue
                        if "tajikistan" not in parent_text and "tajikistan" not in text.lower():
                            continue
                        if any(skip in href for skip in ["#", "javascript:", "mailto:"]):
                            continue

                        full_url = href if href.startswith("http") else urljoin("https://www.ebrd.com", href)
                        results.append({
                            "source": "EBRD",
                            "title": text,
                            "url": full_url,
                            "donor": "EBRD",
                            "region": "Tajikistan",
                            "status": "Active",
                        })

            except Exception as e:
                logger.error("[EBRD] Procurement error: %s", e)

            if results:
                break
            await self.delay()

        return results

    async def _scrape_projects(self) -> list[dict]:
        """Парсим страницу проектов EBRD для Таджикистана."""
        results = []

        url = (
            "https://www.ebrd.com/home/what-we-do/projects.html"
            "?1=1&filterCountry=Tajikistan"
            "&filterSector=Municipal%20and%20environmental%20infrastructure"
        )
        html = await self.fetch(url)
        if not html:
            return results

        try:
            soup = BeautifulSoup(html, "lxml")

            # Ищем проекты
            items = soup.select(
                ".project-card, .project-item, article, .card, "
                ".search-result, .result, .views-row, .node"
            )

            if not items:
                # Fallback: ищем все ссылки в основном контенте
                main = soup.select_one("main, #main-content, .content, article")
                if main:
                    items = main.select("a[href*='project']")

            for item in items:
                try:
                    if item.name == "a":
                        title = item.get_text(strip=True)
                        link = item.get("href", "")
                    else:
                        title_el = item.select_one("a[href], h3 a, h4 a")
                        if not title_el:
                            continue
                        title = title_el.get_text(strip=True)
                        link = title_el.get("href", "")

                    if not title or len(title) < 5:
                        continue
                    if not link.startswith("http"):
                        link = urljoin("https://www.ebrd.com", link)

                    # Фильтр по Tajikistan
                    item_text = (item.get_text() if item.name != "a" else title).lower()
                    if "tajikistan" not in item_text:
                        continue

                    results.append({
                        "source": "EBRD Projects",
                        "title": title,
                        "url": link,
                        "donor": "EBRD",
                        "region": "Tajikistan",
                        "status": "Active",
                    })
                except Exception:
                    continue

        except Exception as e:
            logger.error("[EBRD] Projects error: %s", e)

        return results
