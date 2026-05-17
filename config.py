"""
Конфигурация проекта — все настройки из .env файла.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Загружаем .env
load_dotenv()

# ─── Telegram ────────────────────────────────────────────────
TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID: str = os.getenv("TELEGRAM_CHAT_ID", "")

# ─── Gemini ──────────────────────────────────────────────────
GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
GEMINI_MAX_TOKENS: int = 600

# ─── Настройки сканера ───────────────────────────────────────
SCAN_INTERVAL_HOURS: int = int(os.getenv("SCAN_INTERVAL_HOURS", "12"))
MIN_PIPE_DIAMETER_MM: int = int(os.getenv("MIN_PIPE_DIAMETER_MM", "400"))
REQUEST_TIMEOUT_SEC: int = int(os.getenv("REQUEST_TIMEOUT_SEC", "30"))
REQUEST_DELAY_SEC: int = int(os.getenv("REQUEST_DELAY_SEC", "2"))
MAX_RETRIES: int = 3
RETRY_BACKOFF_BASE: int = 2  # секунды (2, 4, 8)

# ─── База данных ─────────────────────────────────────────────
DB_PATH: str = os.getenv("DB_PATH", "./data/tenders.db")

# ─── Логирование ─────────────────────────────────────────────
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
LOG_FILE: str = os.getenv("LOG_FILE", "./logs/monitor.log")

# ─── Создаём директории если не существуют ───────────────────
Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
Path(LOG_FILE).parent.mkdir(parents=True, exist_ok=True)

# ─── Источники для сканирования ──────────────────────────────
SOURCES = [
    {
        "name": "UN Tajikistan Procurement",
        "url": "https://tajikistan.un.org/en/jobs",
        "scraper": "WorldBankScraper",
        "priority": 1,
    },
    {
        "name": "World Bank Projects TJ",
        "url": "https://projects.worldbank.org/en/projects-operations/projects-list?countrycode_exact=TJ&os=0",
        "scraper": "WorldBankScraper",
        "priority": 1,
    },
    {
        "name": "World Bank STEP Procurement",
        "url": "https://projects.worldbank.org/en/projects-operations/procurement/noticesearch?OP_LANG=EN&searchStr=tajikistan&project_ctry_code=TJ",
        "scraper": "WorldBankScraper",
        "priority": 1,
    },
    {
        "name": "ADB Tajikistan Tenders",
        "url": "https://www.adb.org/projects/tenders?country=TAJ&status=Active",
        "scraper": "ADBScraper",
        "priority": 1,
    },
    {
        "name": "EBRD Procurement Tajikistan",
        "url": "https://www.ebrd.com/work-with-us/procurement/project-procurement-notices.html?1=1&filterCountry=Tajikistan",
        "scraper": "EBRDScraper",
        "priority": 2,
    },
    {
        "name": "tenders.tj",
        "url": "https://tenders.tj/",
        "scraper": "TendersTJScraper",
        "priority": 2,
    },
    {
        "name": "WSIP-1 PMU Direct",
        "url": "https://wsip-1.tj/",
        "scraper": "WorldBankScraper",
        "priority": 1,
    },
    {
        "name": "mewr.tj (МЭВР)",
        "url": "https://www.mewr.tj/",
        "scraper": "WorldBankScraper",
        "priority": 3,
    },
    # ─── Новые приоритетные источники (🔴) ───────────────────
    {
        "name": "IsDB Procurement",
        "url": "https://www.isdb.org/procurement",
        "scraper": "IsDBScraper",
        "priority": 1,
    },
    {
        "name": "AIIB Procurement",
        "url": "https://www.aiib.org/en/opportunities/business/procurement-notices/index.html",
        "scraper": "AIIBScraper",
        "priority": 1,
    },
    {
        "name": "UNDP Procurement Tajikistan",
        "url": "https://procurement-notices.undp.org/view_notices.cfm?Country=TJK",
        "scraper": "UNDPScraper",
        "priority": 1,
    },
    {
        "name": "GIZ Tenders",
        "url": "https://www.giz.de/en/workingwithgiz/tenders.html",
        "scraper": "GIZScraper",
        "priority": 2,
    },
    {
        "name": "SAM.gov (USAID)",
        "url": "https://sam.gov/search/?index=opp&q=tajikistan+water",
        "scraper": "SAMGovScraper",
        "priority": 2,
    },
    {
        "name": "DevelopmentAid.org",
        "url": "https://www.developmentaid.org/tenders/search?country=Tajikistan",
        "scraper": "DevelopmentAidScraper",
        "priority": 2,
    },
    # ─── Новостной сигнал (ранний мониторинг) ────────────────
    {
        "name": "AsiaPlus (новости TJ)",
        "url": "https://asiaplustj.info/ru",
        "scraper": "AsiaPlusScraper",
        "priority": 3,
    },
    # ─── Вторичные источники (🟡 мониторинг) ─────────────────
    {
        "name": "EIB (European Investment Bank)",
        "url": "https://www.eib.org/en/projects/pipelines/all/index.htm?q=tajikistan",
        "scraper": "SecondaryScraper",
        "priority": 3,
    },
    {
        "name": "EDB/EFSD (Eurasian Development Bank)",
        "url": "https://eabr.org/en/projects/?country=Tajikistan",
        "scraper": "SecondaryScraper",
        "priority": 3,
    },
    {
        "name": "KfW Development Bank",
        "url": "https://www.kfw-entwicklungsbank.de/International-financing/KfW-Development-Bank/Projects/Project-database/?q=tajikistan+water",
        "scraper": "SecondaryScraper",
        "priority": 3,
    },
    {
        "name": "OPEC Fund",
        "url": "https://opecfund.org/operations?country=Tajikistan",
        "scraper": "SecondaryScraper",
        "priority": 3,
    },
    {
        "name": "FAO Procurement",
        "url": "https://www.fao.org/procurement/general-information/en/",
        "scraper": "SecondaryScraper",
        "priority": 3,
    },
    {
        "name": "dgMarket",
        "url": "https://www.dgmarket.com/tenders/np-notice.do?noticeType=PROCUREMENT&country=TJ",
        "scraper": "SecondaryScraper",
        "priority": 3,
    },
]

# ─── Ключевые проекты для отдельного мониторинга ─────────────
WATCH_PROJECTS = [
    {
        "name": "WSIP-1",
        "id": "P177325",
        "pmu_email": "pmu@wsip-1.tj",
        "url": "https://projects.worldbank.org/en/projects-operations/project-detail/P177325",
        "watch_lots": ["RWSSP-NCB-W/016"],
    },
    {
        "name": "RWSSP",
        "id": "P162637",
        "pmu_email": "pmu@wsip-1.tj",
        "url": "https://projects.worldbank.org/en/projects-operations/project-detail/P162637",
    },
    {
        "name": "ADB Vaksh Basin Irrigation",
        "id": "53109",
        "url": "https://www.adb.org/projects/53109-002/main",
    },
    {
        "name": "EBRD Yavan Water Supply",
        "url": "https://www.ebrd.com/where-we-are/tajikistan/overview.html",
    },
    {
        "name": "WSIP-2 (SOP-2) — следить за появлением PID",
        "url": "https://projects.worldbank.org/en/projects-operations/projects-list?countrycode_exact=TJ&mjthemecode=WA",
    },
]
