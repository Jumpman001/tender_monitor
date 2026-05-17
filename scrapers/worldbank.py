"""
WorldBank Scraper v3 — проверенная версия.

Источники:
- World Bank Projects → JSON API (search.worldbank.org/api/v2/projects)  ✅ РАБОТАЕТ
- World Bank STEP     → JSON API (search.worldbank.org/api/v2/procnotices) ✅ РАБОТАЕТ (2817 записей)
- wsip-1.tj           → прямой HTML парсинг
"""

from bs4 import BeautifulSoup
from urllib.parse import urljoin

from scrapers.base import BaseScraper
from utils.logger import logger


class WorldBankScraper(BaseScraper):

    def __init__(self):
        super().__init__("WorldBank")

    async def scrape(self) -> list[dict]:
        results = []

        # 1. World Bank Projects JSON API — 28 активных проектов TJ
        wb = await self._scrape_wb_api()
        results.extend(wb)
        logger.info("[WorldBank] WB Projects API: %d", len(wb))
        await self.delay()

        # 2. World Bank STEP Procurement JSON API — 2817 закупок TJ
        step = await self._scrape_step_api()
        results.extend(step)
        logger.info("[WorldBank] STEP API: %d", len(step))
        await self.delay()



        logger.info("[WorldBank] ИТОГО: %d", len(results))
        return results

    # ──────────────────────────────────────────────────────────────────────────
    # 1. WORLD BANK PROJECTS — JSON API
    # ──────────────────────────────────────────────────────────────────────────
    async def _scrape_wb_api(self) -> list[dict]:
        """
        Официальный JSON API World Bank Projects.
        Тестировано: 28 активных проектов для TJ.
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
            # projects — это dict: {project_id: project_data, ...}
            if isinstance(projects, dict):
                items = list(projects.values())
            elif isinstance(projects, list):
                items = projects
            else:
                items = []

            for proj in items:
                if not isinstance(proj, dict):
                    continue

                title = proj.get("project_name", "").strip()
                if not title:
                    continue

                wb_id = proj.get("id", "")
                closing = proj.get("closingdate", "")
                total_amt = proj.get("totalamt", 0)
                sector = proj.get("sector1", {})
                sector_name = sector.get("Name", "") if isinstance(sector, dict) else str(sector)

                budget_str = ""
                if total_amt:
                    try:
                        budget_str = f"$ {int(float(str(total_amt).replace(',', ''))):,}"
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
        Тестировано: 2817 закупок для TJ.
        Ключи записи: id, notice_type, noticedate, notice_status,
        submission_deadline_date, project_id, project_name,
        bid_reference_no, bid_description, contact_email, contact_name, etc.
        """
        api_url = (
            "https://search.worldbank.org/api/v2/procnotices"
            "?format=json"
            "&project_ctry_code=TJ"
            "&notice_status_exact=Published"
            "&rows=50&os=0"
        )
        results = []
        data = await self.fetch_json(api_url)
        if not data:
            # Fallback: другой параметр
            data = await self.fetch_json(
                "https://search.worldbank.org/api/v2/procnotices"
                "?format=json&countrycode=TJ&rows=50&os=0"
            )
        if not data:
            return results

        try:
            notices = data.get("procnotices", [])
            # API возвращает LIST, не dict!
            if isinstance(notices, dict):
                notices = list(notices.values())

            for notice in notices:
                if not isinstance(notice, dict):
                    continue

                # Правильные ключи из реального ответа API
                title = (
                    notice.get("bid_description", "")
                    or notice.get("project_name", "")
                ).strip()
                if not title:
                    continue

                proj_id = notice.get("project_id", "")
                bid_ref = notice.get("bid_reference_no", "")
                deadline = notice.get("submission_deadline_date", "")
                contact_email = notice.get("contact_email", "")
                contact_name = notice.get("contact_name", "")
                contact_org = notice.get("contact_organization", "")
                notice_id = notice.get("id", "")
                notice_type = notice.get("notice_type", "")
                project_name = notice.get("project_name", "")
                notice_text = notice.get("notice_text", "")[:1500]
                contact_address = notice.get("contact_address", "")
                contact_phone = notice.get("contact_phone_no", "")

                # Обогащаем description для AI — чем больше текста, тем лучше карточка
                desc_parts = [f"{notice_type}: {project_name}" if project_name else notice_type]
                if notice_text:
                    desc_parts.append(notice_text)
                if contact_address:
                    desc_parts.append(f"Address: {contact_address}")
                description = "\n".join(desc_parts)

                # URL: ссылка на страницу проекта с секцией procurement
                # (единственный рабочий формат — 200 OK, проверено)
                tender_url = (
                    f"https://projects.worldbank.org/en/projects-operations"
                    f"/project-detail/{proj_id}#procurement"
                ) if proj_id else (
                    "https://projects.worldbank.org/en/projects-operations"
                    "/procurement?countrycode_exact=TJ"
                )

                results.append({
                    "source": "World Bank STEP",
                    "title": title,
                    "url": tender_url,
                    "description": description,
                    "project_id": f"{proj_id} / {bid_ref}" if bid_ref else str(proj_id),
                    "donor": "World Bank IDA",
                    "tender_deadline": str(deadline)[:10] if deadline else None,
                    "contact_email": contact_email if contact_email else None,
                    "contact_phone": contact_phone if contact_phone else None,
                    "contact_name": f"{contact_name} ({contact_org})" if contact_org else contact_name or None,
                    "status": notice.get("notice_status", "Active"),
                    "region": "Tajikistan",
                })
        except Exception as e:
            logger.error("[WorldBank] Ошибка STEP API: %s", e)

        return results

    # ──────────────────────────────────────────────────────────────────────────

