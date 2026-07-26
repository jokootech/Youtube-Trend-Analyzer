"""Hybrid YouTube Scraper Orchestrator with Multi-Language Adaptive Thresholds."""

from __future__ import annotations

import re
import aiohttp
from aiohttp_socks import ProxyConnector
from loguru import logger

from config.settings import Settings, get_settings
from scrapers.metrics import calculate_velocity, get_cutoff_dt, parse_dt
from scrapers.models import VideoMeta
from scrapers.rss_fetcher import RSSFetcher
from scrapers.youtube_api import YouTubeApiClient


def _detect_language_context(topics: list[str]) -> str:
    """Detects target community language based on input keywords (fa, es, en)."""
    text = " ".join(topics)
    # تشخیص زبان فارسی بر اساس کاراکترهای الفبای فارسی
    if re.search(r"[\u0600-\u06FF]", text):
        return "fa"
    # تشخیص زبان اسپانیایی بر اساس کاراکترهای خاص اسپانیایی
    if re.search(r"[áéíóúñ¿¡]", text.lower()):
        return "es"
    return "en"


def _get_language_thresholds(lang: str) -> dict[str, float]:
    """Returns adaptive viral thresholds based on community size."""
    if lang == "fa":
        return {
            "min_views": 500,         # کف بازدید مناسب برای ترندهای تازه فارسی
            "min_velocity": 15.0,     # ۱۵ بازدید در ساعت
            "mega_viral": 50000,      # ۵۰ هزار بازدید در فارسی
            "breakout_views": 5000,
        }
    elif lang == "es":
        return {
            "min_views": 5000,
            "min_velocity": 100.0,
            "mega_viral": 300000,
            "breakout_views": 20000,
        }
    else:  # en (English / Global Benchmark)
        return {
            "min_views": 50000,
            "min_velocity": 1000.0,
            "mega_viral": 1000000,
            "breakout_views": 100000,
        }


class YouTubeScraper:
    """Orchestrates hybrid RSS discovery, API enrichment, and adaptive Breakout ranking."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._s = settings or get_settings()
        self._session: aiohttp.ClientSession | None = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            proxy_url = getattr(self._s, "http_proxy", "socks5://127.0.0.1:12334")
            connector = ProxyConnector.from_url(proxy_url) if proxy_url and proxy_url.startswith("socks") else None

            self._session = aiohttp.ClientSession(
                connector=connector,
                headers={"User-Agent": "Mozilla/5.0 (compatible; TrendAnalyzerBot/1.0)"},
                timeout=aiohttp.ClientTimeout(total=self._s.youtube_api_timeout),
            )
        return self._session

    async def close(self) -> None:
        """Safely close the underlying aiohttp client session."""
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None

    async def fetch_and_rank(self, existing_ids: set[str] | None = None) -> list[VideoMeta]:
        """End-to-end enterprise pipeline with adaptive language filtering."""
        existing_ids = existing_ids or set()
        session = await self._get_session()

        rss_fetcher = RSSFetcher(self._s, session)
        api_client = YouTubeApiClient(self._s, session)

        # Step 1: Detect target language & apply threshold standards
        lang_code = _detect_language_context(self._s.target_topics)
        thresh = _get_language_thresholds(lang_code)
        logger.info(
            "Detected language context: '{lang}' | Thresholds: Min Views={mv}, Min Velocity={mv_v}",
            lang=lang_code.upper(),
            mv=thresh["min_views"],
            mv_v=thresh["min_velocity"],
        )

        # Step 2: Discovery via RSS with API Fallback
        rss_entries = await rss_fetcher.discover_all()
        if len(rss_entries) < 5:
            logger.info("RSS yield low, fetching from Search API fallback")
            for topic in self._s.target_topics:
                search_results = await api_client.search_videos_fallback(topic)
                existing_rss_ids = {e["video_id"] for e in rss_entries}
                for sr in search_results:
                    if sr["video_id"] not in existing_rss_ids:
                        rss_entries.append(sr)

        # Step 3: Deduplication
        unique_entries = {
            e["video_id"]: e for e in rss_entries
            if e["video_id"] not in existing_ids
        }

        # Step 4: Age Filtering (حداکثر ۳ روز اخیر)
        cutoff_dt = get_cutoff_dt(self._s.video_age_days_max)
        fresh_entries: dict[str, dict] = {}
        for vid, entry in unique_entries.items():
            pub_raw = entry.get("published_at", "")
            pub_dt = parse_dt(pub_raw) if pub_raw else None
            if pub_dt is None or pub_dt >= cutoff_dt:
                fresh_entries[vid] = entry

        if not fresh_entries:
            logger.info("No fresh videos found matching age criteria")
            return []

        # Step 5: Enrich via API
        fresh_ids = list(fresh_entries.keys())
        enriched_stats = await api_client.enrich_videos(fresh_ids)

        # Step 6: Multi-Language Adaptive Filtering
        metas: list[VideoMeta] = []
        for stat in enriched_stats:
            views = stat.get("view_count", 0)

            # فیلتر کف بازدید بر اساس زبان
            if views < thresh["min_views"]:
                continue

            vid = stat["video_id"]
            entry = fresh_entries.get(vid, {})
            pub_dt = parse_dt(stat.get("published_at") or entry.get("published_at", ""))
            velocity = calculate_velocity(views, pub_dt)

            # فیلتر سرعت رشد بر اساس زبان
            if velocity < thresh["min_velocity"]:
                continue

            metas.append(VideoMeta(
                video_id=vid,
                title=stat.get("title") or entry.get("title", ""),
                channel_id=stat.get("channel_id") or entry.get("channel_id", ""),
                channel_title=stat.get("channel_title") or entry.get("channel_title", ""),
                published_at=pub_dt,
                view_count=views,
                like_count=stat["like_count"],
                comment_count=stat["comment_count"],
                view_velocity=velocity,
                rss_source=entry.get("rss_source", ""),
            ))

        # Step 7: Rank by Velocity & Select Top Candidates
        metas.sort(key=lambda m: m.view_velocity, reverse=True)
        top_candidates = metas[: self._s.top_n_videos]

        logger.info(
            "Adaptive ranking complete [{lang}]: {total} candidates passed filter -> Top {n} selected",
            lang=lang_code.upper(),
            total=len(metas),
            n=len(top_candidates),
        )

        return top_candidates