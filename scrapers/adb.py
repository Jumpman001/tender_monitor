"""
ADB Scraper v3 — проверенная версия.

ADB закрыл RSS и API (404/403). Используем:
- HTML парсинг страницы поиска ADB (работает с certifi SSL)
- ADB Data Library API как fallback
"""

from bs4 import BeautifulSoup
from urllib.parse import urljoin, quote

from scrapers.base import BaseScraper
from utils.logger import logger


class ADBScraper(BaseScraper):

    def __init__(self):
        super().__init__("ADB")

    async def scrape(self) -> list[dict]:
        results = []

        # 1. ADB — парсим HTML страницу проектов
        projects = await self._scrape_projects_html()
        results.extend(projects)
        logger.info("[ADB] Projects HTML: %d", len(projects))
        await self.delay()

        # 2. ADB — парсим страницу тендеров
        tenders = await self._scrape_tenders_html()
        results.extend(tenders)
        logger.info("[ADB] Tenders HTML: %d", len(tenders))

        logger.info("[ADB] ИТОГО: %d", len(results))
        return results

    async def _scrape_projects_html(self) -> list[dict]:
        """Парсим HTML страницу проектов ADB по Таджикистану."""
        results = []

        urls = [
            "https://www.adb.org/projects/country/taj/sector/water-and-other-urban-infrastructure-and-services-1060",
            "https://www.adb.org/projects/country/taj",
        ]

        for url in urls:
            html = await self.fetch(url)
            if not html:
                logger.warning("[ADB] Не удалось загрузить: %s", url[:60])
                continue

            try:
                soup = BeautifulSoup(html, "lxml")

                # ADB использует div.item-list или ol/ul с результатами
                items = soup.select(
                    ".item-list li, .views-row, .project-item, "
                    "article, .search-result, .result, .list-item, "
                    "table tbody tr, .node--type-project"
                )

                if not items:
                    # Fallback — ищем все ссылки с /projects/ в href
                    items = soup.select("a[href*='/projects/']")

                for item in items:
                    try:
                        if item.name == "a":
                            title_el = item
                        else:
                            title_el = item.select_one(
                                "a[href], h3 a, h4 a, .title a, .views-field a"
                            )

                        if not title_el:
                            continue

                        title = title_el.get_text(strip=True)
                        if not title or len(title) < 5:
                            continue

                        link = title_el.get("href", "")
                        if link and not link.startswith("http"):
                            link = urljoin("https://www.adb.org", link)

                        # Пропускаем навигационные ссылки
                        if any(skip in link for skip in ["/country/", "/sector/", "/theme/", "#"]):
                            continue

                        desc_el = item.select_one(
                            ".description, .summary, p, .views-field-body"
                        ) if item.name != "a" else None
                        description = desc_el.get_text(strip=True)[:500] if desc_el else ""

                        results.append({
                            "source": "ADB",
                            "title": title,
                            "url": link,
                            "description": description,
                            "donor": "Asian Development Bank",
                            "region": "Tajikistan",
                            "status": "Active",
                        })
                    except Exception as e:
                        logger.debug("[ADB] Item error: %s", str(e))
                        continue

            except Exception as e:
                logger.error("[ADB] Projects HTML error: %s", e)

            if results:
                break  # Нашли — второй URL не нужен
            await self.delay()

        # Парсим детали для первых 5
        for tender in results[:5]:
            if tender.get("url") and "adb.org" in tender["url"]:
                await self.delay()
                detail = await self._scrape_detail(tender["url"])
                tender.update({k: v for k, v in detail.items() if v})

        return results

    async def _scrape_tenders_html(self) -> list[dict]:
        """Парсим страницу Business Opportunities ADB."""
        results = []

        url = "https://www.adb.org/business/opportunities/current"
        html = await self.fetch(url)
        if not html:
            return results

        try:
            soup = BeautifulSoup(html, "lxml")

            items = soup.select(
                ".item-list li, .views-row, table tbody tr, "
                "article, .search-result, .result"
            )

            for item in items:
                try:
                    title_el = item.select_one("a[href], h3 a, h4 a, td a")
                    if not title_el:
                        continue

                    title = title_el.get_text(strip=True)
                    if not title or len(title) < 5:
                        continue

                    link = title_el.get("href", "")
                    if link and not link.startswith("http"):
                        link = urljoin("https://www.adb.org", link)

                    # Фильтруем по Tajikistan
                    item_text = item.get_text().lower()
                    if "tajikistan" not in item_text and "taj" not in item_text:
                        continue

                    results.append({
                        "source": "ADB Tenders",
                        "title": title,
                        "url": link,
                        "donor": "Asian Development Bank",
                        "region": "Tajikistan",
                        "status": "Active",
                    })
                except Exception:
                    continue

        except Exception as e:
            logger.error("[ADB] Tenders HTML error: %s", e)

        return results

    async def _scrape_detail(self, url: str) -> dict:
        """Парсит детальную страницу проекта/тендера ADB."""
        detail = {}
        html = await self.fetch(url)
        if not html:
            return detail

        try:
            soup = BeautifulSoup(html, "lxml")

            for row in soup.select("tr, .field-group, dl dt, .detail-row"):
                label_el = row.select_one("th, dt, .label, strong")
                value_el = row.select_one("td, dd, .value, span:last-child")
                if not label_el or not value_el:
                    continue

                label = label_el.get_text(strip=True).lower()
                value = value_el.get_text(strip=True)
                if not value:
                    continue

                if any(k in label for k in ["deadline", "closing", "submission date"]):
                    detail["tender_deadline"] = value
                elif any(k in label for k in ["amount", "budget", "cost", "value"]):
                    detail["budget"] = value
                elif any(k in label for k in ["project no", "project number", "reference"]):
                    detail["project_id"] = value
                elif "contact" in label:
                    detail["contact_name"] = value
                elif "email" in label or "@" in value:
                    detail["contact_email"] = value
                elif any(k in label for k in ["sector", "theme"]):
                    detail["description"] = f"Sector: {value}"

            desc = soup.select_one(".field--name-body, .project-description, #content .text")
            if desc:
                detail["description"] = desc.get_text(strip=True)[:1000]

        except Exception as e:
            logger.debug("[ADB] Detail parse error %s: %s", url[:50], e)

        return detail
