"""Async YouTube RSS feed fetcher (Zero Quota / Zero Ban risk)."""

from __future__ import annotations

import asyncio
import xml.etree.ElementTree as ET
from typing import Any
from urllib.parse import quote

import aiohttp
from loguru import logger

from config.settings import Settings
from scrapers.sanitizer import extract_video_id


class RSSFetcher:
    """Handles fetching and parsing YouTube Atom/RSS feeds for targeted channels and playlists."""

    _RSS_CHANNEL_URL = "https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
    _RSS_PLAYLIST_URL = "https://www.youtube.com/feeds/videos.xml?playlist_id={playlist_id}"
    
    _ATOM_NS = "http://www.w3.org/2005/Atom"
    _YT_NS = "http://www.youtube.com/xml/schemas/2015"

    def __init__(self, settings: Settings, session: aiohttp.ClientSession) -> None:
        self._s = settings
        self._session = session

    async def fetch_feed_entries(self, feed_url: str, source_label: str) -> list[dict[str, Any]]:
        """Fetch and parse a single YouTube RSS/Atom feed URL into raw entry dicts."""
        logger.debug("Fetching RSS feed url={url}", url=feed_url)
        try:
            timeout = aiohttp.ClientTimeout(total=self._s.youtube_rss_timeout)
            async with self._session.get(feed_url, timeout=timeout) as resp:
                if resp.status != 200:
                    logger.warning("RSS fetch failed status={status} url={url}", status=resp.status, url=feed_url)
                    return []
                xml_bytes = await resp.read()
        except Exception as exc:
            logger.error("RSS fetch error url={url} error={error!r}", url=feed_url, error=exc)
            return []

        try:
            root = ET.fromstring(xml_bytes)
        except ET.ParseError as pe:
            logger.error("XML parse error url={url} error={error!r}", url=feed_url, error=pe)
            return []

        entries: list[dict[str, Any]] = []
        ns = {
            "atom": self._ATOM_NS,
            "yt": self._YT_NS,
        }

        for entry in root.findall("atom:entry", ns):
            # 1. Extract Video ID safely via YT namespace or ID element fallback
            yt_vid_elem = entry.find("yt:videoId", ns)
            if yt_vid_elem is not None and yt_vid_elem.text:
                vid = yt_vid_elem.text.strip()
            else:
                raw_id = entry.findtext("atom:id", "", ns)
                vid = extract_video_id(raw_id)

            if not vid:
                continue

            # 2. Extract Channel metadata safely
            yt_ch_elem = entry.find("yt:channelId", ns)
            ch_id = yt_ch_elem.text.strip() if yt_ch_elem is not None and yt_ch_elem.text else ""

            author_elem = entry.find("atom:author", ns)
            ch_title = "Unknown"
            if author_elem is not None:
                ch_title = author_elem.findtext("atom:name", "Unknown", ns)
                if not ch_id:
                    uri = author_elem.findtext("atom:uri", "", ns)
                    ch_id = uri.rsplit("/", 1)[-1] if uri else ""

            published = entry.findtext("atom:published", "", ns)
            title = entry.findtext("atom:title", "Unknown", ns)

            entries.append({
                "video_id": vid,
                "title": title,
                "channel_id": ch_id,
                "channel_title": ch_title,
                "published_at": published,
                "rss_source": source_label,
            })

        logger.debug("RSS returned {count} entries from {source}", count=len(entries), source=source_label)
        return entries

    async def discover_all(self) -> list[dict[str, Any]]:
        """Fetch videos from all configured channels via RSS in parallel."""
        tasks: list[asyncio.Task] = []

        # YouTube RSS feeds are supported only for channel_id and playlist_id
        for ch_id in getattr(self._s, "target_channel_ids", []):
            if ch_id:
                url = self._RSS_CHANNEL_URL.format(channel_id=ch_id)
                tasks.append(asyncio.create_task(self.fetch_feed_entries(url, source_label=f"channel:{ch_id}")))

        if not tasks:
            logger.info("No channel RSS feeds configured — delegating discovery to Search API")
            return []

        results = await asyncio.gather(*tasks, return_exceptions=True)
        all_entries: list[dict[str, Any]] = []

        for res in results:
            if isinstance(res, list):
                all_entries.extend(res)
            elif isinstance(res, Exception):
                logger.error("RSS discovery task failed: {error!r}", error=res)

        return all_entries