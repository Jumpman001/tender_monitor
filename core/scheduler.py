"""
Scheduler — APScheduler расписание автоматических задач.
"""

from datetime import datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger

from aiogram import Bot

from config import SCAN_INTERVAL_HOURS
from database import db
from database.models import Tender, ScanLog
from core.filter import passes_filter, extract_pipe_diameter
from core.deduplicator import compute_hash
from core.ai_card import generate_ai_card, format_ai_card_markdown
from scrapers.worldbank import WorldBankScraper
from scrapers.adb import ADBScraper
from scrapers.ebrd import EBRDScraper
from scrapers.tenders_tj import TendersTJScraper
from scrapers.isdb import IsDBScraper
from scrapers.aiib import AIIBScraper
from scrapers.undp import UNDPScraper
from scrapers.giz import GIZScraper
from scrapers.sam_gov import SAMGovScraper
from scrapers.developmentaid import DevelopmentAidScraper
from scrapers.asiaplus import AsiaPlusScraper
from scrapers.secondary import SecondaryScraper
from bot.notifier import send_tender_notification, send_digest, send_deadline_reminder
from utils.logger import logger


async def run_full_scan(bot: Bot) -> None:
    """Полный скан всех источников — вызывается по расписанию или вручную."""
    logger.info("═══ НАЧАЛО ПОЛНОГО СКАНИРОВАНИЯ ═══")
    start_time = datetime.utcnow()

    all_scrapers = [
        # Приоритет 🔴 — основные источники
        WorldBankScraper(),
        ADBScraper(),
        EBRDScraper(),
        IsDBScraper(),
        AIIBScraper(),
        UNDPScraper(),
        # Приоритет 🟡 — дополнительные
        TendersTJScraper(),
        GIZScraper(),
        SAMGovScraper(),
        DevelopmentAidScraper(),
        # Приоритет 🟢 — мониторинг / сигналы
        AsiaPlusScraper(),
        SecondaryScraper(),
    ]

    total_found = 0
    total_new = 0
    errors_list = []

    for scraper in all_scrapers:
        source_name = scraper.source_name
        logger.info("─── Сканирование: %s ───", source_name)

        try:
            raw_tenders = await scraper.scrape()
            found_count = len(raw_tenders)
            new_count = 0

            for raw in raw_tenders:
                title = raw.get("title", "")
                description = raw.get("description", "")
                url = raw.get("url", "")
                source = raw.get("source", source_name)

                # Фильтрация
                if not passes_filter(title, description):
                    continue

                # Дедупликация
                hash_val = compute_hash(source, title, url)
                if await db.tender_exists(hash_val):
                    logger.debug("Дубликат: %s", title[:50])
                    continue

                # Создаём объект Tender
                pipe_diameter = extract_pipe_diameter(f"{title} {description}")

                tender = Tender(
                    hash=hash_val,
                    source=source,
                    title=title,
                    url=url,
                    description=description[:1000] if description else None,
                    project_id=raw.get("project_id"),
                    donor=raw.get("donor"),
                    contractor=raw.get("contractor"),
                    budget=raw.get("budget"),
                    pipe_diameter=pipe_diameter or raw.get("pipe_diameter"),
                    tender_deadline=raw.get("tender_deadline"),
                    contract_completion=raw.get("contract_completion"),
                    status=raw.get("status", "Unknown"),
                    contact_email=raw.get("contact_email"),
                    contact_phone=raw.get("contact_phone"),
                    contact_name=raw.get("contact_name"),
                    region=raw.get("region"),
                )

                # AI карточка (только для новых тендеров)
                ai_data = await generate_ai_card(
                    title=title,
                    description=description[:2000] if description else "",
                    source=source,
                    url=url,
                )

                if ai_data:
                    tender.ai_card = format_ai_card_markdown(ai_data)
                    # Обогащаем данные из AI
                    tender.pipe_diameter = ai_data.get("pipe_diameter") or tender.pipe_diameter
                    tender.pipe_type = ai_data.get("pipe_type")
                    tender.pipe_length_km = ai_data.get("pipe_length_km")
                    tender.contractor = ai_data.get("contractor") or tender.contractor
                    tender.contact_email = ai_data.get("contact_email") or tender.contact_email
                    tender.contact_phone = ai_data.get("contact_phone") or tender.contact_phone
                    tender.contact_name = ai_data.get("contact_name") or tender.contact_name
                    # Добавляем организацию и должность к имени контакта
                    contact_org = ai_data.get("contact_organization", "")
                    contact_pos = ai_data.get("contact_position", "")
                    if contact_org and tender.contact_name:
                        extra = ", ".join(filter(None, [contact_pos, contact_org]))
                        if extra:
                            tender.contact_name = f"{tender.contact_name} ({extra})"
                    tender.region = ai_data.get("region") or tender.region
                    tender.urgency = ai_data.get("urgency", "LOW")
                    tender.summary_ru = ai_data.get("summary_ru")
                    tender.status = ai_data.get("status") or tender.status

                # Сохраняем в БД
                inserted = await db.insert_tender(tender)
                if inserted:
                    new_count += 1
                    # Отправляем уведомление
                    sent = await send_tender_notification(bot, tender)
                    if sent:
                        await db.mark_notified(hash_val)

            total_found += found_count
            total_new += new_count

            # Логируем сканирование
            scan_log = ScanLog(
                scanned_at=datetime.utcnow().isoformat(),
                source=source_name,
                found_total=found_count,
                new_tenders=new_count,
            )
            await db.insert_scan_log(scan_log)

            logger.info(
                "[%s] Завершено: найдено %d, новых %d",
                source_name, found_count, new_count,
            )

        except Exception as e:
            error_msg = f"{source_name}: {str(e)}"
            errors_list.append(error_msg)
            logger.error("Ошибка сканирования %s: %s", source_name, str(e))

            # Логируем ошибку
            scan_log = ScanLog(
                scanned_at=datetime.utcnow().isoformat(),
                source=source_name,
                found_total=0,
                new_tenders=0,
                errors=str(e)[:500],
            )
            await db.insert_scan_log(scan_log)

        finally:
            await scraper.close()

    elapsed = (datetime.utcnow() - start_time).total_seconds()
    logger.info(
        "═══ СКАНИРОВАНИЕ ЗАВЕРШЕНО ═══ "
        "Время: %.1f сек | Найдено: %d | Новых: %d | Ошибок: %d",
        elapsed, total_found, total_new, len(errors_list),
    )

    # Отправляем итоговое сообщение в Telegram
    try:
        from config import TELEGRAM_CHAT_ID
        if TELEGRAM_CHAT_ID:
            summary = (
                f"✅ <b>Скан завершён</b> ({elapsed:.0f} сек)\n"
                f"📊 Найдено: {total_found} | Новых: {total_new}"
            )
            if errors_list:
                summary += f"\n⚠️ Ошибки: {len(errors_list)}"
            await bot.send_message(
                chat_id=TELEGRAM_CHAT_ID,
                text=summary,
                parse_mode="HTML",
            )
    except Exception as e:
        logger.error("Ошибка отправки итогового сообщения: %s", str(e))


async def check_deadlines(bot: Bot) -> None:
    """Проверяет тендеры с дедлайном < 7 дней и отправляет напоминания."""
    logger.info("Проверка скорых дедлайнов...")
    tenders = await db.get_tenders_with_deadline_soon(7)
    if tenders:
        await send_deadline_reminder(bot, tenders)
        logger.info("Отправлено %d напоминаний о дедлайнах", len(tenders))
    else:
        logger.info("Нет тендеров со скорым дедлайном")


async def send_weekly_digest(bot: Bot) -> None:
    """Отправляет еженедельный дайджест."""
    logger.info("Генерация еженедельного дайджеста...")
    report_data = await db.get_weekly_report_data()
    await send_digest(bot, report_data)


def setup_scheduler(bot: Bot) -> AsyncIOScheduler:
    """Настраивает и возвращает планировщик задач."""
    scheduler = AsyncIOScheduler(timezone="Asia/Dushanbe")

    # Каждые N часов: полный скан всех источников
    scheduler.add_job(
        run_full_scan,
        trigger=IntervalTrigger(hours=SCAN_INTERVAL_HOURS),
        args=[bot],
        id="full_scan",
        name="Полный скан источников",
        replace_existing=True,
    )

    # Каждое воскресенье 09:00: еженедельный дайджест
    scheduler.add_job(
        send_weekly_digest,
        trigger=CronTrigger(day_of_week="sun", hour=9, minute=0),
        args=[bot],
        id="weekly_digest",
        name="Еженедельный дайджест",
        replace_existing=True,
    )

    # Каждый день 08:00: проверка дедлайнов < 7 дней
    scheduler.add_job(
        check_deadlines,
        trigger=CronTrigger(hour=8, minute=0),
        args=[bot],
        id="deadline_check",
        name="Проверка дедлайнов",
        replace_existing=True,
    )

    logger.info(
        "Планировщик настроен: скан каждые %dч, дайджест — вс 09:00, "
        "дедлайны — ежедневно 08:00",
        SCAN_INTERVAL_HOURS,
    )

    return scheduler
