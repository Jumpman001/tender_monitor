"""
Настройка логирования — файл + консоль.
"""

import logging
import sys
from pathlib import Path

from config import LOG_LEVEL, LOG_FILE


def setup_logger(name: str = "tender_monitor") -> logging.Logger:
    """Создаёт и настраивает логгер с выводом в файл и консоль."""
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, LOG_LEVEL.upper(), logging.INFO))

    # Формат
    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Консольный handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # Файловый handler
    log_path = Path(LOG_FILE)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    file_handler = logging.FileHandler(str(log_path), encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger


# Глобальный экземпляр логгера
logger = setup_logger()
