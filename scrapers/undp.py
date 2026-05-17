"""
UNDP Scraper — United Nations Development Programme procurement notices.
Публикует закупки по воде и ирригации отдельно от tajikistan.un.org.
"""

from bs4 import BeautifulSoup
from urllib.parse import urljoin

from scrapers.base import BaseScraper
from utils.logger import logger


class UNDPScraper(BaseScraper):
    """Скрапер для UNDP procurement notices."""

    def __init__(self):
        super().__init__("UNDP")

    async def scrape(self) -> list[dict]:
        """Парсит закупки UNDP для Таджикистана."""
        results = []

        # UNDP Procurement Notices — Tajikistan
        urls = [
            "https://procurement-notices.undp.org/view_notices.cfm?Country=TJK",
            "https://procurement-notices.undp.org/view_notices.cfm?Country=TJK&category=4",  # Infrastructure
        ]

        for base_url in urls:
            html = await self.fetch(base_url)
            if not html:
                logger.warning("[UNDP] Не удалось загрузить: %s", base_url[:60])
                continue

            try:
                soup = BeautifulSoup(html, "lxml")

                # UNDP обычно показывает таблицу
                table = soup.select_one("table")
                if table:
                    rows = table.select("tbody tr, tr")
                    for row in rows:
                        try:
                            cells = row.select("td")
                            if len(cells) < 3:
                                continue

                            # Заголовок — обычно первая ячейка с ссылкой
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

                            # Дедлайн — обычно последняя ячейка с датой
                            deadline = ""
                            for cell in reversed(cells):
                                text = cell.get_text(strip=True)
                                if any(c.isdigit() for c in text) and (
                                    "/" in text or "-" in text or "20" in text
                                ):
                                    deadline = text
                                    break

                            # Тип/категория
                            category = ""
                            if len(cells) > 1:
                                category = cells[1].get_text(strip=True)

                            results.append({
                                "source": "UNDP",
                                "title": title,
                                "url": link or base_url,
                                "description": f"Category: {category}" if category else "",
                                "donor": "UNDP",
                                "tender_deadline": deadline if deadline else None,
                                "status": "Active",
                            })
                        except Exception as e:
                            logger.debug("[UNDP] Ошибка парсинга строки: %s", str(e))
                            continue

                # Если нет таблицы — ищем карточки
                if not results:
                    items = soup.select(
                        ".notice-item, .views-row, article, .card, "
                        ".list-item, .procurement-notice"
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

                            desc_el = item.select_one("p, .description, .summary")
                            description = desc_el.get_text(strip=True)[:500] if desc_el else ""

                            date_el = item.select_one(".date, time, .deadline")
                            deadline = date_el.get_text(strip=True) if date_el else ""

                            results.append({
                                "source": "UNDP",
                                "title": title,
                                "url": link or base_url,
                                "description": description,
                                "donor": "UNDP",
                                "tender_deadline": deadline if deadline else None,
                                "status": "Active",
                            })
                        except Exception as e:
                            logger.debug("[UNDP] Ошибка парсинга карточки: %s", str(e))
                            continue

            except Exception as e:
                logger.error("[UNDP] Ошибка парсинга: %s", str(e))

            await self.delay()

        # Парсим детали (первые 10)
        for tender in results[:10]:
            if tender.get("url") and "undp.org" in tender["url"]:
                await self.delay()
                detail = await self._scrape_detail(tender["url"])
                tender.update({k: v for k, v in detail.items() if v})

        logger.info("[UNDP] Найдено тендеров: %d", len(results))
        return results

    async def _scrape_detail(self, url: str) -> dict:
        """Парсит детальную страницу закупки UNDP."""
        detail = {}
        html = await self.fetch(url)
        if not html:
            return detail

        try:
            soup = BeautifulSoup(html, "lxml")

            content = soup.select_one(
                ".main-content, #content, .notice-detail, article, .content-area"
            )
            if content:
                detail["description"] = content.get_text(strip=True)[:1500]

            # Ищем поля
            for label in soup.select("dt, th, strong, .label, b"):
                label_text = label.get_text(strip=True).lower()
                sibling = label.find_next_sibling()
                if not sibling:
                    continue
                value = sibling.get_text(strip=True)

                if any(kw in label_text for kw in ["budget", "amount", "value"]):
                    detail["budget"] = value
                elif any(kw in label_text for kw in ["deadline", "closing", "submission"]):
                    detail["tender_deadline"] = value
                elif "email" in label_text or "@" in value:
                    detail["contact_email"] = value
                elif "contact" in label_text or "focal" in label_text:
                    detail["contact_name"] = value
                elif "reference" in label_text or "notice" in label_text:
                    detail["project_id"] = value

        except Exception as e:
            logger.debug("[UNDP] Ошибка парсинга деталей: %s", str(e))

        return detail
