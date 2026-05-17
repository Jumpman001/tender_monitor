"""
ADB Scraper — Asian Development Bank тендеры Таджикистана.
"""

from bs4 import BeautifulSoup
from urllib.parse import urljoin

from scrapers.base import BaseScraper
from utils.logger import logger


class ADBScraper(BaseScraper):
    """Скрапер для Asian Development Bank."""

    def __init__(self):
        super().__init__("ADB")

    async def scrape(self) -> list[dict]:
        """Парсит тендеры ADB для Таджикистана."""
        results = []

        # Основная страница тендеров
        url = "https://www.adb.org/projects/tenders?country=TAJ&status=Active"
        html = await self.fetch(url)
        if not html:
            logger.warning("[ADB] Не удалось загрузить страницу тендеров")
            return results

        try:
            soup = BeautifulSoup(html, "lxml")

            # ADB обычно отображает тендеры в таблице или списке
            # Пробуем таблицу
            table = soup.select_one("table.views-table, table.tender-list, table")
            if table:
                rows = table.select("tbody tr")
                for row in rows:
                    try:
                        cells = row.select("td")
                        if len(cells) < 2:
                            continue

                        # Извлекаем данные из ячеек
                        title_cell = cells[0]
                        title_link = title_cell.select_one("a")

                        title = title_link.get_text(strip=True) if title_link else title_cell.get_text(strip=True)
                        link = ""
                        if title_link:
                            link = title_link.get("href", "")
                            if link and not link.startswith("http"):
                                link = urljoin("https://www.adb.org", link)

                        # Пробуем извлечь sector, project, deadline из других ячеек
                        project_id = cells[1].get_text(strip=True) if len(cells) > 1 else ""
                        sector = cells[2].get_text(strip=True) if len(cells) > 2 else ""
                        deadline = cells[3].get_text(strip=True) if len(cells) > 3 else ""
                        budget = cells[4].get_text(strip=True) if len(cells) > 4 else ""

                        results.append({
                            "source": "ADB",
                            "title": title,
                            "url": link or url,
                            "description": f"Sector: {sector}",
                            "project_id": project_id,
                            "donor": "ADB",
                            "budget": budget if budget else None,
                            "tender_deadline": deadline if deadline else None,
                            "status": "Active",
                        })
                    except Exception as e:
                        logger.debug("[ADB] Ошибка парсинга строки таблицы: %s", str(e))
                        continue

            # Пробуем список (views-row)
            if not results:
                items = soup.select(
                    ".views-row, .item-list li, .view-content .views-row, "
                    ".tender-item, article"
                )
                for item in items:
                    try:
                        title_el = item.select_one("h3 a, h4 a, .views-field-title a, a")
                        if not title_el:
                            continue

                        title = title_el.get_text(strip=True)
                        link = title_el.get("href", "")
                        if link and not link.startswith("http"):
                            link = urljoin("https://www.adb.org", link)

                        # Sector
                        sector_el = item.select_one(
                            ".views-field-field-sector, .sector, .field-sector"
                        )
                        sector = sector_el.get_text(strip=True) if sector_el else ""

                        # Deadline
                        date_el = item.select_one(
                            ".views-field-field-date, .date, .deadline, time"
                        )
                        deadline = date_el.get_text(strip=True) if date_el else ""

                        # Project ID
                        proj_el = item.select_one(
                            ".views-field-field-project-number, .project-number"
                        )
                        project_id = proj_el.get_text(strip=True) if proj_el else ""

                        results.append({
                            "source": "ADB",
                            "title": title,
                            "url": link or url,
                            "description": f"Sector: {sector}" if sector else "",
                            "project_id": project_id,
                            "donor": "ADB",
                            "tender_deadline": deadline if deadline else None,
                            "status": "Active",
                        })
                    except Exception as e:
                        logger.debug("[ADB] Ошибка парсинга элемента: %s", str(e))
                        continue

            logger.info("[ADB] Найдено тендеров: %d", len(results))

        except Exception as e:
            logger.error("[ADB] Ошибка парсинга: %s", str(e))

        # Парсим детали для каждого тендера (первые 10)
        detailed_results = []
        for i, tender in enumerate(results[:10]):
            if tender.get("url") and tender["url"] != url:
                await self.delay()
                detail = await self._scrape_detail(tender["url"])
                tender.update({k: v for k, v in detail.items() if v})
            detailed_results.append(tender)

        return detailed_results

    async def _scrape_detail(self, url: str) -> dict:
        """Парсит детальную страницу тендера ADB."""
        detail = {}
        html = await self.fetch(url)
        if not html:
            return detail

        try:
            soup = BeautifulSoup(html, "lxml")

            # Описание
            body = soup.select_one(
                ".field--name-body, .main-content, article .content, #content"
            )
            if body:
                detail["description"] = body.get_text(strip=True)[:1000]

            # Budget
            budget_el = soup.select_one(
                ".field--name-field-amount, .budget, .cost"
            )
            if budget_el:
                detail["budget"] = budget_el.get_text(strip=True)

            # Contact
            contact_el = soup.select_one(
                ".field--name-field-contact, .contact-info"
            )
            if contact_el:
                detail["contact_name"] = contact_el.get_text(strip=True)[:200]

        except Exception as e:
            logger.debug("[ADB] Ошибка парсинга деталей: %s", str(e))

        return detail
