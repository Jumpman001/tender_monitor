"""
SAM.gov Scraper v2 — проверенная версия.

Тестировано:
- sam.gov/api/prod/sgs/v1/search/ ✅ 200 (JSON с _embedded.results)
"""

from urllib.parse import quote

from scrapers.base import BaseScraper
from utils.logger import logger


class SAMGovScraper(BaseScraper):

    def __init__(self):
        super().__init__("SAM.gov")

    async def scrape(self) -> list[dict]:
        results = []

        search_queries = [
            "tajikistan water",
            "tajikistan irrigation",
            "tajikistan pipeline",
        ]

        seen_ids = set()

        for query in search_queries:
            # Рабочий API endpoint (проверено)
            api_url = (
                f"https://sam.gov/api/prod/sgs/v1/search/"
                f"?index=opp&q={quote(query)}&page=0&size=25"
            )

            data = await self.fetch_json(api_url)
            if not data:
                logger.warning("[SAM.gov] API не ответил для '%s'", query)
                await self.delay()
                continue

            try:
                embedded = data.get("_embedded", {})
                items = embedded.get("results", [])

                for item in items:
                    try:
                        # SAM.gov вкладывает данные в _source
                        source_data = item.get("_source", item)

                        title = source_data.get("title", "")
                        if not title:
                            title = source_data.get("solicitationNumber", "")
                        if not title:
                            continue

                        notice_id = source_data.get("noticeId", source_data.get("_id", ""))
                        if notice_id in seen_ids:
                            continue
                        seen_ids.add(notice_id)

                        sol_number = source_data.get("solicitationNumber", "")
                        department = source_data.get("department", source_data.get("organizationName", ""))
                        description = source_data.get("description", "")[:500]
                        deadline = source_data.get("responseDeadLine", source_data.get("responseDateStr", ""))
                        status = source_data.get("uiLink", {}).get("status", "Active") if isinstance(source_data.get("uiLink"), dict) else "Active"

                        url = f"https://sam.gov/opp/{notice_id}/view" if notice_id else "https://sam.gov"

                        results.append({
                            "source": "SAM.gov",
                            "title": title,
                            "url": url,
                            "description": description,
                            "project_id": sol_number,
                            "donor": f"US Government ({department})" if department else "US Government / USAID",
                            "tender_deadline": str(deadline)[:10] if deadline else None,
                            "status": "Active",
                        })
                    except Exception as e:
                        logger.debug("[SAM.gov] Item error: %s", str(e))
                        continue

                logger.info("[SAM.gov] '%s': %d results", query, len(items))

            except Exception as e:
                logger.error("[SAM.gov] Parse error: %s", str(e))

            await self.delay()

        logger.info("[SAM.gov] Всего: %d", len(results))
        return results
