"""
IsDB Scraper v3 — проверенная версия.

BGATE не существует (DNS fail). Используем:
- isdb.org/tajikistan ✅ (51KB статичный HTML)
- DevelopmentAid как агрегатор
"""

from bs4 import BeautifulSoup
from urllib.parse import urljoin

from scrapers.base import BaseScraper
from utils.logger import logger


class IsDBScraper(BaseScraper):

    def __init__(self):
        super().__init__("IsDB")

    async def scrape(self) -> list[dict]:
        results = []

        # 1. IsDB Projects страница по Таджикистану (статичный HTML, 51KB)
        projects = await self._scrape_isdb_projects()
        results.extend(projects)
        logger.info("[IsDB] Projects: %d", len(projects))
        await self.delay()

        # 2. Поиск IsDB тендеров через DevelopmentAid
        da = await self._scrape_via_developmentaid()
        results.extend(da)
        logger.info("[IsDB] via DevelopmentAid: %d", len(da))

        logger.info("[IsDB] ИТОГО: %d", len(results))
        return results

    async def _scrape_isdb_projects(self) -> list[dict]:
        """
        IsDB Projects страница по Таджикистану.
        Тестировано: 200 OK, 51257 bytes.
        """
        results = []

        urls = [
            "https://www.isdb.org/tajikistan",
            "https://www.isdb.org/en/projects?country=Tajikistan",
        ]

        for url in urls:
            html = await self.fetch(url)
            if not html:
                continue

            try:
                soup = BeautifulSoup(html, "lxml")

                # Ищем карточки проектов
                items = soup.select(
                    ".project-card, .views-row, article, "
                    ".field--name-title, .project-item, li.project, "
                    ".card, .node, .teaser, .content-item"
                )

                if not items:
                    # Fallback: ищем все ссылки в main content с /project в href
                    main = soup.select_one("main, #main-content, .main-content, article, .content")
                    if main:
                        items = main.select("a[href*='/project'], a[href*='/projects']")

                if not items:
                    # Fallback 2: любые ссылки содержащие ключевые слова
                    all_links = soup.find_all("a", href=True)
                    items = [a for a in all_links if any(
                        kw in a.get_text().lower() for kw in
                        ["water", "irrigation", "infrastructure", "transport", "energy", "health", "education"]
                    ) and len(a.get_text(strip=True)) > 10]

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
                                title_el = item.select_one("a[href]")
                            if not title_el:
                                continue
                            title = title_el.get_text(strip=True)
                            link = title_el.get("href", "")

                        if not title or len(title) < 5:
                            continue

                        if not link.startswith("http"):
                            link = urljoin("https://www.isdb.org", link)

                        # Пропускаем навигационные ссылки
                        if any(skip in link for skip in ["#", "javascript:", "tel:", "mailto:"]):
                            continue

                        desc_el = item.select_one(".description, .summary, p, .field--name-body") if item.name != "a" else None
                        description = desc_el.get_text(strip=True)[:300] if desc_el else ""

                        amount_el = item.select_one(".amount, .budget, .cost, [class*='amount']") if item.name != "a" else None
                        budget = amount_el.get_text(strip=True) if amount_el else ""

                        results.append({
                            "source": "IsDB Projects",
                            "title": title,
                            "url": link,
                            "description": description,
                            "donor": "Islamic Development Bank",
                            "budget": budget if budget else None,
                            "region": "Tajikistan",
                            "status": "Planned",
                        })
                    except Exception as e:
                        logger.debug("[IsDB] Project item error: %s", e)
                        continue

                if results:
                    break  # Нашли — второй URL не нужен

            except Exception as e:
                logger.error("[IsDB] Projects parse error: %s", e)

        return results

    async def _scrape_via_developmentaid(self) -> list[dict]:
        """DevelopmentAid агрегирует тендеры IsDB."""
        results = []

        url = "https://developmentaid.org/tenders/search?country=tajikistan&donor=IsDB"
        html = await self.fetch(url)
        if not html:
            return results

        try:
            soup = BeautifulSoup(html, "lxml")

            items = soup.select(
                ".tender-card, .tender-item, article, "
                ".search-result, .listing-item, .card, .result"
            )

            for item in items:
                try:
                    title_el = item.select_one("h2 a, h3 a, h4 a, .title a, a[href]")
                    if not title_el:
                        continue

                    title = title_el.get_text(strip=True)
                    if not title or len(title) < 5:
                        continue

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
