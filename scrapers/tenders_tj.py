"""
tenders.tj Scraper — парсинг локального портала тендеров Таджикистана.
"""

from bs4 import BeautifulSoup
from urllib.parse import urljoin

from scrapers.base import BaseScraper
from utils.logger import logger


class TendersTJScraper(BaseScraper):
    """Скрапер для tenders.tj — местный портал тендеров."""

    def __init__(self):
        super().__init__("tenders.tj")

    async def scrape(self) -> list[dict]:
        """Парсит тендеры с tenders.tj."""
        base_url = "https://tenders.tj/"
        results = []

        html = await self.fetch(base_url)
        if not html:
            logger.warning("[tenders.tj] Не удалось загрузить страницу")
            return results

        try:
            soup = BeautifulSoup(html, "lxml")

            # Ищем карточки тендеров
            # tenders.tj может использовать таблицу или список карточек
            items = soup.select(
                ".tender-item, .tender-card, .tenders-list .item, "
                "table tbody tr, .list-group-item, article, "
                ".card, .views-row, .tender"
            )

            for item in items:
                try:
                    # Заголовок и ссылка
                    title_el = item.select_one(
                        "a[href], h3 a, h4 a, .title a, .tender-title a"
                    )
                    if not title_el:
                        # Пробуем из ячеек таблицы
                        cells = item.select("td")
                        if cells:
                            title_el = cells[0].select_one("a")
                        if not title_el:
                            continue

                    title = title_el.get_text(strip=True)
                    if not title or len(title) < 5:
                        continue

                    link = title_el.get("href", "")
                    if link and not link.startswith("http"):
                        link = urljoin(base_url, link)

                    # Описание
                    desc_el = item.select_one(
                        ".description, .tender-description, .summary, p, "
                        ".field--name-body"
                    )
                    description = desc_el.get_text(strip=True)[:500] if desc_el else ""

                    # Дата
                    date_el = item.select_one(
                        ".date, .deadline, time, .tender-date, "
                        ".field--name-field-date"
                    )
                    deadline = date_el.get_text(strip=True) if date_el else ""

                    # Категория
                    cat_el = item.select_one(
                        ".category, .tender-category, .badge, .tag"
                    )
                    category = cat_el.get_text(strip=True) if cat_el else ""

                    # Бюджет
                    budget_el = item.select_one(
                        ".price, .budget, .amount, .tender-budget"
                    )
                    budget = budget_el.get_text(strip=True) if budget_el else ""

                    # Регион
                    region_el = item.select_one(
                        ".region, .location, .tender-region"
                    )
                    region = region_el.get_text(strip=True) if region_el else ""

                    results.append({
                        "source": "tenders.tj",
                        "title": title,
                        "url": link or base_url,
                        "description": f"{category}. {description}".strip(". "),
                        "budget": budget if budget else None,
                        "tender_deadline": deadline if deadline else None,
                        "region": region if region else None,
                        "status": "Active",
                    })
                except Exception as e:
                    logger.debug("[tenders.tj] Ошибка парсинга элемента: %s", str(e))
                    continue

            logger.info("[tenders.tj] Найдено тендеров: %d", len(results))

        except Exception as e:
            logger.error("[tenders.tj] Ошибка парсинга: %s", str(e))

        # Парсим детали (первые 15 тендеров)
        for i, tender in enumerate(results[:15]):
            if tender.get("url") and tender["url"] != base_url:
                await self.delay()
                detail = await self._scrape_detail(tender["url"])
                tender.update({k: v for k, v in detail.items() if v})

        return results

    async def _scrape_detail(self, url: str) -> dict:
        """Парсит детальную страницу тендера на tenders.tj."""
        detail = {}
        html = await self.fetch(url)
        if not html:
            return detail

        try:
            soup = BeautifulSoup(html, "lxml")

            # Описание
            content = soup.select_one(
                ".tender-detail, .content, .main-content, article, "
                "#content, .tender-body"
            )
            if content:
                detail["description"] = content.get_text(strip=True)[:1500]

            # Контактная информация
            contact_section = soup.select_one(
                ".contact, .contact-info, .contacts"
            )
            if contact_section:
                text = contact_section.get_text()
                # Email
                import re
                emails = re.findall(r'[\w.+-]+@[\w-]+\.[\w.]+', text)
                if emails:
                    detail["contact_email"] = emails[0]
                # Телефон
                phones = re.findall(r'[\+\d][\d\s\-\(\)]{8,}', text)
                if phones:
                    detail["contact_phone"] = phones[0].strip()

            # Бюджет
            for el in soup.select("dt, th, strong, .label, td"):
                el_text = el.get_text(strip=True).lower()
                if any(kw in el_text for kw in ["бюджет", "сумма", "стоимость", "budget", "price"]):
                    sibling = el.find_next_sibling()
                    if sibling:
                        detail["budget"] = sibling.get_text(strip=True)

            # Регион
            for el in soup.select("dt, th, strong, .label, td"):
                el_text = el.get_text(strip=True).lower()
                if any(kw in el_text for kw in ["регион", "область", "район", "region", "location"]):
                    sibling = el.find_next_sibling()
                    if sibling:
                        detail["region"] = sibling.get_text(strip=True)

        except Exception as e:
            logger.debug("[tenders.tj] Ошибка парсинга деталей: %s", str(e))

        return detail
