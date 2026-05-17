"""
Tender Monitor Bot — точка входа.
Запуск Telegram бота + APScheduler + первичное сканирование.
"""

import asyncio
import sys

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
from database.db import init_db
from bot.handlers import router, set_scan_function
from core.scheduler import setup_scheduler, run_full_scan
from utils.logger import logger


async def main():
    """Главная функция — запуск бота."""
    # ─── Проверка конфигурации ───────────────────────────────
    if not TELEGRAM_BOT_TOKEN or TELEGRAM_BOT_TOKEN == "your_bot_token_here":
        logger.error("TELEGRAM_BOT_TOKEN не установлен! Скопируй .env.example → .env и заполни.")
        sys.exit(1)

    if not TELEGRAM_CHAT_ID or TELEGRAM_CHAT_ID == "your_chat_id_here":
        logger.warning("TELEGRAM_CHAT_ID не установлен — уведомления не будут отправляться.")

    # ─── Инициализация БД ────────────────────────────────────
    await init_db()

    # ─── Инициализация бота ──────────────────────────────────
    bot = Bot(
        token=TELEGRAM_BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher()
    dp.include_router(router)

    # ─── Установка функции сканирования для хендлеров ────────
    set_scan_function(run_full_scan)

    # ─── Настройка планировщика ──────────────────────────────
    scheduler = setup_scheduler(bot)
    scheduler.start()
    logger.info("APScheduler запущен")

    # ─── Первичное сканирование (в фоне) ─────────────────────
    logger.info("Запуск первичного сканирования в фоне...")
    asyncio.create_task(run_full_scan(bot))

    # ─── Запуск бота ─────────────────────────────────────────
    logger.info("Бот запущен! Ожидание команд...")

    try:
        # Отправляем стартовое сообщение
        if TELEGRAM_CHAT_ID and TELEGRAM_CHAT_ID != "your_chat_id_here":
            try:
                await bot.send_message(
                    chat_id=TELEGRAM_CHAT_ID,
                    text=(
                        "🚀 <b>Tender Monitor Bot запущен!</b>\n\n"
                        "Автоматический мониторинг тендеров на трубы\n"
                        "DN ≥ 400 мм в Таджикистане.\n\n"
                        "Первичное сканирование запущено..."
                    ),
                )
            except Exception as e:
                logger.warning("Не удалось отправить стартовое сообщение: %s", str(e))

        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())

    finally:
        scheduler.shutdown(wait=False)
        await bot.session.close()
        logger.info("Бот остановлен.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Бот остановлен пользователем (Ctrl+C)")
    except Exception as e:
        logger.error("Критическая ошибка: %s", str(e))
        sys.exit(1)
