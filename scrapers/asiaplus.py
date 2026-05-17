"""
Asia-Plus Scraper — asiaplustj.info, главные новости Таджикистана.
Сигнализирует о новых проектах за 6–12 месяцев до тендера.
"""

from bs4 import BeautifulSoup
from urllib.parse import urljoin, quote

from scrapers.base import BaseScraper
from utils.logger import logger


class AsiaPlusScraper(BaseScraper):
    """Скрапер для asiaplustj.info — новостной сигнал о будущих проектах."""

    def __init__(self):
        super().__init__("AsiaPlus")

    async def scrape(self) -> list[dict]:
        """Парсит новости Asia-Plus о водных проектах."""
        results = []

        # Поиск по ключевым словам — вода, ирригация, трубопровод
        search_queries = [
            "водоснабжение",
            "ирригация",
            "трубопровод",
            "водовод",
            "канализация",
            "water supply",
        ]

        for query in search_queries:
            url = f"https://asiaplustj.info/ru/search?q={quote(query)}"

            html = await self.fetch(url)
            if not html:
                logger.warning("[AsiaPlus] Не удалось загрузить поиск: %s", query)
                await self.delay()
                continue

            try:
                soup = BeautifulSoup(html, "lxml")

                # Результаты поиска — статьи
                items = soup.select(
                    "article, .search-result, .result-item, .news-item, "
                    ".card, .list-item, .views-row, .article-item, "
                    ".teaser, .post-item"
                )

                for item in items:
                    try:
                        title_el = item.select_one(
                            "a[href], h2 a, h3 a, h4 a, .title a, .heading a"
                        )
                        if not title_el:
                            continue

                        title = title_el.get_text(strip=True)
                        if not title or len(title) < 10:
                            continue

                        link = title_el.get("href", "")
                        if link and not link.startswith("http"):
                            link = urljoin("https://asiaplustj.info", link)

                        # Дата публикации
                        date_el = item.select_one(
                            ".date, time, .datetime, .published, .post-date"
                        )
                        pub_date = date_el.get_text(strip=True) if date_el else ""

                        # Краткое описание
                        desc_el = item.select_one(
                            "p, .description, .summary, .teaser-text, .excerpt"
                        )
                        description = desc_el.get_text(strip=True)[:500] if desc_el else ""

                        results.append({
                            "source": "AsiaPlus (новости)",
                            "title": title,
                            "url": link or url,
                            "description": description,
                            "donor": None,
                            "tender_deadline": None,
                            "status": "Planned",  # Это новость, а не тендер
                            "contract_completion": pub_date if pub_date else None,
                        })
                    except Exception as e:
                        logger.debug("[AsiaPlus] Ошибка парсинга элемента: %s", str(e))
                        continue

            except Exception as e:
                logger.error("[AsiaPlus] Ошибка парсинга: %s", str(e))

            await self.delay()

        # Также парсим главную для свежих новостей
        await self._scrape_main_page(results)

        logger.info("[AsiaPlus] Найдено релевантных новостей: %d", len(results))
        return results

    async def _scrape_main_page(self, results: list[dict]) -> None:
        """Парсит главную страницу для свежих упоминаний."""
        url = "https://asiaplustj.info/ru"
        html = await self.fetch(url)
        if not html:
            return

        try:
            soup = BeautifulSoup(html, "lxml")

            # Все ссылки на статьи
            links = soup.select("a[href]")

            water_keywords = [
                "вод", "ирригаци", "труб", "канализ", "насос",
                "мелиор", "дренаж", "water", "irrigation", "pipe",
                "wsip", "всемирный банк", "world bank", "adb", "ebrd",
            ]

            for link_el in links:
                try:
                    title = link_el.get_text(strip=True)
                    if not title or len(title) < 15:
                        continue

                    title_lower = title.lower()
                    if not any(kw in title_lower for kw in water_keywords):
                        continue

                    link = link_el.get("href", "")
                    if link and not link.startswith("http"):
                        link = urljoin("https://asiaplustj.info", link)

                    # Проверяем что это уникальная статья
                    if any(r["url"] == link for r in results):
                        continue

                    results.append({
                        "source": "AsiaPlus (новости)",
                        "title": title,
                        "url": link,
                        "description": "",
                        "donor": None,
                        "status": "Planned",
                    })
                except Exception:
                    continue

        except Exception as e:
            logger.error("[AsiaPlus] Ошибка парсинга главной: %s", str(e))
