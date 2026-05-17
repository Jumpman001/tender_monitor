"""
WorldBank Scraper v2 — исправленная версия.

ПРОБЛЕМА оригинала: tajikistan.un.org и STEP рендерятся через JavaScript.
BeautifulSoup получает пустой HTML → 0 результатов.

РЕШЕНИЕ:
- World Bank Projects → JSON API (search.worldbank.org/api/v2)
- World Bank STEP    → JSON API (search.worldbank.org/api/v2/procnotices)
- UN Tajikistan      → DGMarket RSS (агрегирует все UN тендеры)
- wsip-1.tj          → прямой HTML парсинг (простой сайт, без JS)
"""

import feedparser
from bs4 import BeautifulSoup
from urllib.parse import urljoin

from scrapers.base import BaseScraper
from utils.logger import logger


class WorldBankScraper(BaseScraper):

    def __init__(self):
        super().__init__("WorldBank")

    async def scrape(self) -> list[dict]:
        results = []

        # 1. World Bank Projects JSON API
        wb = await self._scrape_wb_api()
        results.extend(wb)
        logger.info("[WorldBank] WB Projects API: %d", len(wb))
        await self.delay()

        # 2. World Bank STEP Procurement JSON API
        step = await self._scrape_step_api()
        results.extend(step)
        logger.info("[WorldBank] STEP API: %d", len(step))
        await self.delay()

        # 3. DGMarket RSS — агрегирует UN, ВБ, АБР тендеры по Таджикистану
        dgm = await self._scrape_dgmarket_rss()
        results.extend(dgm)
        logger.info("[WorldBank] DGMarket RSS: %d", len(dgm))
        await self.delay()

        # 4. wsip-1.tj — простой HTML, парсится нормально
        wsip = await self._scrape_wsip()
        results.extend(wsip)
        logger.info("[WorldBank] WSIP-1 PMU: %d", len(wsip))

        logger.info("[WorldBank] ИТОГО: %d", len(results))
        return results

    # ──────────────────────────────────────────────────────────────────────────
    # 1. WORLD BANK PROJECTS — JSON API
    # ──────────────────────────────────────────────────────────────────────────
    async def _scrape_wb_api(self) -> list[dict]:
        """
        Официальный JSON API World Bank Projects.
        Документация: https://datahelpdesk.worldbank.org/knowledgebase/articles/898580
        """
        api_url = (
            "https://search.worldbank.org/api/v2/projects"
            "?format=json"
            "&countrycode_exact=TJ"
            "&status_exact=Active"
            "&fl=id,project_name,status,boardapprovaldate,closingdate,"
            "totalamt,sector1,mjtheme1nam,regionname,countryshortname"
            "&rows=50&os=0"
        )
        results = []
        data = await self.fetch_json(api_url)
        if not data:
            logger.warning("[WorldBank] WB API не ответил")
            return results

        try:
            projects = data.get("projects", {})
            for proj_id, proj in projects.items():
                if not isinstance(proj, dict):
                    continue

                title = proj.get("project_name", "").strip()
                if not title:
                    continue

                wb_id = proj.get("id", proj_id)
                closing = proj.get("closingdate", "")
                total_amt = proj.get("totalamt", 0)
                sector = proj.get("sector1", {})
                sector_name = sector.get("Name", "") if isinstance(sector, dict) else ""

                budget_str = ""
                if total_amt:
                    try:
                        budget_str = f"$ {int(float(total_amt)):,}"
                    except Exception:
                        budget_str = str(total_amt)

                results.append({
                    "source": "World Bank",
                    "title": title,
                    "url": f"https://projects.worldbank.org/en/projects-operations/project-detail/{wb_id}",
                    "description": f"Sector: {sector_name}" if sector_name else "",
                    "project_id": wb_id,
                    "donor": "World Bank IDA",
                    "budget": budget_str,
                    "contract_completion": closing[:10] if closing else None,
                    "status": proj.get("status", "Active"),
                })
        except Exception as e:
            logger.error("[WorldBank] Ошибка WB API: %s", e)

        return results

    # ──────────────────────────────────────────────────────────────────────────
    # 2. WORLD BANK STEP — JSON API закупок
    # ──────────────────────────────────────────────────────────────────────────
    async def _scrape_step_api(self) -> list[dict]:
        """
        STEP Procurement Notices — JSON API.
        Это правильный способ получить данные о закупках ВБ без JS.
        """
        api_url = (
            "https://search.worldbank.org/api/v2/procnotices"
            "?format=json"
            "&project_ctry_code=TJ"
            "&rows=50&os=0"
        )
        results = []
        data = await self.fetch_json(api_url)
        if not data:
            # Fallback: попробуем другой endpoint
            data = await self._step_fallback()
        if not data:
            return results

        try:
            notices = data.get("procnotices", {})
            if isinstance(notices, dict):
                notices = list(notices.values())
            elif not isinstance(notices, list):
                notices = []

            for notice in notices:
                if not isinstance(notice, dict):
                    continue

                title = notice.get("noticeTitle", notice.get("title", "")).strip()
                if not title:
                    continue

                proj_id = notice.get("id", notice.get("project_id", ""))
                deadline = notice.get("deadlineDate", notice.get("deadline", ""))
                contact = notice.get("contactEmail", "")
                budget = notice.get("estimatedValue", "")
                notice_url = notice.get("url", notice.get("link", ""))
                if not notice_url:
                    notice_url = f"https://projects.worldbank.org/en/projects-operations/procurement/noticesearch?OP_LANG=EN&project_ctry_code=TJ"

                results.append({
                    "source": "World Bank STEP",
                    "title": title,
                    "url": notice_url,
                    "project_id": str(proj_id),
                    "donor": "World Bank IDA",
                    "budget": str(budget) if budget else None,
                    "tender_deadline": str(deadline)[:10] if deadline else None,
                    "contact_email": contact if contact else None,
                    "status": "Active",
                })
        except Exception as e:
            logger.error("[WorldBank] Ошибка STEP API: %s", e)

        return results

    async def _step_fallback(self) -> dict | None:
        """Резервный STEP endpoint если основной не ответил."""
        fallback_url = (
            "https://search.worldbank.org/api/v2/procnotices"
            "?format=json&countrycode=TJ&rows=30&os=0"
        )
        return await self.fetch_json(fallback_url)

    # ──────────────────────────────────────────────────────────────────────────
    # 3. DGMARKET RSS — агрегирует UN, ВБ, АБР тендеры
    # ──────────────────────────────────────────────────────────────────────────
    async def _scrape_dgmarket_rss(self) -> list[dict]:
        """
        DGMarket RSS — надёжный агрегатор всех донорских тендеров по TJ.
        Включает UN Tajikistan, UNDP, ВБ, АБР тендеры в одном фиде.
        НЕ требует JavaScript — чистый XML.
        """
        rss_url = "https://www.dgmarket.com/tenders/rss.do?countryId=TJ"
        results = []

        try:
            rss_text = await self.fetch(rss_url)
            if not rss_text:
                logger.warning("[WorldBank] DGMarket RSS недоступен")
                return results

            feed = feedparser.parse(rss_text)
            for entry in feed.entries:
                title = entry.get("title", "").strip()
                link = entry.get("link", "")
                summary = entry.get("summary", entry.get("description", ""))[:600]
                published = entry.get("published", "")

                if not title:
                    continue

                # Определяем источник по домену ссылки
                source_name = "UN Tajikistan"
                if "worldbank" in link:
                    source_name = "World Bank"
                elif "undp" in link:
                    source_name = "UNDP"
                elif "adb.org" in link:
                    source_name = "ADB"

                results.append({
                    "source": f"DGMarket ({source_name})",
                    "title": title,
                    "url": link,
                    "description": BeautifulSoup(summary, "lxml").get_text(strip=True) if summary else "",
                    "donor": source_name,
                    "tender_deadline": published[:10] if published else None,
                    "status": "Active",
                })

        except Exception as e:
            logger.error("[WorldBank] DGMarket RSS ошибка: %s", e)

        return results

    # ──────────────────────────────────────────────────────────────────────────
    # 4. WSIP-1 PMU — простой HTML сайт, парсится нормально
    # ──────────────────────────────────────────────────────────────────────────
    async def _scrape_wsip(self) -> list[dict]:
        """
        wsip-1.tj — прямой сайт PMU WSIP-1.
        Простой HTML без тяжёлого JS → BeautifulSoup работает.
        """
        urls = ["https://wsip-1.tj/", "https://wsip-1.tj/procurement/"]
        results = []

        for url in urls:
            html = await self.fetch(url)
            if not html:
                continue
            try:
                soup = BeautifulSoup(html, "lxml")
                # Ищем любые ссылки с ключевыми словами тендеров
                for a in soup.find_all("a", href=True):
                    text = a.get_text(strip=True)
                    href = a["href"]
                    if not text or len(text) < 10:
                        continue
                    kw = ["procurement", "tender", "bid", "закупк", "тендер",
                          "pipe", "труб", "water", "вода", "wsip", "rwssp"]
                    if any(k in text.lower() or k in href.lower() for k in kw):
                        full_url = href if href.startswith("http") else urljoin(url, href)
                        results.append({
                            "source": "WSIP-1 PMU",
                            "title": text,
                            "url": full_url,
                            "donor": "World Bank IDA",
                            "contact_email": "pmu@wsip-1.tj",
                            "contact_org": "MIDP / PMU WSIP-1",
                            "status": "Active",
                        })
            except Exception as e:
                logger.debug("[WorldBank] WSIP ошибка: %s", e)

        return results
