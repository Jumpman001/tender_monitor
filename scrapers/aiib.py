"""
AIIB Scraper — Asian Infrastructure Investment Bank.
$500 млн по Рогуну + совместные проекты с ADB и EBRD.
"""

from bs4 import BeautifulSoup
from urllib.parse import urljoin

from scrapers.base import BaseScraper
from utils.logger import logger


class AIIBScraper(BaseScraper):
    """Скрапер для AIIB procurement."""

    def __init__(self):
        super().__init__("AIIB")

    async def scrape(self) -> list[dict]:
        """Парсит тендеры AIIB."""
        results = []

        # AIIB procurement page
        urls = [
            "https://www.aiib.org/en/opportunities/business/procurement-notices/index.html",
            "https://www.aiib.org/en/projects/list/index.html?status=Approved",
        ]

        for base_url in urls:
            html = await self.fetch(base_url)
            if not html:
                logger.warning("[AIIB] Не удалось загрузить: %s", base_url[:60])
                continue

            try:
                soup = BeautifulSoup(html, "lxml")

                # Таблица или карточки
                items = soup.select(
                    "table tbody tr, .procurement-item, .project-item, "
                    ".list-item, article, .card, .views-row, "
                    ".notice-item, .search-result"
                )

                for item in items:
                    try:
                        title_el = item.select_one(
                            "a[href], h3 a, h4 a, .title a, td a"
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
                            link = urljoin("https://www.aiib.org", link)

                        # Проверка на Tajikistan
                        item_text = item.get_text(strip=True).lower()
                        if "tajikistan" not in item_text and "таджикистан" not in item_text:
                            # Для страницы проектов — оставляем все, детали проверим позже
                            if "procurement" in base_url:
                                continue

                        desc_el = item.select_one(".description, .summary, p")
                        description = desc_el.get_text(strip=True)[:500] if desc_el else ""

                        date_el = item.select_one(".date, time, .deadline")
                        deadline = date_el.get_text(strip=True) if date_el else ""

                        # Бюджет
                        budget = ""
                        for cell in item.select("td, .amount, .budget"):
                            text = cell.get_text(strip=True)
                            if "$" in text or "USD" in text or "million" in text.lower():
                                budget = text
                                break

                        results.append({
                            "source": "AIIB",
                            "title": title,
                            "url": link or base_url,
                            "description": description,
                            "donor": "AIIB",
                            "budget": budget if budget else None,
                            "tender_deadline": deadline if deadline else None,
                            "status": "Active",
                        })
                    except Exception as e:
                        logger.debug("[AIIB] Ошибка парсинга элемента: %s", str(e))
                        continue

            except Exception as e:
                logger.error("[AIIB] Ошибка парсинга: %s", str(e))

            await self.delay()

        # Парсим детали
        for tender in results[:10]:
            if tender.get("url") and "aiib.org" in tender["url"]:
                await self.delay()
                detail = await self._scrape_detail(tender["url"])
                tender.update({k: v for k, v in detail.items() if v})

        logger.info("[AIIB] Найдено тендеров: %d", len(results))
        return results

    async def _scrape_detail(self, url: str) -> dict:
        """Парсит детальную страницу."""
        detail = {}
        html = await self.fetch(url)
        if not html:
            return detail

        try:
            soup = BeautifulSoup(html, "lxml")

            content = soup.select_one(
                ".main-content, article .content, #content, .field--name-body"
            )
            if content:
                detail["description"] = content.get_text(strip=True)[:1500]

            for label in soup.select("dt, th, strong, .label, .field-label"):
                label_text = label.get_text(strip=True).lower()
                sibling = label.find_next_sibling()
                if not sibling:
                    continue
                value = sibling.get_text(strip=True)

                if any(kw in label_text for kw in ["total", "amount", "financing", "budget"]):
                    detail["budget"] = value
                elif any(kw in label_text for kw in ["deadline", "closing"]):
                    detail["tender_deadline"] = value
                elif "sector" in label_text:
                    detail["description"] = f"Sector: {value}. " + detail.get("description", "")
                elif "project" in label_text and "id" in label_text:
                    detail["project_id"] = value
                elif "country" in label_text:
                    detail["region"] = value

        except Exception as e:
            logger.debug("[AIIB] Ошибка парсинга деталей: %s", str(e))

        return detail
