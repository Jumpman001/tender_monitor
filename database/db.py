"""
Инициализация SQLite базы данных и CRUD-операции.
"""

import aiosqlite
from typing import Optional

from config import DB_PATH
from database.models import Tender, ScanLog
from utils.logger import logger


async def init_db() -> None:
    """Создаёт таблицы если не существуют."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS tenders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                hash TEXT UNIQUE NOT NULL,
                source TEXT NOT NULL,
                title TEXT NOT NULL,
                description TEXT,
                project_id TEXT,
                donor TEXT,
                contractor TEXT,
                budget TEXT,
                pipe_diameter TEXT,
                tender_deadline TEXT,
                contract_completion TEXT,
                status TEXT,
                contact_email TEXT,
                contact_phone TEXT,
                contact_name TEXT,
                url TEXT NOT NULL,
                region TEXT,
                ai_card TEXT,
                first_seen TEXT NOT NULL,
                last_updated TEXT NOT NULL,
                notified INTEGER DEFAULT 0
            );
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS scan_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                scanned_at TEXT NOT NULL,
                source TEXT NOT NULL,
                found_total INTEGER,
                new_tenders INTEGER,
                errors TEXT
            );
        """)
        await db.commit()
    logger.info("База данных инициализирована: %s", DB_PATH)


async def tender_exists(hash_value: str) -> bool:
    """Проверяет существует ли тендер с данным хэшем."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT 1 FROM tenders WHERE hash = ?", (hash_value,)
        )
        row = await cursor.fetchone()
        return row is not None


async def insert_tender(tender: Tender) -> bool:
    """Вставляет тендер в БД. Возвращает True если вставлен, False если дубликат."""
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                """
                INSERT INTO tenders (
                    hash, source, title, description, project_id, donor,
                    contractor, budget, pipe_diameter, tender_deadline,
                    contract_completion, status, contact_email, contact_phone,
                    contact_name, url, region, ai_card, first_seen,
                    last_updated, notified
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                tender.to_db_tuple(),
            )
            await db.commit()
            logger.info("Новый тендер сохранён: %s", tender.title[:80])
            return True
    except aiosqlite.IntegrityError:
        logger.debug("Дубликат тендера (hash): %s", tender.hash[:16])
        return False


async def update_tender_ai_card(hash_value: str, ai_card: str) -> None:
    """Обновляет AI-карточку тендера."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE tenders SET ai_card = ?, last_updated = datetime('now') WHERE hash = ?",
            (ai_card, hash_value),
        )
        await db.commit()


async def mark_notified(hash_value: str) -> None:
    """Помечает тендер как уведомлённый."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE tenders SET notified = 1 WHERE hash = ?", (hash_value,)
        )
        await db.commit()


async def get_unnotified_tenders() -> list[Tender]:
    """Возвращает все тендеры, по которым не было уведомлений."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM tenders WHERE notified = 0 ORDER BY first_seen DESC"
        )
        rows = await cursor.fetchall()
        return [Tender.from_db_row(dict(row)) for row in rows]


async def get_recent_tenders(limit: int = 10) -> list[Tender]:
    """Возвращает последние N тендеров."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM tenders ORDER BY first_seen DESC LIMIT ?", (limit,)
        )
        rows = await cursor.fetchall()
        return [Tender.from_db_row(dict(row)) for row in rows]


async def get_active_tenders() -> list[Tender]:
    """Возвращает тендеры со статусом Active."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM tenders WHERE status = 'Active' ORDER BY first_seen DESC"
        )
        rows = await cursor.fetchall()
        return [Tender.from_db_row(dict(row)) for row in rows]


async def search_tenders(query: str) -> list[Tender]:
    """Поиск тендеров по title и description."""
    pattern = f"%{query}%"
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """SELECT * FROM tenders
               WHERE title LIKE ? OR description LIKE ?
               ORDER BY first_seen DESC LIMIT 20""",
            (pattern, pattern),
        )
        rows = await cursor.fetchall()
        return [Tender.from_db_row(dict(row)) for row in rows]


async def get_tender_count() -> int:
    """Возвращает общее количество тендеров."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("SELECT COUNT(*) FROM tenders")
        row = await cursor.fetchone()
        return row[0] if row else 0


async def get_last_scan() -> Optional[ScanLog]:
    """Возвращает последнюю запись лога сканирования."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM scan_log ORDER BY scanned_at DESC LIMIT 1"
        )
        row = await cursor.fetchone()
        if row:
            row_dict = dict(row)
            return ScanLog(
                id=row_dict.get("id"),
                scanned_at=row_dict["scanned_at"],
                source=row_dict["source"],
                found_total=row_dict.get("found_total", 0),
                new_tenders=row_dict.get("new_tenders", 0),
                errors=row_dict.get("errors"),
            )
        return None


async def insert_scan_log(scan: ScanLog) -> None:
    """Записывает лог сканирования."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """INSERT INTO scan_log (scanned_at, source, found_total, new_tenders, errors)
               VALUES (?, ?, ?, ?, ?)""",
            (scan.scanned_at, scan.source, scan.found_total, scan.new_tenders, scan.errors),
        )
        await db.commit()


async def get_tenders_with_deadline_soon(days: int = 7) -> list[Tender]:
    """Возвращает тендеры с дедлайном менее N дней."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """SELECT * FROM tenders
               WHERE tender_deadline IS NOT NULL
                 AND tender_deadline != ''
                 AND date(tender_deadline) <= date('now', '+' || ? || ' days')
                 AND date(tender_deadline) >= date('now')
                 AND status = 'Active'
               ORDER BY tender_deadline ASC""",
            (days,),
        )
        rows = await cursor.fetchall()
        return [Tender.from_db_row(dict(row)) for row in rows]


async def get_weekly_report_data() -> dict:
    """Возвращает данные для еженедельного дайджеста."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row

        # Новые за неделю
        cursor = await db.execute(
            """SELECT * FROM tenders
               WHERE date(first_seen) >= date('now', '-7 days')
               ORDER BY first_seen DESC"""
        )
        new_rows = await cursor.fetchall()

        # Активные
        cursor2 = await db.execute(
            "SELECT COUNT(*) FROM tenders WHERE status = 'Active'"
        )
        active_count = (await cursor2.fetchone())[0]

        # Всего
        cursor3 = await db.execute("SELECT COUNT(*) FROM tenders")
        total_count = (await cursor3.fetchone())[0]

        return {
            "new_tenders": [Tender.from_db_row(dict(r)) for r in new_rows],
            "active_count": active_count,
            "total_count": total_count,
        }
