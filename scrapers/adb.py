"""
ADB Scraper v4 — проверенная версия.

Рабочие URL:
- /where-we-work/tajikistan ✅ 200 OK (111KB) — 13 проектных ссылок
- /projects/XXXXX/main — детальные страницы проектов

Все остальные ADB endpoints (RSS, API, /projects/country/) → 404/403.
"""

from bs4 import BeautifulSoup
from urllib.parse import urljoin

from scrapers.base import BaseScraper
from utils.logger import logger


class ADBScraper(BaseScraper):

    def __init__(self):
        super().__init__("ADB")

    async def scrape(self) -> list[dict]:
        results = []

        # 1. Страница Таджикистана — единственный рабочий endpoint
        projects = await self._scrape_country_page()
        results.extend(projects)
        logger.info("[ADB] Country page: %d", len(projects))

        logger.info("[ADB] ИТОГО: %d", len(results))
        return results

    async def _scrape_country_page(self) -> list[dict]:
        """
        Парсим /where-we-work/tajikistan.
        Тестировано: 200 OK, 111790 bytes, 13 проектных ссылок.
        """
        results = []
        url = "https://www.adb.org/where-we-work/tajikistan"
        html = await self.fetch(url)
        if not html:
            return results

        try:
            soup = BeautifulSoup(html, "lxml")

            # Собираем все ссылки на проекты /projects/XXXXX/main
            project_links = []
            for a in soup.select("a[href*='/projects/']"):
                href = a.get("href", "")
                text = a.get_text(strip=True)

                # Пропускаем навигационные ссылки
                if not text or len(text) < 10:
                    continue
                if any(skip in href for skip in [
                    "/tenders", "/country/", "/sector/", "/theme/",
                    "#", "javascript:", "/list/"
                ]):
                    continue

                full_url = href if href.startswith("http") else urljoin("https://www.adb.org", href)

                # Дедупликация
                if full_url not in [p["url"] for p in project_links]:
                    project_links.append({
                        "title": text,
                        "url": full_url,
                    })

            logger.info("[ADB] Найдено %d проектных ссылок", len(project_links))

            # Парсим детали каждого проекта
            for proj in project_links:
                await self.delay()
                detail = await self._scrape_project_detail(proj["url"])

                result = {
                    "source": "ADB",
                    "title": proj["title"],
                    "url": proj["url"],
                    "donor": "Asian Development Bank",
                    "region": "Tajikistan",
                    "status": "Active",
                }

                if detail:
                    result.update({k: v for k, v in detail.items() if v})

                results.append(result)

        except Exception as e:
            logger.error("[ADB] Country page error: %s", e)

        return results

    async def _scrape_project_detail(self, url: str) -> dict:
        """Парсит детальную страницу проекта ADB."""
        detail = {}
        html = await self.fetch(url)
        if not html:
            return detail

        try:
            soup = BeautifulSoup(html, "lxml")

            # Описание проекта
            desc = soup.select_one(
                ".project-description, .field--name-body, "
                "#content .text, .project-overview, article p"
            )
            if desc:
                detail["description"] = desc.get_text(strip=True)[:1500]

            # Таблица с деталями
            for row in soup.select("tr, .field-group, dl dt, .detail-row, .project-field"):
                label_el = row.select_one("th, dt, .label, strong, .field-label")
                value_el = row.select_one("td, dd, .value, span:last-child, .field-value")
                if not label_el or not value_el:
                    continue

                label = label_el.get_text(strip=True).lower()
                value = value_el.get_text(strip=True)
                if not value:
                    continue

                if any(k in label for k in ["deadline", "closing", "submission"]):
                    detail["tender_deadline"] = value
                elif any(k in label for k in ["amount", "budget", "cost", "value", "financing"]):
                    detail["budget"] = value
                elif any(k in label for k in ["project no", "project number", "reference", "loan"]):
                    detail["project_id"] = value
                elif "approval" in label:
                    detail["contract_start"] = value
                elif any(k in label for k in ["status", "stage"]):
                    detail["status"] = value
                elif "sector" in label or "theme" in label:
                    if not detail.get("description"):
                        detail["description"] = f"Sector: {value}"
                elif "contact" in label:
                    detail["contact_name"] = value
                elif "email" in label or "@" in value:
                    detail["contact_email"] = value
                elif "phone" in label or "tel" in label:
                    detail["contact_phone"] = value

        except Exception as e:
            logger.debug("[ADB] Detail parse error %s: %s", url[:50], e)

        return detail
