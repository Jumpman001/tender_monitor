"""
Telegram Bot Handlers — все команды бота.
"""

import asyncio
from datetime import datetime

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from core.deep_search import deep_investigate

from config import TELEGRAM_CHAT_ID, SCAN_INTERVAL_HOURS
from database import db
from bot.keyboards import start_keyboard, scan_keyboard, settings_keyboard
from bot.notifier import format_tender_message, send_tender_notification
from utils.logger import logger

router = Router()

class SearchState(StatesGroup):
    waiting_for_project_name = State()

# ─── Ссылка на функцию сканирования (устанавливается из main.py) ────
_run_scan_func = None


def set_scan_function(func):
    """Устанавливает ссылку на функцию полного сканирования."""
    global _run_scan_func
    _run_scan_func = func


# ─── /start ──────────────────────────────────────────────────────────

@router.message(Command("start"))
async def cmd_start(message: Message):
    """Приветствие + инструкция."""
    total = await db.get_tender_count()

    text = (
        "🏗 <b>Tender Monitor Bot</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "Автоматический мониторинг тендеров\n"
        "на трубы DN ≥ 400 мм в Таджикистане\n\n"
        f"📦 Тендеров в базе: <b>{total}</b>\n"
        f"⏱ Сканирование каждые <b>{SCAN_INTERVAL_HOURS}</b> часов\n\n"
        "<b>Доступные команды:</b>\n"
        "/start — приветствие\n"
        "/status — статус бота\n"
        "/scan — запустить скан вручную\n"
        "/report — еженедельный дайджест\n"
        "/history N — последние N тендеров\n"
        "/search текст — поиск по базе\n"
        "/active — активные тендеры\n"
        "/urgent — срочные тендеры\n"
        "/settings — настройки\n"
        "━━━━━━━━━━━━━━━━━━━━━"
    )

    await message.answer(text, parse_mode="HTML", reply_markup=start_keyboard())


# ─── /status ─────────────────────────────────────────────────────────

@router.message(Command("status"))
async def cmd_status(message: Message):
    """Статус бота: последний скан, количество тендеров."""
    total = await db.get_tender_count()
    last_scan = await db.get_last_scan()

    scan_info = "❌ Ещё не выполнялся"
    if last_scan:
        scan_info = (
            f"✅ {last_scan.scanned_at[:19]}\n"
            f"   Источник: {last_scan.source}\n"
            f"   Найдено: {last_scan.found_total} | Новых: {last_scan.new_tenders}"
        )
        if last_scan.errors:
            scan_info += f"\n   ⚠️ Ошибки: {last_scan.errors[:100]}"

    text = (
        "📊 <b>СТАТУС БОТА</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        f"📦 Тендеров в базе: <b>{total}</b>\n"
        f"🔄 Последний скан:\n{scan_info}\n"
        f"⏱ Интервал: каждые {SCAN_INTERVAL_HOURS} часов\n"
        "━━━━━━━━━━━━━━━━━━━━━"
    )

    await message.answer(text, parse_mode="HTML")


# ─── /scan ───────────────────────────────────────────────────────────

@router.message(Command("scan"))
async def cmd_scan(message: Message):
    """Запустить немедленный скан всех источников."""
    await message.answer(
        "🔄 <b>Запускаю сканирование всех источников...</b>\n"
        "Это может занять 1–3 минуты.",
        parse_mode="HTML",
    )

    if _run_scan_func:
        try:
            asyncio.create_task(_run_scan_func(message.bot))
        except Exception as e:
            await message.answer(f"❌ Ошибка запуска сканирования: {e}")
    else:
        await message.answer("⚠️ Функция сканирования не инициализирована.")


# ─── /report ─────────────────────────────────────────────────────────

@router.message(Command("report"))
async def cmd_report(message: Message):
    """Еженедельный дайджест."""
    from bot.notifier import send_digest

    report_data = await db.get_weekly_report_data()
    success = await send_digest(message.bot, report_data)

    if not success:
        # Отправляем в текущий чат если CHAT_ID не совпадает
        new_tenders = report_data.get("new_tenders", [])
        text = (
            f"📊 <b>ДАЙДЖЕСТ</b>\n\n"
            f"Новых за неделю: {len(new_tenders)}\n"
            f"Активных: {report_data.get('active_count', 0)}\n"
            f"Всего: {report_data.get('total_count', 0)}"
        )
        await message.answer(text, parse_mode="HTML")


# ─── /history ────────────────────────────────────────────────────────

@router.message(Command("history"))
async def cmd_history(message: Message):
    """Последние N тендеров (по умолчанию 10)."""
    # Парсим аргумент
    args = message.text.strip().split()
    limit = 10
    if len(args) > 1:
        try:
            limit = int(args[1])
            limit = min(limit, 50)  # Максимум 50
        except ValueError:
            limit = 10

    tenders = await db.get_recent_tenders(limit)

    if not tenders:
        await message.answer("📭 В базе пока нет тендеров.")
        return

    lines = [
        f"📋 <b>Последние {len(tenders)} тендеров:</b>",
        "━━━━━━━━━━━━━━━━━━━━━",
        "",
    ]

    for i, t in enumerate(tenders, 1):
        status_emoji = {"Active": "🟢", "Signed": "🔵", "Planned": "🟡"}.get(
            t.status, "⚪"
        )
        budget_str = f" | {t.budget}" if t.budget else ""
        lines.append(
            f"{status_emoji} {i}. <a href=\"{t.url}\">{t.title[:55]}</a>{budget_str}"
        )
        lines.append(f"   📌 {t.source} | {t.first_seen[:10]}")
        lines.append("")

    lines.append("━━━━━━━━━━━━━━━━━━━━━")

    # Разбиваем на части если слишком длинное
    text = "\n".join(lines)
    if len(text) > 4000:
        # Отправляем частями
        parts = [text[i:i + 4000] for i in range(0, len(text), 4000)]
        for part in parts:
            await message.answer(part, parse_mode="HTML", disable_web_page_preview=True)
    else:
        await message.answer(text, parse_mode="HTML", disable_web_page_preview=True)


# ─── /search ─────────────────────────────────────────────────────────

@router.message(Command("search"))
async def cmd_search(message: Message):
    """Поиск по базе тендеров."""
    args = message.text.strip().split(maxsplit=1)
    if len(args) < 2:
        await message.answer("ℹ️ Использование: /search <текст>\nПример: /search irrigation pipeline")
        return

    query = args[1]
    tenders = await db.search_tenders(query)

    if not tenders:
        await message.answer(f"🔍 По запросу «{query}» ничего не найдено.")
        return

    lines = [
        f"🔍 <b>Результаты поиска: «{query}»</b>",
        f"Найдено: {len(tenders)}",
        "━━━━━━━━━━━━━━━━━━━━━",
        "",
    ]

    for i, t in enumerate(tenders, 1):
        lines.append(f"{i}. <a href=\"{t.url}\">{t.title[:60]}</a>")
        lines.append(f"   📌 {t.source} | {t.status}")
        lines.append("")

    text = "\n".join(lines)
    if len(text) > 4000:
        text = text[:4000] + "\n... (обрезано)"
    await message.answer(text, parse_mode="HTML", disable_web_page_preview=True)


# ─── /active ─────────────────────────────────────────────────────────

@router.message(Command("active"))
async def cmd_active(message: Message):
    """Только тендеры со статусом Active."""
    tenders = await db.get_active_tenders()

    if not tenders:
        await message.answer("📭 Нет активных тендеров.")
        return

    lines = [
        f"🟢 <b>Активные тендеры: {len(tenders)}</b>",
        "━━━━━━━━━━━━━━━━━━━━━",
        "",
    ]

    for i, t in enumerate(tenders[:20], 1):
        budget_str = f" | {t.budget}" if t.budget else ""
        lines.append(f"🟢 {i}. <a href=\"{t.url}\">{t.title[:55]}</a>{budget_str}")
        lines.append(f"   📅 Дедлайн: {t.tender_deadline or 'N/A'}")
        lines.append("")

    if len(tenders) > 20:
        lines.append(f"... и ещё {len(tenders) - 20} активных тендеров")

    text = "\n".join(lines)
    if len(text) > 4000:
        text = text[:4000] + "\n... (обрезано)"
    await message.answer(text, parse_mode="HTML", disable_web_page_preview=True)


# ─── /urgent ─────────────────────────────────────────────────────────

@router.message(Command("urgent"))
async def cmd_urgent(message: Message):
    """Только HIGH urgency тендеры (дедлайн < 14 дней)."""
    tenders = await db.get_tenders_with_deadline_soon(14)

    if not tenders:
        await message.answer("✅ Нет срочных тендеров (дедлайн < 14 дней).")
        return

    lines = [
        f"🔴 <b>СРОЧНЫЕ ТЕНДЕРЫ: {len(tenders)}</b>",
        "━━━━━━━━━━━━━━━━━━━━━",
        "",
    ]

    for i, t in enumerate(tenders, 1):
        lines.append(f"🔴 {i}. <a href=\"{t.url}\">{t.title[:55]}</a>")
        lines.append(f"   📅 Дедлайн: {t.tender_deadline}")
        if t.budget:
            lines.append(f"   💰 {t.budget}")
        lines.append("")

    text = "\n".join(lines)
    if len(text) > 4000:
        text = text[:4000] + "\n... (обрезано)"
    await message.answer(text, parse_mode="HTML", disable_web_page_preview=True)


# ─── /settings ───────────────────────────────────────────────────────

@router.message(Command("settings"))
async def cmd_settings(message: Message):
    """Настройки бота."""
    from config import MIN_PIPE_DIAMETER_MM, REQUEST_DELAY_SEC, DB_PATH

    text = (
        "⚙️ <b>НАСТРОЙКИ</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        f"⏱ Интервал сканирования: {SCAN_INTERVAL_HOURS} ч\n"
        f"🔩 Мин. диаметр: DN {MIN_PIPE_DIAMETER_MM} мм\n"
        f"⏳ Пауза между запросами: {REQUEST_DELAY_SEC} сек\n"
        f"💾 База данных: {DB_PATH}\n"
        "━━━━━━━━━━━━━━━━━━━━━"
    )

    await message.answer(
        text,
        parse_mode="HTML",
        reply_markup=settings_keyboard(SCAN_INTERVAL_HOURS),
    )


# ─── Callback handlers ──────────────────────────────────────────────

@router.callback_query(F.data.startswith("cmd:"))
async def callback_command(callback: CallbackQuery):
    """Обработка inline-кнопок команд."""
    cmd = callback.data.split(":")[1]
    await callback.answer()

    # Создаём фейковое сообщение с текстом команды
    if cmd == "start":
        await cmd_start(callback.message)
    elif cmd == "status":
        await cmd_status(callback.message)
    elif cmd == "scan":
        await callback.message.answer(
            "🔄 <b>Запускаю сканирование...</b>", parse_mode="HTML"
        )
        if _run_scan_func:
            asyncio.create_task(_run_scan_func(callback.message.bot))
    elif cmd == "history":
        callback.message.text = "/history 10"
        await cmd_history(callback.message)
    elif cmd == "active":
        await cmd_active(callback.message)
    elif cmd == "urgent":
        await cmd_urgent(callback.message)
    elif cmd == "report":
        await cmd_report(callback.message)


@router.callback_query(F.data.startswith("mark:"))
async def callback_mark_viewed(callback: CallbackQuery):
    """Пометить тендер как просмотренный."""
    tender_hash = callback.data.split(":")[1]
    await callback.answer("✅ Отмечено как просмотренный")
    logger.info("[Bot] Тендер отмечен как просмотренный: %s", tender_hash[:16])


@router.callback_query(F.data.startswith("history:"))
async def callback_tender_history(callback: CallbackQuery):
    """Показать историю тендера."""
    tender_hash_prefix = callback.data.split(":")[1]
    await callback.answer("📋 История изменений")

    # Поиск тендера по хэшу
    tenders = await db.get_recent_tenders(100)
    found = None
    for t in tenders:
        if t.hash.startswith(tender_hash_prefix):
            found = t
            break

    if found:
        text = (
            f"📋 <b>История тендера</b>\n\n"
            f"📌 {found.title[:60]}\n"
            f"🔗 {found.source}\n"
            f"📅 Первое обнаружение: {found.first_seen[:19]}\n"
            f"🔄 Последнее обновление: {found.last_updated[:19]}\n"
            f"📊 Статус: {found.status}\n"
        )
        if found.ai_card:
            text += f"\n{found.ai_card[:500]}"
    else:
        text = "ℹ️ Тендер не найден в базе."

    await callback.message.answer(text, parse_mode="HTML", disable_web_page_preview=True)


# ─── Глубокий поиск (Deep Search) ────────────────────────────────────

@router.callback_query(F.data == "action:deep_search")
async def process_deep_search_btn(callback: CallbackQuery, state: FSMContext):
    """Нажатие кнопки 'Поиск в сети'."""
    await callback.message.answer(
        "🔍 <b>Глубокий поиск по проекту</b>\n\n"
        "Отправьте мне название проекта, тендера или любую ключевую информацию (на английском или русском).\n"
        "Я найду все доступные данные в интернете и составлю полное досье.",
        parse_mode="HTML"
    )
    await state.set_state(SearchState.waiting_for_project_name)
    await callback.answer()

@router.message(SearchState.waiting_for_project_name)
async def execute_deep_search(message: Message, state: FSMContext):
    project_name = message.text.strip()
    if len(project_name) < 3:
        await message.answer("Слишком короткое название. Попробуйте снова.")
        return
        
    await state.clear()
    msg = await message.answer("⏳ <i>Ищу информацию в открытых источниках и анализирую... (это займет около 10-20 секунд)</i>", parse_mode="HTML")
    
    try:
        report = await deep_investigate(project_name)
        await msg.edit_text(report, parse_mode="HTML")
    except Exception as e:
        logger.error("Deep search error: %s", e)
        await msg.edit_text("⚠️ Ошибка при поиске. Попробуйте позже.")
