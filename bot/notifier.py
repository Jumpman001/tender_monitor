"""
Notifier — форматирование и отправка уведомлений о проектах в Telegram.
Фокус: водоснабжение, ирригация, канализация, замена труб в Таджикистане.
"""

from datetime import datetime, timedelta
from typing import Optional

from aiogram import Bot
from aiogram.enums import ParseMode

from config import TELEGRAM_CHAT_ID
from database.models import Tender
from bot.keyboards import tender_keyboard
from utils.logger import logger


def _determine_urgency(tender: Tender) -> str:
    """Определяет уровень срочности."""
    # 🔴 HIGH — дедлайн менее 14 дней или статус Active + бюджет > $5 млн
    if tender.tender_deadline:
        try:
            deadline = None
            for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d.%m.%Y", "%B %d, %Y", "%d %B %Y"):
                try:
                    deadline = datetime.strptime(tender.tender_deadline.strip(), fmt)
                    break
                except ValueError:
                    continue

            if deadline:
                days_left = (deadline - datetime.utcnow()).days
                if days_left < 14:
                    return "HIGH"
                elif days_left <= 60:
                    return "MEDIUM"
        except Exception:
            pass

    # Бюджет > $5 млн и Active
    if tender.status == "Active" and tender.budget:
        try:
            import re
            budget_str = tender.budget.replace(",", "").replace(" ", "")
            numbers = re.findall(r"[\d]+(?:\.[\d]+)?", budget_str)
            if numbers:
                amount = float(numbers[0])
                if "млн" in tender.budget.lower() or "million" in tender.budget.lower():
                    amount *= 1_000_000
                if amount > 5_000_000:
                    return "HIGH"
        except Exception:
            pass

    if tender.status == "Active":
        return "MEDIUM"

    return "LOW"


def _urgency_emoji(urgency: str) -> str:
    """Эмодзи для уровня срочности."""
    return {"HIGH": "🔴", "MEDIUM": "🟡", "LOW": "🟢"}.get(urgency, "⚪")


def _stage_from_status(tender: Tender) -> str:
    """Определяет стадию проекта по имеющимся данным."""
    status = (tender.status or "").lower()

    if status in ("completed", "closed", "завершён"):
        return "✅ Завершён"
    elif status == "signed":
        return "🔴 Контракт подписан"
    elif status == "active":
        if tender.tender_deadline:
            return "🟡 Тендер объявлен"
        return "🏗 В реализации"
    elif status == "planned":
        return "🔵 Подготовка"
    elif status == "cancelled":
        return "❌ Отменён"
    else:
        return f"📊 {tender.status}" if tender.status else "📊 Не определён"


def format_tender_message(tender: Tender) -> str:
    """Форматирует уведомление о проекте для Telegram."""
    urgency = tender.urgency if tender.urgency != "LOW" else _determine_urgency(tender)
    emoji = _urgency_emoji(urgency)
    stage = _stage_from_status(tender)

    # ═══ ЗАГОЛОВОК ═══
    lines = [
        f"{emoji} <b>НОВЫЙ ПРОЕКТ</b>",
        "━━━━━━━━━━━━━━━━━━━━━",
    ]

    # Источник и ID
    project_part = f"📌 {tender.project_id} | " if tender.project_id else "📌 "
    lines.append(f"{project_part}<b>{tender.source}</b>")
    lines.append(f"🏗 <b>{tender.title}</b>")
    lines.append("")

    # ═══ СТАДИЯ ПРОЕКТА ═══
    lines.append(f"📊 <b>Стадия:</b> {stage}")

    # Дедлайн с оставшимися днями
    if tender.tender_deadline:
        days_info = ""
        try:
            for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d.%m.%Y", "%B %d, %Y"):
                try:
                    dl = datetime.strptime(tender.tender_deadline.strip(), fmt)
                    days_left = (dl - datetime.utcnow()).days
                    if days_left > 0:
                        days_info = f" (<b>{days_left} дней</b>)"
                    elif days_left == 0:
                        days_info = " (<b>СЕГОДНЯ!</b>)"
                    else:
                        days_info = " (истёк)"
                    break
                except ValueError:
                    continue
        except Exception:
            pass
        lines.append(f"📅 <b>Дедлайн подачи:</b> {tender.tender_deadline}{days_info}")

    if tender.contract_completion:
        lines.append(f"🏁 <b>Завершение:</b> {tender.contract_completion}")

    lines.append("")

    # ═══ ФИНАНСЫ ═══
    if tender.budget or tender.donor:
        if tender.budget:
            lines.append(f"💰 <b>Бюджет:</b> {tender.budget}")
        if tender.donor:
            lines.append(f"🏦 <b>Донор:</b> {tender.donor}")
        lines.append("")

    # ═══ ТРУБЫ ═══
    pipe_info = []
    if tender.pipe_diameter:
        pipe_info.append(f"⌀ {tender.pipe_diameter}")
    if tender.pipe_type:
        pipe_info.append(tender.pipe_type)
    if pipe_info:
        lines.append(f"🔩 <b>Трубы:</b> {' | '.join(pipe_info)}")
    if tender.pipe_length_km:
        lines.append(f"📏 <b>Протяжённость:</b> {tender.pipe_length_km} км")
    if pipe_info or tender.pipe_length_km:
        lines.append("")

    # ═══ РЕГИОН И ПОДРЯДЧИК ═══
    if tender.region:
        lines.append(f"📍 <b>Регион:</b> {tender.region}")
    if tender.contractor:
        lines.append(f"🔨 <b>Подрядчик:</b> {tender.contractor}")
    if tender.region or tender.contractor:
        lines.append("")

    # ═══ КОНТАКТЫ ═══
    has_contacts = tender.contact_name or tender.contact_email or tender.contact_phone
    if has_contacts:
        lines.append("📞 <b>КОНТАКТЫ:</b>")
        if tender.contact_name:
            lines.append(f"   👤 {tender.contact_name}")
        if tender.contact_email:
            lines.append(f"   📧 {tender.contact_email}")
        if tender.contact_phone:
            lines.append(f"   📱 {tender.contact_phone}")
        lines.append("")

    # ═══ AI АНАЛИТИКА ═══
    if tender.summary_ru:
        lines.append(f"📝 <i>{tender.summary_ru}</i>")
        lines.append("")

    # ═══ ССЫЛКА ═══
    lines.append(f"🔗 <a href=\"{tender.url}\">Открыть проект →</a>")
    lines.append("━━━━━━━━━━━━━━━━━━━━━")
    lines.append(f"⏱ {tender.first_seen[:16] if tender.first_seen else 'сейчас'}")

    return "\n".join(lines)


async def send_tender_notification(bot: Bot, tender: Tender) -> bool:
    """Отправляет уведомление о проекте в Telegram."""
    if not TELEGRAM_CHAT_ID:
        logger.warning("[Notifier] TELEGRAM_CHAT_ID не установлен")
        return False

    try:
        message_text = format_tender_message(tender)
        keyboard = tender_keyboard(tender.url, tender.hash)

        await bot.send_message(
            chat_id=TELEGRAM_CHAT_ID,
            text=message_text,
            parse_mode=ParseMode.HTML,
            reply_markup=keyboard,
            disable_web_page_preview=True,
        )
        logger.info("[Notifier] Уведомление отправлено: %s", tender.title[:60])
        return True
    except Exception as e:
        logger.error("[Notifier] Ошибка отправки уведомления: %s", str(e))
        return False


async def send_digest(bot: Bot, report_data: dict) -> bool:
    """Отправляет еженедельный дайджест."""
    if not TELEGRAM_CHAT_ID:
        return False

    try:
        new_tenders: list[Tender] = report_data.get("new_tenders", [])
        active_count = report_data.get("active_count", 0)
        total_count = report_data.get("total_count", 0)

        lines = [
            "📊 <b>ЕЖЕНЕДЕЛЬНЫЙ ДАЙДЖЕСТ — ПРОЕКТЫ ВОДОСНАБЖЕНИЯ ТДЖ</b>",
            "━━━━━━━━━━━━━━━━━━━━━",
            f"📅 {(datetime.utcnow() - timedelta(days=7)).strftime('%d.%m')} — {datetime.utcnow().strftime('%d.%m.%Y')}",
            "",
            f"🆕 Новых проектов: <b>{len(new_tenders)}</b>",
            f"🟡 С активным тендером: <b>{active_count}</b>",
            f"📦 Всего в базе: <b>{total_count}</b>",
            "",
        ]

        if new_tenders:
            lines.append("<b>Новые проекты:</b>")
            lines.append("")
            for i, t in enumerate(new_tenders[:15], 1):
                urgency = _determine_urgency(t)
                emoji = _urgency_emoji(urgency)
                stage = _stage_from_status(t)
                budget_str = f" | {t.budget}" if t.budget else ""
                lines.append(
                    f"{emoji} {i}. <a href=\"{t.url}\">{t.title[:55]}</a>"
                )
                lines.append(f"     {stage}{budget_str}")
            if len(new_tenders) > 15:
                lines.append(f"... и ещё {len(new_tenders) - 15} проектов")
        else:
            lines.append("ℹ️ Новых проектов не обнаружено.")

        lines.append("")
        lines.append("━━━━━━━━━━━━━━━━━━━━━")

        await bot.send_message(
            chat_id=TELEGRAM_CHAT_ID,
            text="\n".join(lines),
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True,
        )
        logger.info("[Notifier] Еженедельный дайджест отправлен")
        return True
    except Exception as e:
        logger.error("[Notifier] Ошибка отправки дайджеста: %s", str(e))
        return False


async def send_deadline_reminder(bot: Bot, tenders: list[Tender]) -> bool:
    """Отправляет напоминания о проектах с дедлайном < 7 дней."""
    if not TELEGRAM_CHAT_ID or not tenders:
        return False

    try:
        lines = [
            "⚠️ <b>СКОРЫЕ ДЕДЛАЙНЫ — ДЕЙСТВУЙТЕ!</b>",
            "━━━━━━━━━━━━━━━━━━━━━",
            "",
        ]

        for t in tenders:
            days_info = ""
            try:
                for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d.%m.%Y"):
                    try:
                        dl = datetime.strptime(t.tender_deadline.strip(), fmt)
                        days_left = (dl - datetime.utcnow()).days
                        days_info = f" ({days_left} дн.)" if days_left > 0 else " (СЕГОДНЯ!)"
                        break
                    except ValueError:
                        continue
            except Exception:
                pass

            lines.append(f"🔴 <a href=\"{t.url}\">{t.title[:55]}</a>")
            lines.append(f"   📅 Дедлайн: <b>{t.tender_deadline}</b>{days_info}")
            if t.budget:
                lines.append(f"   💰 {t.budget}")
            if t.contact_email:
                lines.append(f"   📧 {t.contact_email}")
            lines.append("")

        lines.append("━━━━━━━━━━━━━━━━━━━━━")

        await bot.send_message(
            chat_id=TELEGRAM_CHAT_ID,
            text="\n".join(lines),
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True,
        )
        logger.info("[Notifier] Отправлено %d напоминаний о дедлайнах", len(tenders))
        return True
    except Exception as e:
        logger.error("[Notifier] Ошибка отправки напоминаний: %s", str(e))
        return False
