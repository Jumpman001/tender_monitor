"""
BaseScraper — абстрактный класс для всех скраперов.
"""

import asyncio
from abc import ABC, abstractmethod
from typing import Optional

import aiohttp
from fake_useragent import UserAgent

from config import REQUEST_TIMEOUT_SEC, MAX_RETRIES, RETRY_BACKOFF_BASE, REQUEST_DELAY_SEC
from utils.logger import logger


class BaseScraper(ABC):
    """Базовый скрапер с retry-логикой и fake User-Agent."""

    def __init__(self, source_name: str):
        self.source_name = source_name
        self._ua = UserAgent()
        self._session: Optional[aiohttp.ClientSession] = None

    def _get_headers(self) -> dict:
        """Возвращает заголовки с рандомным User-Agent."""
        return {
            "User-Agent": self._ua.random,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9,ru;q=0.8",
        }

    async def _get_session(self) -> aiohttp.ClientSession:
        """Возвращает или создаёт HTTP-сессию."""
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT_SEC)
            self._session = aiohttp.ClientSession(
                timeout=timeout,
                headers=self._get_headers(),
            )
        return self._session

    async def close(self) -> None:
        """Закрывает HTTP-сессию."""
        if self._session and not self._session.closed:
            await self._session.close()

    async def fetch(self, url: str) -> Optional[str]:
        """
        GET запрос с retry (3 попытки, exponential backoff 2s, 4s, 8s).
        Возвращает HTML или None при ошибке.
        """
        session = await self._get_session()

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                logger.debug(
                    "[%s] Запрос (попытка %d/%d): %s",
                    self.source_name, attempt, MAX_RETRIES, url[:100],
                )
                async with session.get(url, headers=self._get_headers()) as resp:
                    if resp.status == 200:
                        text = await resp.text()
                        logger.debug(
                            "[%s] Получено %d байт: %s",
                            self.source_name, len(text), url[:80],
                        )
                        return text
                    else:
                        logger.warning(
                            "[%s] HTTP %d для %s",
                            self.source_name, resp.status, url[:80],
                        )
            except asyncio.TimeoutError:
                logger.warning(
                    "[%s] Timeout (попытка %d/%d): %s",
                    self.source_name, attempt, MAX_RETRIES, url[:80],
                )
            except aiohttp.ClientError as e:
                logger.warning(
                    "[%s] ClientError (попытка %d/%d): %s — %s",
                    self.source_name, attempt, MAX_RETRIES, url[:80], str(e),
                )
            except Exception as e:
                logger.error(
                    "[%s] Неожиданная ошибка (попытка %d/%d): %s — %s",
                    self.source_name, attempt, MAX_RETRIES, url[:80], str(e),
                )

            if attempt < MAX_RETRIES:
                backoff = RETRY_BACKOFF_BASE ** attempt
                logger.debug("[%s] Backoff %ds перед retry", self.source_name, backoff)
                await asyncio.sleep(backoff)

        logger.error("[%s] Все %d попыток исчерпаны для: %s", self.source_name, MAX_RETRIES, url[:80])
        return None

    async def fetch_json(self, url: str) -> Optional[dict]:
        """GET запрос, возвращает JSON или None."""
        session = await self._get_session()

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                async with session.get(url, headers=self._get_headers()) as resp:
                    if resp.status == 200:
                        data = await resp.json(content_type=None)
                        return data
                    else:
                        logger.warning(
                            "[%s] HTTP %d (JSON) для %s",
                            self.source_name, resp.status, url[:80],
                        )
            except Exception as e:
                logger.warning(
                    "[%s] JSON ошибка (попытка %d/%d): %s",
                    self.source_name, attempt, MAX_RETRIES, str(e),
                )

            if attempt < MAX_RETRIES:
                await asyncio.sleep(RETRY_BACKOFF_BASE ** attempt)

        return None

    async def delay(self) -> None:
        """Пауза между запросами к одному сайту."""
        await asyncio.sleep(REQUEST_DELAY_SEC)

    @abstractmethod
    async def scrape(self) -> list[dict]:
        """
        Основной метод парсинга. Возвращает список словарей с данными тендеров.

        Каждый словарь должен содержать минимум:
        - source: str
        - title: str
        - url: str
        - description: str (опционально)
        - project_id: str (опционально)
        - donor: str (опционально)
        - budget: str (опционально)
        - tender_deadline: str (опционально)
        - status: str (опционально)
        - region: str (опционально)
        """
        ...
