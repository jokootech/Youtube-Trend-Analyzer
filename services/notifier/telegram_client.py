"""Telegram Bot API Client implementation using HTTP/SOCKS5 Proxy."""

from __future__ import annotations

import aiohttp
from aiohttp_socks import ProxyConnector
from loguru import logger

from config.settings import Settings


class TelegramClient:
    """Async wrapper around Telegram Bot API with proxy support."""

    def __init__(self, settings: Settings) -> None:
        self._s = settings
        self._bot_token = settings.telegram_bot_token.get_secret_value()
        self._chat_id = settings.telegram_chat_id
        self._base_url = f"https://api.telegram.org/bot{self._bot_token}"

    async def send_message(self, text: str) -> bool:
        """Send an HTML-formatted message to the configured target chat."""
        url = f"{self._base_url}/sendMessage"
        payload = {
            "chat_id": self._chat_id,
            "text": text,
            "parse_mode": self._s.telegram_parse_mode,
            "disable_web_page_preview": self._s.telegram_disable_web_preview,
        }

        # Handle SOCKS5 or HTTP proxy dynamically if provided
        proxy_url = getattr(self._s, "http_proxy", "socks5://127.0.0.1:12334")
        
        connector = ProxyConnector.from_url(proxy_url) if proxy_url.startswith("socks") else None
        session_kwargs = {"connector": connector} if connector else {}

        try:
            async with aiohttp.ClientSession(**session_kwargs) as session:
                async with session.post(
                    url, 
                    json=payload, 
                    proxy=None if connector else proxy_url, 
                    timeout=aiohttp.ClientTimeout(total=15)
                ) as resp:
                    if resp.status == 200:
                        logger.debug("Telegram notification dispatched successfully")
                        return True
                    
                    body = await resp.text()
                    logger.error("Telegram API returned non-200 status={s}: {b}", s=resp.status, b=body[:200])
                    return False
        except Exception as exc:
            logger.error("Telegram request exception with proxy: {err}", err=exc)
            return False