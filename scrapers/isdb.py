"""
IsDB Scraper — Islamic Development Bank procurement.
$916 млн в Таджикистан, 50% в инфраструктуру.
"""

from bs4 import BeautifulSoup
from urllib.parse import urljoin

from scrapers.base import BaseScraper
from utils.logger import logger


class IsDBScraper(BaseScraper):
    """Скрапер для Islamic Development Bank procurement."""

    def __init__(self):
        super().__init__("IsDB")

    async def scrape(self) -> list[dict]:
        """Парсит тендеры IsDB для Таджикистана."""
        results = []

        # IsDB Procurement portal — поиск по Tajikistan
        urls = [
            "https://www.isdb.org/procurement",
            "https://www.isdb.org/procurement?country=Tajikistan",
        ]

        for base_url in urls:
            html = await self.fetch(base_url)
            if not html:
                logger.warning("[IsDB] Не удалось загрузить: %s", base_url[:60])
                continue

            try:
                soup = BeautifulSoup(html, "lxml")

                # Ищем карточки/таблицу закупок
                items = soup.select(
                    "table tbody tr, .procurement-item, .views-row, "
                    ".card, article, .list-item, .node--type-procurement, "
                    ".procurement-notice, .tender-item"
                )

                for item in items:
                    try:
                        title_el = item.select_one(
                            "a[href], h3 a, h4 a, .title a, .field--name-title a"
                        )
                        if not title_el:
                            cells = item.select("td")
                            if cells and len(cells) >= 2:
                                title_el = cells[0].select_one("a")
                            if not title_el:
                                continue

                        title = title_el.get_text(strip=True)
                        if not title or len(title) < 5:
                            continue

                        link = title_el.get("href", "")
                        if link and not link.startswith("http"):
                            link = urljoin("https://www.isdb.org", link)

                        # Описание
                        desc_el = item.select_one(
                            ".description, .summary, p, .field--name-body, .teaser"
                        )
                        description = desc_el.get_text(strip=True)[:500] if desc_el else ""

                        # Дата
                        date_el = item.select_one(
                            ".date, time, .deadline, .field--name-field-deadline"
                        )
                        deadline = date_el.get_text(strip=True) if date_el else ""

                        # Страна
                        country_el = item.select_one(
                            ".country, .field--name-field-country, .location"
                        )
                        country = country_el.get_text(strip=True) if country_el else ""

                        # Фильтруем по Tajikistan (если не отфильтровано URL-ом)
                        combined = f"{title} {description} {country}".lower()
                        if "tajikistan" not in combined and "таджикистан" not in combined:
                            # Если URL уже содержит country=Tajikistan, берём всё
                            if "country=Tajikistan" not in base_url:
                                continue

                        # Сектор
                        sector_el = item.select_one(
                            ".sector, .field--name-field-sector, .category"
                        )
                        sector = sector_el.get_text(strip=True) if sector_el else ""

                        results.append({
                            "source": "IsDB",
                            "title": title,
                            "url": link or base_url,
                            "description": f"Sector: {sector}. {description}".strip(". ") if sector else description,
                            "donor": "Islamic Development Bank",
                            "tender_deadline": deadline if deadline else None,
                            "region": country if country else None,
                            "status": "Active",
                        })
                    except Exception as e:
                        logger.debug("[IsDB] Ошибка парсинга элемента: %s", str(e))
                        continue

            except Exception as e:
                logger.error("[IsDB] Ошибка парсинга: %s", str(e))

            await self.delay()

        # Парсим детали (первые 10)
        for tender in results[:10]:
            if tender.get("url") and "isdb.org" in tender["url"]:
                await self.delay()
                detail = await self._scrape_detail(tender["url"])
                tender.update({k: v for k, v in detail.items() if v})

        logger.info("[IsDB] Найдено тендеров: %d", len(results))
        return results

    async def _scrape_detail(self, url: str) -> dict:
        """Парсит детальную страницу тендера IsDB."""
        detail = {}
        html = await self.fetch(url)
        if not html:
            return detail

        try:
            soup = BeautifulSoup(html, "lxml")

            content = soup.select_one(
                ".field--name-body, .main-content, article .content, #content"
            )
            if content:
                detail["description"] = content.get_text(strip=True)[:1500]

            # Ищем бюджет, контакты в парах label-value
            for label in soup.select("dt, th, strong, .label, .field__label"):
                label_text = label.get_text(strip=True).lower()
                sibling = label.find_next_sibling()
                if not sibling:
                    parent = label.parent
                    if parent:
                        sibling = parent.find_next_sibling()
                if not sibling:
                    continue
                value = sibling.get_text(strip=True)

                if any(kw in label_text for kw in ["budget", "amount", "value", "cost"]):
                    detail["budget"] = value
                elif any(kw in label_text for kw in ["deadline", "closing", "submission"]):
                    detail["tender_deadline"] = value
                elif "email" in label_text or "@" in value:
                    detail["contact_email"] = value
                elif "contact" in label_text:
                    detail["contact_name"] = value
                elif "project" in label_text and ("id" in label_text or "number" in label_text):
                    detail["project_id"] = value

        except Exception as e:
            logger.debug("[IsDB] Ошибка парсинга деталей: %s", str(e))

        return detail
