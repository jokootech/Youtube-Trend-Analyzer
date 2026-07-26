"""Telegram Notifier Service with Proper Proxy & Lifecycle Management."""

from __future__ import annotations

import aiohttp
from aiohttp_socks import ProxyConnector
from loguru import logger

from config.settings import Settings
from services.llm.schemas import AnalysisResult
from services.notifier.card_formatter import build_analysis_html_card


class TelegramNotifier:
    """Handles dispatching analysis cards and text alerts to Telegram."""

    def __init__(self, settings: Settings) -> None:
        self._s = settings
        self._session: aiohttp.ClientSession | None = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            # دریافت آدرس پروکسی از تنظیمات یا مقدار پیش‌فرض هدیفای
            proxy_url = getattr(self._s, "http_proxy", "socks5://127.0.0.1:12334")
            connector = ProxyConnector.from_url(proxy_url) if proxy_url and proxy_url.startswith("socks") else None

            self._session = aiohttp.ClientSession(
                connector=connector,
                timeout=aiohttp.ClientTimeout(total=15.0),
            )
        return self._session

    async def close(self) -> None:
        """Explicitly and safely close the aiohttp session."""
        if self._session and not self._session.closed:
            try:
                await self._session.close()
            except Exception as exc:
                logger.warning("Error closing TelegramNotifier session: {err!r}", err=exc)
            finally:
                self._session = None

    async def send_text(self, text: str) -> bool:
        """Send a simple HTML text message."""
        bot_token = self._s.telegram_bot_token.get_secret_value()
        chat_id = self._s.telegram_chat_id
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"

        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }

        try:
            session = await self._get_session()
            async with session.post(url, json=payload) as resp:
                if resp.status == 200:
                    return True
                body = await resp.text()
                logger.error("Telegram send failed status={s}: {b}", s=resp.status, b=body)
                return False
        except Exception as exc:
            logger.error("Telegram dispatch exception: {err!r}", err=exc)
            return False

    async def send_analysis_card(self, result: AnalysisResult) -> bool:
        """Format and send analysis HTML card to Telegram."""
        card_html = build_analysis_html_card(result)
        return await self.send_text(card_html)