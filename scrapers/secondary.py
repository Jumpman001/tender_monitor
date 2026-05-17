"""
Secondary Sources Scraper — мониторинг (🟡 приоритет):
EIB, EDB/EFSD, KfW, OPEC Fund, FAO, dgMarket.
Все в одном скрапере для упрощения.
"""

from bs4 import BeautifulSoup
from urllib.parse import urljoin

from scrapers.base import BaseScraper
from utils.logger import logger


class SecondaryScraper(BaseScraper):
    """Скрапер для вторичных источников — EIB, EDB, KfW, OPEC Fund, FAO, dgMarket."""

    def __init__(self):
        super().__init__("Secondary")

    # Конфигурация всех вторичных источников
    SECONDARY_SOURCES = [
        {
            "name": "EIB (European Investment Bank)",
            "urls": [
                "https://www.eib.org/en/projects/pipelines/all/index.htm?q=tajikistan",
            ],
            "donor": "EIB",
            "base_domain": "https://www.eib.org",
        },
        {
            "name": "EDB/EFSD (Eurasian Development Bank)",
            "urls": [
                "https://eabr.org/en/projects/?country=Tajikistan",
                "https://efsd.org/en/projects/",
            ],
            "donor": "EDB/EFSD",
            "base_domain": "https://eabr.org",
        },
        {
            "name": "KfW Development Bank",
            "urls": [
                "https://www.kfw-entwicklungsbank.de/International-financing/KfW-Development-Bank/Projects/Project-database/?q=tajikistan+water",
            ],
            "donor": "KfW",
            "base_domain": "https://www.kfw-entwicklungsbank.de",
        },
        {
            "name": "OPEC Fund",
            "urls": [
                "https://opecfund.org/operations?country=Tajikistan",
            ],
            "donor": "OPEC Fund",
            "base_domain": "https://opecfund.org",
        },
        {
            "name": "FAO Procurement",
            "urls": [
                "https://www.fao.org/procurement/general-information/en/",
            ],
            "donor": "FAO",
            "base_domain": "https://www.fao.org",
        },
        {
            "name": "dgMarket",
            "urls": [
                "https://www.dgmarket.com/tenders/np-notice.do?noticeType=PROCUREMENT&country=TJ",
            ],
            "donor": "Various",
            "base_domain": "https://www.dgmarket.com",
        },
    ]

    async def scrape(self) -> list[dict]:
        """Парсит все вторичные источники."""
        results = []

        for source_config in self.SECONDARY_SOURCES:
            source_name = source_config["name"]
            donor = source_config["donor"]
            base_domain = source_config["base_domain"]

            logger.info("[Secondary] Сканирование: %s", source_name)

            for url in source_config["urls"]:
                html = await self.fetch(url)
                if not html:
                    logger.warning("[Secondary] Недоступен: %s", source_name)
                    continue

                try:
                    soup = BeautifulSoup(html, "lxml")
                    source_results = self._parse_generic(soup, url, source_name, donor, base_domain)
                    results.extend(source_results)
                    logger.info(
                        "[Secondary] %s: найдено %d",
                        source_name, len(source_results),
                    )
                except Exception as e:
                    logger.error("[Secondary] Ошибка парсинга %s: %s", source_name, str(e))

                await self.delay()

        logger.info("[Secondary] Всего найдено: %d", len(results))
        return results

    def _parse_generic(
        self,
        soup: BeautifulSoup,
        url: str,
        source_name: str,
        donor: str,
        base_domain: str,
    ) -> list[dict]:
        """Универсальный парсер для всех вторичных источников."""
        results = []

        # Пробуем таблицы
        for table in soup.select("table"):
            rows = table.select("tbody tr, tr")
            for row in rows:
                try:
                    cells = row.select("td")
                    if len(cells) < 2:
                        continue

                    title_el = None
                    for cell in cells:
                        a = cell.select_one("a[href]")
                        if a and len(a.get_text(strip=True)) > 5:
                            title_el = a
                            break

                    if not title_el:
                        continue

                    title = title_el.get_text(strip=True)
                    link = title_el.get("href", "")
                    if link and not link.startswith("http"):
                        link = urljoin(base_domain, link)

                    # Фильтр по Tajikistan
                    row_text = row.get_text(strip=True).lower()
                    if "tajikistan" not in row_text and "таджикистан" not in row_text:
                        # Для EDB — проверяем все строки
                        if donor not in ("EDB/EFSD",):
                            continue

                    description = " | ".join(
                        c.get_text(strip=True) for c in cells[1:] if c.get_text(strip=True)
                    )[:500]

                    results.append({
                        "source": source_name,
                        "title": title,
                        "url": link or url,
                        "description": description,
                        "donor": donor,
                        "status": "Active",
                    })
                except Exception:
                    continue

        # Пробуем карточки/списки
        if not results:
            items = soup.select(
                "article, .card, .project-item, .views-row, .list-item, "
                ".search-result, .result-item, .teaser, .node"
            )
            for item in items:
                try:
                    title_el = item.select_one("a[href], h3 a, h4 a, .title a")
                    if not title_el:
                        continue

                    title = title_el.get_text(strip=True)
                    if not title or len(title) < 5:
                        continue

                    link = title_el.get("href", "")
                    if link and not link.startswith("http"):
                        link = urljoin(base_domain, link)

                    # Фильтр по Tajikistan
                    item_text = item.get_text(strip=True).lower()
                    if "tajikistan" not in item_text and "таджикистан" not in item_text:
                        continue

                    desc_el = item.select_one("p, .description, .summary")
                    description = desc_el.get_text(strip=True)[:500] if desc_el else ""

                    date_el = item.select_one(".date, time, .deadline")
                    deadline = date_el.get_text(strip=True) if date_el else ""

                    results.append({
                        "source": source_name,
                        "title": title,
                        "url": link or url,
                        "description": description,
                        "donor": donor,
                        "tender_deadline": deadline if deadline else None,
                        "status": "Active",
                    })
                except Exception:
                    continue

        return results
