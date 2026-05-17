"""
Inline-клавиатуры для Telegram бота.
"""

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def tender_keyboard(url: str, tender_hash: str) -> InlineKeyboardMarkup:
    """Клавиатура для карточки тендера."""
    buttons = [
        [
            InlineKeyboardButton(
                text="📄 Подробнее",
                url=url,
            ),
        ],
        [
            InlineKeyboardButton(
                text="📋 История",
                callback_data=f"history:{tender_hash[:32]}",
            ),
            InlineKeyboardButton(
                text="✅ Отмечено",
                callback_data=f"mark:{tender_hash[:32]}",
            ),
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def scan_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура после ручного сканирования."""
    buttons = [
        [
            InlineKeyboardButton(
                text="📊 Статус",
                callback_data="cmd:status",
            ),
            InlineKeyboardButton(
                text="📋 История",
                callback_data="cmd:history",
            ),
        ],
        [
            InlineKeyboardButton(
                text="🔍 Активные",
                callback_data="cmd:active",
            ),
            InlineKeyboardButton(
                text="🔴 Срочные",
                callback_data="cmd:urgent",
            ),
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def start_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура приветственного сообщения."""
    buttons = [
        [
            InlineKeyboardButton(
                text="🔄 Запустить скан",
                callback_data="cmd:scan",
            ),
            InlineKeyboardButton(
                text="📊 Статус",
                callback_data="cmd:status",
            ),
        ],
        [
            InlineKeyboardButton(
                text="📋 История (10)",
                callback_data="cmd:history",
            ),
            InlineKeyboardButton(
                text="🔍 Активные",
                callback_data="cmd:active",
            ),
        ],
        [
            InlineKeyboardButton(
                text="🔴 Срочные",
                callback_data="cmd:urgent",
            ),
            InlineKeyboardButton(
                text="📊 Отчёт",
                callback_data="cmd:report",
            ),
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def settings_keyboard(scan_interval: int) -> InlineKeyboardMarkup:
    """Клавиатура настроек."""
    buttons = [
        [
            InlineKeyboardButton(
                text=f"⏱ Интервал: {scan_interval}ч",
                callback_data="settings:interval",
            ),
        ],
        [
            InlineKeyboardButton(
                text="🔙 Назад",
                callback_data="cmd:start",
            ),
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)
