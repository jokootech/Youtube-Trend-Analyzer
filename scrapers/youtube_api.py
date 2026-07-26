"""YouTube Data API v3 async client wrapper."""

from __future__ import annotations

from typing import Any

import aiohttp
from loguru import logger

from config.settings import Settings
from scrapers.metrics import get_cutoff_dt
from scrapers.sanitizer import sanitize_comment


class YouTubeApiClient:
    """Handles direct interactions with YouTube Data API v3."""

    _API_VIDEOS = "https://www.googleapis.com/youtube/v3/videos"
    _API_COMMENTS = "https://www.googleapis.com/youtube/v3/commentThreads"
    _API_SEARCH = "https://www.googleapis.com/youtube/v3/search"

    def __init__(self, settings: Settings, session: aiohttp.ClientSession) -> None:
        self._s = settings
        self._session = session

    async def close(self) -> None:
        """Safely close internal HTTP session if managed locally."""
        if hasattr(self, "_session") and self._session and not self._session.closed:
            await self._session.close()
            self._session = None

    async def _api_request(self, url: str, params: dict[str, Any]) -> dict[str, Any] | None:
        """Execute a single HTTP GET request to YouTube Data API v3."""
        params["key"] = self._s.youtube_api_key.get_secret_value()
        try:
            async with self._session.get(url, params=params) as resp:
                if resp.status != 200:
                    body = await resp.text()
                    # لاگ اختصاصی برای کامنت‌های غیرفعال شده (کاهش سطح لاگ از warning به debug)
                    if resp.status == 403 and "commentsDisabled" in body:
                        logger.debug("Comments are disabled for this video: {body}", body=body[:150])
                        return None
                    logger.warning("API error status={status} body={body}", status=resp.status, body=body[:300])
                    return None
                return await resp.json()
        except Exception as exc:
            logger.error("API request exception url={url} error={error!r}", url=url, error=exc)
            return None

    async def enrich_videos(self, video_ids: list[str]) -> list[dict[str, Any]]:
        """Fetch stats (views, likes, comments) in batch (max 50 per request)."""
        if not video_ids:
            return []

        chunk_size = 50
        all_stats: list[dict[str, Any]] = []

        for i in range(0, len(video_ids), chunk_size):
            chunk = video_ids[i : i + chunk_size]
            data = await self._api_request(self._API_VIDEOS, {
                "part": "statistics,snippet",
                "id": ",".join(chunk),
                "maxResults": len(chunk),
            })
            if not data or "items" not in data:
                continue

            for item in data["items"]:
                stats = item.get("statistics", {})
                snippet = item.get("snippet", {})
                all_stats.append({
                    "video_id": item["id"],
                    "title": snippet.get("title", ""),
                    "channel_id": snippet.get("channelId", ""),
                    "channel_title": snippet.get("channelTitle", ""),
                    "published_at": snippet.get("publishedAt", ""),
                    "view_count": int(stats.get("viewCount", 0)),
                    "like_count": int(stats.get("likeCount", 0)),
                    "comment_count": int(stats.get("commentCount", 0)),
                })

        logger.info("Enriched {count}/{total} videos via API", count=len(all_stats), total=len(video_ids))
        return all_stats

    async def fetch_top_comments(self, video_id: str) -> list[str]:
        """Fetch and sanitize top-relevant comments for a video (handles disabled comments gracefully)."""
        data = await self._api_request(self._API_COMMENTS, {
            "part": "snippet",
            "videoId": video_id,
            "maxResults": self._s.youtube_max_comments,
            "order": "relevance",
            "textFormat": "plainText",
        })
        if not data or "items" not in data:
            return []

        comments: list[str] = []
        for item in data["items"]:
            top_level = item.get("snippet", {}).get("topLevelComment", {})
            text = top_level.get("snippet", {}).get("textDisplay", "")
            if text.strip():
                comments.append(sanitize_comment(text))
        return comments

    async def search_videos_fallback(self, query: str) -> list[dict[str, Any]]:
        """Fallback search endpoint when RSS yields low results."""
        cutoff_str = get_cutoff_dt(self._s.video_age_days_max).strftime("%Y-%m-%dT%H:%M:%SZ")
        data = await self._api_request(self._API_SEARCH, {
            "part": "snippet",
            "q": query,
            "type": "video",
            "order": "relevance",  # تغییر به relevance جهت دریافت ویدیوهای باکیفیت‌تر و دارای بازدید
            "maxResults": self._s.youtube_max_results,
            "publishedAfter": cutoff_str,
        })
        if not data or "items" not in data:
            return []

        results: list[dict[str, Any]] = []
        for item in data["items"]:
            vid = item.get("id", {}).get("videoId")
            if not vid:
                continue
            snippet = item.get("snippet", {})
            results.append({
                "video_id": vid,
                "title": snippet.get("title", ""),
                "channel_id": snippet.get("channelId", ""),
                "channel_title": snippet.get("channelTitle", ""),
                "published_at": snippet.get("publishedAt", ""),
                "rss_source": f"search:{query}",
            })
        return results