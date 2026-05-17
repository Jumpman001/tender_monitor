"""
WorldBank Scraper — парсинг трёх источников:
1. tajikistan.un.org (UN Procurement)
2. World Bank Projects (Tajikistan)
3. World Bank STEP Procurement Notices
"""

from bs4 import BeautifulSoup
from urllib.parse import urljoin

from scrapers.base import BaseScraper
from utils.logger import logger


class WorldBankScraper(BaseScraper):
    """Скрапер для World Bank, UN Tajikistan и связанных источников."""

    def __init__(self):
        super().__init__("WorldBank")

    async def scrape(self) -> list[dict]:
        """Парсит все три источника World Bank."""
        results = []

        # Источник 1: UN Tajikistan Procurement
        un_results = await self._scrape_un_tajikistan()
        results.extend(un_results)

        await self.delay()

        # Источник 2: World Bank Projects
        wb_results = await self._scrape_wb_projects()
        results.extend(wb_results)

        await self.delay()

        # Источник 3: STEP Procurement
        step_results = await self._scrape_step_procurement()
        results.extend(step_results)

        logger.info("[WorldBank] Всего найдено: %d тендеров", len(results))
        return results

    async def _scrape_un_tajikistan(self) -> list[dict]:
        """Парсит tajikistan.un.org/en/jobs."""
        url = "https://tajikistan.un.org/en/jobs"
        results = []

        html = await self.fetch(url)
        if not html:
            logger.warning("[WorldBank] Не удалось загрузить UN Tajikistan")
            return results

        try:
            soup = BeautifulSoup(html, "lxml")

            # Ищем карточки тендеров / вакансий
            articles = soup.select("article, .views-row, .node--type-job, .card")

            for article in articles:
                try:
                    # Извлекаем заголовок
                    title_el = article.select_one("h2 a, h3 a, .card-title a, .field--name-title a")
                    if not title_el:
                        title_el = article.select_one("a[href]")

                    if not title_el:
                        continue

                    title = title_el.get_text(strip=True)
                    link = title_el.get("href", "")
                    if link and not link.startswith("http"):
                        link = urljoin("https://tajikistan.un.org", link)

                    # Дата
                    date_el = article.select_one(
                        ".date-display-single, .datetime, time, .field--name-field-date"
                    )
                    deadline = date_el.get_text(strip=True) if date_el else None

                    # Описание
                    desc_el = article.select_one(
                        ".field--name-body, .summary, .teaser, p"
                    )
                    description = desc_el.get_text(strip=True)[:500] if desc_el else ""

                    results.append({
                        "source": "UN Tajikistan",
                        "title": title,
                        "url": link,
                        "description": description,
                        "tender_deadline": deadline,
                        "donor": "United Nations",
                        "status": "Active",
                    })
                except Exception as e:
                    logger.debug("[WorldBank] Ошибка парсинга UN карточки: %s", str(e))
                    continue

            logger.info("[WorldBank] UN Tajikistan: найдено %d", len(results))

        except Exception as e:
            logger.error("[WorldBank] Ошибка парсинга UN Tajikistan: %s", str(e))

        return results

    async def _scrape_wb_projects(self) -> list[dict]:
        """Парсит World Bank Projects — список активных проектов Таджикистана."""
        # World Bank projects API
        api_url = (
            "https://search.worldbank.org/api/v2/projects?"
            "format=json&countrycode_exact=TJ&status_exact=Active"
            "&fl=id,project_name,countryname,status,boardapprovaldate,"
            "closingdate,totalamt,sector1,mjtheme1nam"
            "&rows=50&os=0"
        )
        results = []

        data = await self.fetch_json(api_url)
        if not data:
            # Fallback: парсим HTML страницу
            return await self._scrape_wb_projects_html()

        try:
            projects = data.get("projects", {})
            for proj_id, proj in projects.items():
                if isinstance(proj, dict):
                    title = proj.get("project_name", "")
                    wb_id = proj.get("id", proj_id)
                    status = proj.get("status", "Active")
                    total_amt = proj.get("totalamt", "")
                    closing_date = proj.get("closingdate", "")
                    sector = proj.get("sector1", {})
                    sector_name = sector.get("Name", "") if isinstance(sector, dict) else str(sector)

                    detail_url = f"https://projects.worldbank.org/en/projects-operations/project-detail/{wb_id}"

                    budget_str = ""
                    if total_amt:
                        try:
                            budget_str = f"$ {int(float(total_amt)):,}"
                        except (ValueError, TypeError):
                            budget_str = str(total_amt)

                    results.append({
                        "source": "World Bank",
                        "title": title,
                        "url": detail_url,
                        "description": f"Sector: {sector_name}",
                        "project_id": wb_id,
                        "donor": "World Bank IDA",
                        "budget": budget_str,
                        "contract_completion": closing_date[:10] if closing_date else None,
                        "status": status,
                    })

            logger.info("[WorldBank] WB Projects API: найдено %d", len(results))

        except Exception as e:
            logger.error("[WorldBank] Ошибка парсинга WB API: %s", str(e))

        return results

    async def _scrape_wb_projects_html(self) -> list[dict]:
        """Fallback: парсит HTML страницу World Bank Projects."""
        url = "https://projects.worldbank.org/en/projects-operations/projects-list?countrycode_exact=TJ&os=0"
        results = []

        html = await self.fetch(url)
        if not html:
            return results

        try:
            soup = BeautifulSoup(html, "lxml")
            rows = soup.select(".proj-list-row, .projects-list .row, tr[data-project]")

            for row in rows:
                try:
                    title_el = row.select_one("a")
                    if not title_el:
                        continue
                    title = title_el.get_text(strip=True)
                    link = title_el.get("href", "")
                    if link and not link.startswith("http"):
                        link = urljoin("https://projects.worldbank.org", link)

                    results.append({
                        "source": "World Bank",
                        "title": title,
                        "url": link,
                        "donor": "World Bank IDA",
                        "status": "Active",
                    })
                except Exception:
                    continue

            logger.info("[WorldBank] WB Projects HTML: найдено %d", len(results))
        except Exception as e:
            logger.error("[WorldBank] Ошибка парсинга WB HTML: %s", str(e))

        return results

    async def _scrape_step_procurement(self) -> list[dict]:
        """Парсит World Bank STEP Procurement Notices."""
        # STEP API / HTML
        url = (
            "https://projects.worldbank.org/en/projects-operations/procurement/"
            "noticesearch?OP_LANG=EN&searchStr=tajikistan&project_ctry_code=TJ"
        )
        results = []

        html = await self.fetch(url)
        if not html:
            logger.warning("[WorldBank] Не удалось загрузить STEP Procurement")
            return results

        try:
            soup = BeautifulSoup(html, "lxml")

            # Ищем строки таблицы или карточки закупок
            rows = soup.select(
                "table tbody tr, .procurement-row, .notice-item, "
                ".search-result-item, .procurement-notice"
            )

            for row in rows:
                try:
                    cells = row.select("td")
                    if len(cells) >= 3:
                        title = cells[0].get_text(strip=True)
                        link_el = cells[0].select_one("a")
                        link = ""
                        if link_el:
                            link = link_el.get("href", "")
                            if link and not link.startswith("http"):
                                link = urljoin("https://projects.worldbank.org", link)

                        project_id = cells[1].get_text(strip=True) if len(cells) > 1 else ""
                        deadline = cells[-1].get_text(strip=True) if cells else ""

                        if title:
                            results.append({
                                "source": "World Bank STEP",
                                "title": title,
                                "url": link or url,
                                "project_id": project_id,
                                "tender_deadline": deadline,
                                "donor": "World Bank IDA",
                                "status": "Active",
                            })
                    else:
                        # Попробуем как карточку
                        title_el = row.select_one("a, h3, h4, .title")
                        if title_el:
                            title = title_el.get_text(strip=True)
                            link = title_el.get("href", "")
                            if link and not link.startswith("http"):
                                link = urljoin("https://projects.worldbank.org", link)
                            results.append({
                                "source": "World Bank STEP",
                                "title": title,
                                "url": link or url,
                                "donor": "World Bank IDA",
                                "status": "Active",
                            })
                except Exception:
                    continue

            logger.info("[WorldBank] STEP Procurement: найдено %d", len(results))

        except Exception as e:
            logger.error("[WorldBank] Ошибка парсинга STEP: %s", str(e))

        return results
