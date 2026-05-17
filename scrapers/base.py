"""
BaseScraper — абстрактный класс для всех скраперов.
"""

import asyncio
import ssl
from abc import ABC, abstractmethod
from typing import Optional

import aiohttp
import certifi
from fake_useragent import UserAgent

from config import REQUEST_TIMEOUT_SEC, MAX_RETRIES, RETRY_BACKOFF_BASE, REQUEST_DELAY_SEC
from utils.logger import logger


class BaseScraper(ABC):
    """Базовый скрапер с retry-логикой, fake User-Agent и правильным SSL."""

    def __init__(self, source_name: str):
        self.source_name = source_name
        self._ua = UserAgent()
        self._session: Optional[aiohttp.ClientSession] = None
        # SSL контекст с системными CA-сертификатами через certifi
        self._ssl_ctx = ssl.create_default_context(cafile=certifi.where())

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
            connector = aiohttp.TCPConnector(ssl=self._ssl_ctx)
            self._session = aiohttp.ClientSession(
                timeout=timeout,
                headers=self._get_headers(),
                connector=connector,
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
        При SSL-ошибке автоматически пробует без верификации.
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
                        if resp.status in (403, 404):
                            break
            except aiohttp.ClientConnectorSSLError:
                # SSL ошибка — пробуем без верификации
                logger.warning(
                    "[%s] SSL ошибка, пробуем без верификации: %s",
                    self.source_name, url[:80],
                )
                try:
                    connector = aiohttp.TCPConnector(ssl=False)
                    async with aiohttp.ClientSession(
                        timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT_SEC),
                        connector=connector,
                    ) as fallback:
                        async with fallback.get(url, headers=self._get_headers()) as resp:
                            if resp.status == 200:
                                return await resp.text()
                except Exception:
                    pass
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

    async def fetch_json(self, url: str) -> Optional[dict | list]:
        """GET запрос, возвращает JSON (dict или list) или None."""
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
                        if resp.status in (403, 404):
                            break
            except aiohttp.ClientConnectorSSLError:
                try:
                    connector = aiohttp.TCPConnector(ssl=False)
                    async with aiohttp.ClientSession(
                        timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT_SEC),
                        connector=connector,
                    ) as fallback:
                        async with fallback.get(url, headers=self._get_headers()) as resp:
                            if resp.status == 200:
                                return await resp.json(content_type=None)
                except Exception:
                    pass
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
