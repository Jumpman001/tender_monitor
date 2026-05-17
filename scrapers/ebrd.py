"""
EBRD Scraper — European Bank for Reconstruction and Development procurement notices.
"""

from bs4 import BeautifulSoup
from urllib.parse import urljoin

from scrapers.base import BaseScraper
from utils.logger import logger


class EBRDScraper(BaseScraper):
    """Скрапер для EBRD procurement notices — Таджикистан."""

    def __init__(self):
        super().__init__("EBRD")

    async def scrape(self) -> list[dict]:
        """Парсит procurement notices EBRD для Таджикистана."""
        url = (
            "https://www.ebrd.com/work-with-us/procurement/"
            "project-procurement-notices.html?1=1&filterCountry=Tajikistan"
        )
        results = []

        html = await self.fetch(url)
        if not html:
            logger.warning("[EBRD] Не удалось загрузить страницу")
            return results

        try:
            soup = BeautifulSoup(html, "lxml")

            # EBRD отображает notices в таблице или карточках
            # Пробуем таблицу
            table = soup.select_one("table.procurement-table, table")
            if table:
                rows = table.select("tbody tr")
                for row in rows:
                    try:
                        cells = row.select("td")
                        if len(cells) < 2:
                            continue

                        title_cell = cells[0]
                        title_link = title_cell.select_one("a")
                        title = (
                            title_link.get_text(strip=True)
                            if title_link
                            else title_cell.get_text(strip=True)
                        )

                        link = ""
                        if title_link:
                            link = title_link.get("href", "")
                            if link and not link.startswith("http"):
                                link = urljoin("https://www.ebrd.com", link)

                        # Извлекаем поля
                        country = cells[1].get_text(strip=True) if len(cells) > 1 else ""
                        sector = cells[2].get_text(strip=True) if len(cells) > 2 else ""
                        notice_type = cells[3].get_text(strip=True) if len(cells) > 3 else ""
                        deadline = cells[4].get_text(strip=True) if len(cells) > 4 else ""

                        results.append({
                            "source": "EBRD",
                            "title": title,
                            "url": link or url,
                            "description": f"Sector: {sector}. Notice type: {notice_type}",
                            "donor": "EBRD",
                            "tender_deadline": deadline if deadline else None,
                            "region": country if "tajikistan" in country.lower() else None,
                            "status": "Active",
                        })
                    except Exception as e:
                        logger.debug("[EBRD] Ошибка парсинга строки: %s", str(e))
                        continue

            # Пробуем карточки/список
            if not results:
                items = soup.select(
                    ".procurement-notice, .notice-item, .search-result, "
                    ".views-row, article, .list-item"
                )
                for item in items:
                    try:
                        title_el = item.select_one("h3 a, h4 a, a.title, a[href]")
                        if not title_el:
                            continue

                        title = title_el.get_text(strip=True)
                        if not title or len(title) < 5:
                            continue

                        link = title_el.get("href", "")
                        if link and not link.startswith("http"):
                            link = urljoin("https://www.ebrd.com", link)

                        desc_el = item.select_one("p, .description, .summary")
                        description = desc_el.get_text(strip=True)[:500] if desc_el else ""

                        date_el = item.select_one(".date, time, .deadline")
                        deadline = date_el.get_text(strip=True) if date_el else ""

                        results.append({
                            "source": "EBRD",
                            "title": title,
                            "url": link or url,
                            "description": description,
                            "donor": "EBRD",
                            "tender_deadline": deadline if deadline else None,
                            "status": "Active",
                        })
                    except Exception as e:
                        logger.debug("[EBRD] Ошибка парсинга карточки: %s", str(e))
                        continue

            logger.info("[EBRD] Найдено тендеров: %d", len(results))

        except Exception as e:
            logger.error("[EBRD] Ошибка парсинга: %s", str(e))

        # Парсим детали для каждого тендера (первые 10)
        for i, tender in enumerate(results[:10]):
            if tender.get("url") and tender["url"] != url:
                await self.delay()
                detail = await self._scrape_detail(tender["url"])
                tender.update({k: v for k, v in detail.items() if v})

        return results

    async def _scrape_detail(self, url: str) -> dict:
        """Парсит детальную страницу procurement notice EBRD."""
        detail = {}
        html = await self.fetch(url)
        if not html:
            return detail

        try:
            soup = BeautifulSoup(html, "lxml")

            # Основное описание
            content = soup.select_one(
                ".field--name-body, .main-content, .procurement-detail, "
                "#content, article .content"
            )
            if content:
                detail["description"] = content.get_text(strip=True)[:1500]

            # Бюджет
            for label in soup.select("dt, th, strong, .label"):
                label_text = label.get_text(strip=True).lower()
                sibling = label.find_next_sibling()
                if not sibling:
                    continue
                value = sibling.get_text(strip=True)

                if "budget" in label_text or "value" in label_text or "amount" in label_text:
                    detail["budget"] = value
                elif "deadline" in label_text or "closing" in label_text:
                    detail["tender_deadline"] = value
                elif "contact" in label_text or "email" in label_text:
                    if "@" in value:
                        detail["contact_email"] = value
                    else:
                        detail["contact_name"] = value
                elif "sector" in label_text:
                    detail["description"] = f"Sector: {value}. " + detail.get("description", "")

        except Exception as e:
            logger.debug("[EBRD] Ошибка парсинга деталей: %s", str(e))

        return detail
