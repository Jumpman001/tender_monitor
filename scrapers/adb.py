"""
ADB Scraper v2 — исправленная версия.

ПРОБЛЕМА оригинала: adb.org/projects/tenders — React-приложение.
BeautifulSoup получает <div id="app"></div> → 0 результатов.

РЕШЕНИЕ:
- ADB тендеры → официальный RSS фид (чистый XML, без JS)
- ADB проекты → JSON API (search.adb.org)
- Детали тендера → парсим HTML отдельных страниц (они простые)
"""

import feedparser
from bs4 import BeautifulSoup
from urllib.parse import urljoin

from scrapers.base import BaseScraper
from utils.logger import logger


class ADBScraper(BaseScraper):

    def __init__(self):
        super().__init__("ADB")

    async def scrape(self) -> list[dict]:
        results = []

        # 1. ADB RSS — главный источник (надёжный, без JS)
        rss = await self._scrape_rss()
        results.extend(rss)
        logger.info("[ADB] RSS: %d тендеров", len(rss))
        await self.delay()

        # 2. ADB JSON API проектов
        api = await self._scrape_projects_api()
        results.extend(api)
        logger.info("[ADB] Projects API: %d проектов", len(api))

        logger.info("[ADB] ИТОГО: %d", len(results))
        return results

    # ──────────────────────────────────────────────────────────────────────────
    # 1. ADB RSS FEED — самый надёжный способ
    # ──────────────────────────────────────────────────────────────────────────
    async def _scrape_rss(self) -> list[dict]:
        """
        Официальный RSS ADB по тендерам Таджикистана.
        Документация: adb.org/rss
        Не требует JS — чистый XML.
        """
        # RSS фиды ADB по Таджикистану
        rss_urls = [
            "https://www.adb.org/rss/projects/tenders?country=TAJ",
            # Fallback — все активные тендеры (фильтруем по TJ сами)
            "https://www.adb.org/rss/projects/tenders?status=Active",
        ]
        results = []
        seen_links = set()

        for rss_url in rss_urls:
            try:
                rss_text = await self.fetch(rss_url)
                if not rss_text:
                    logger.warning("[ADB] RSS недоступен: %s", rss_url[:60])
                    continue

                feed = feedparser.parse(rss_text)
                if not feed.entries:
                    logger.warning("[ADB] RSS пуст: %s", rss_url[:60])
                    continue

                for entry in feed.entries:
                    link = entry.get("link", "")
                    if link in seen_links:
                        continue
                    seen_links.add(link)

                    title = entry.get("title", "").strip()
                    summary = entry.get("summary", entry.get("description", ""))
                    published = entry.get("published", "")
                    category = entry.get("tags", [{}])[0].get("term", "") if entry.get("tags") else ""

                    if not title:
                        continue

                    # Если парсим общий фид — фильтруем по Tajikistan
                    if "country=TAJ" not in rss_url:
                        combined = f"{title} {summary}".lower()
                        if "tajikistan" not in combined and "TAJ" not in combined:
                            continue

                    # Очищаем HTML из summary
                    clean_desc = ""
                    if summary:
                        clean_desc = BeautifulSoup(summary, "lxml").get_text(strip=True)[:600]

                    results.append({
                        "source": "ADB",
                        "title": title,
                        "url": link,
                        "description": clean_desc,
                        "donor": "Asian Development Bank",
                        "tender_deadline": published[:10] if published else None,
                        "region": "Tajikistan",
                        "status": "Active",
                    })

                logger.info("[ADB] RSS %s: %d записей", rss_url[-30:], len(feed.entries))
                break  # Если первый RSS сработал — второй не нужен

            except Exception as e:
                logger.error("[ADB] RSS ошибка (%s): %s", rss_url[:40], e)

        # Парсим детали для первых 10 результатов
        for tender in results[:10]:
            if tender.get("url") and "adb.org" in tender["url"]:
                await self.delay()
                detail = await self._scrape_detail_page(tender["url"])
                tender.update({k: v for k, v in detail.items() if v})

        return results

    # ──────────────────────────────────────────────────────────────────────────
    # 2. ADB PROJECTS JSON API
    # ──────────────────────────────────────────────────────────────────────────
    async def _scrape_projects_api(self) -> list[dict]:
        """
        ADB Projects API — список активных проектов по Таджикистану.
        Возвращает JSON без JS-рендеринга.
        """
        # ADB search API
        api_url = (
            "https://www.adb.org/api/projects/search"
            "?country=TAJ&status=active&page=1&per_page=30"
        )
        results = []
        data = await self.fetch_json(api_url)

        if not data:
            # Fallback: попробуем другой формат
            api_url2 = "https://www.adb.org/api/v1/projects?country=TAJ&status=Active"
            data = await self.fetch_json(api_url2)

        if not data:
            logger.warning("[ADB] Projects API не ответил")
            return results

        try:
            # ADB API может вернуть разные структуры
            projects = []
            if isinstance(data, list):
                projects = data
            elif isinstance(data, dict):
                projects = (
                    data.get("projects", [])
                    or data.get("data", [])
                    or data.get("results", [])
                    or list(data.values())
                )

            for proj in projects:
                if not isinstance(proj, dict):
                    continue

                title = (
                    proj.get("title", "")
                    or proj.get("project_title", "")
                    or proj.get("name", "")
                ).strip()

                if not title:
                    continue

                proj_id = (
                    proj.get("project_number", "")
                    or proj.get("id", "")
                    or proj.get("projectNumber", "")
                )
                proj_url = (
                    proj.get("url", "")
                    or proj.get("link", "")
                    or f"https://www.adb.org/projects/{proj_id}/main"
                )
                budget = proj.get("loan_amount", proj.get("amount", proj.get("totalAmount", "")))
                sector = proj.get("sector", proj.get("theme", ""))
                closing = proj.get("closing_date", proj.get("endDate", ""))

                budget_str = ""
                if budget:
                    try:
                        budget_str = f"$ {int(float(str(budget).replace(',', ''))):,}"
                    except Exception:
                        budget_str = str(budget)

                results.append({
                    "source": "ADB Projects",
                    "title": title,
                    "url": proj_url if proj_url.startswith("http") else f"https://www.adb.org{proj_url}",
                    "description": f"Sector: {sector}" if sector else "",
                    "project_id": str(proj_id),
                    "donor": "Asian Development Bank",
                    "budget": budget_str,
                    "contract_completion": str(closing)[:10] if closing else None,
                    "region": "Tajikistan",
                    "status": "Active",
                })

        except Exception as e:
            logger.error("[ADB] Projects API parse error: %s", e)

        return results

    # ──────────────────────────────────────────────────────────────────────────
    # 3. ДЕТАЛЬНАЯ СТРАНИЦА — отдельные страницы тендеров простые HTML
    # ──────────────────────────────────────────────────────────────────────────
    async def _scrape_detail_page(self, url: str) -> dict:
        """
        Детальные страницы ADB тендеров (не список!) — обычный HTML.
        Парсится нормально через BeautifulSoup.
        """
        detail = {}
        html = await self.fetch(url)
        if not html:
            return detail

        try:
            soup = BeautifulSoup(html, "lxml")

            # ADB detail page структура
            # Ищем пары label: value
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

            # Описание
            desc = soup.select_one(".field--name-body, .project-description, #content .text")
            if desc:
                detail["description"] = desc.get_text(strip=True)[:1000]

        except Exception as e:
            logger.debug("[ADB] Detail parse error %s: %s", url[:50], e)

        return detail
