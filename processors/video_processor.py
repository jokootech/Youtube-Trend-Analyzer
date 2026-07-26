"""Individual video processing task handler (Token & Debug Optimized)."""

from __future__ import annotations

from datetime import datetime, timezone
from loguru import logger

from config.settings import Settings
from core.database.database import Database
from scrapers.models import VideoMeta
from scrapers.youtube_api import YouTubeApiClient
from scrapers.youtube_scraper import YouTubeScraper
from services.llm.llm_engine import LLMEngine
from services.llm.schemas import AnalysisResult
from services.notifier.notifier import TelegramNotifier


def _calculate_hours_since(dt: datetime) -> float:
    """Calculate hours elapsed since datetime in UTC."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    delta = datetime.now(timezone.utc) - dt
    return max(delta.total_seconds() / 3600.0, 0.1)


class VideoProcessorTask:
    """Handles deep extraction, LLM analysis, DB persistence, and notification for a single video."""

    def __init__(
        self,
        settings: Settings,
        db: Database,
        scraper: YouTubeScraper,
        llm: LLMEngine,
        notifier: TelegramNotifier,
    ) -> None:
        self._s = settings
        self._db = db
        self._scraper = scraper
        self._llm = llm
        self._notifier = notifier

    async def process_single_video(self, video: VideoMeta) -> AnalysisResult | None:
        """Process a single VideoMeta instance through the remaining pipeline stages."""
        vid = video.video_id[:8]
        logger.info("Processing video_id={vid} title={title}", vid=vid, title=video.title)

        # Step 1: Deduplication record registration
        await self._db.insert_video(
            video_id=video.video_id,
            title=video.title,
            channel_id=video.channel_id,
            channel_title=video.channel_title,
            published_at=video.published_at.isoformat(),
            view_count=video.view_count,
            view_velocity=video.view_velocity,
        )

        # Step 2: Fetch comments safely using YouTubeApiClient via session
        comments: list[str] = []
        try:
            session = await self._scraper._get_session()
            api_client = YouTubeApiClient(self._s, session)
            comments = await api_client.fetch_top_comments(video.video_id)
            logger.debug("Fetched {n} comments for video_id={vid}", n=len(comments), vid=vid)
        except Exception as exc:
            logger.error("Comment fetch failed for video_id={vid}: {err}", vid=vid, err=exc)

        # Step 3: Run LLM Analysis with Detailed Debug Logging
        hours_old = _calculate_hours_since(video.published_at)
        try:
            proposal = await self._llm.analyze_video(
                video_id=video.video_id,
                title=video.title,
                channel_title=video.channel_title,
                view_count=video.view_count,
                like_count=video.like_count,
                comment_count=video.comment_count,
                velocity=video.view_velocity,
                hours_old=hours_old,
                comments=comments,
            )
        except Exception as exc:
            # Using repr(exc) to expose exact exception details (e.g. ValidationError, API error, etc.)
            logger.error("LLM analysis failed for video_id={vid} | Exact Exception: {err}", vid=video.video_id, err=repr(exc))
            return None

        # Step 4: Persist analysis result
        try:
            await self._db.save_analysis(
                video_id=video.video_id,
                provider=self._s.llm_provider.value,
                model=self._s.active_llm_model,
                strategy_json=proposal.model_dump_json(),
            )
        except Exception as exc:
            logger.error("DB analysis save failed for video_id={vid}: {err}", vid=vid, err=exc)

        # Step 5: Send notification
        result = AnalysisResult(
            video_id=video.video_id,
            title=video.title,
            channel_title=video.channel_title,
            view_count=video.view_count,
            view_velocity=video.view_velocity,
            published_at=video.published_at.isoformat(),
            proposal=proposal,
        )

        try:
            sent = await self._notifier.send_analysis_card(result)
            if sent:
                logger.info("Notification sent for video_id={vid}", vid=vid)
            else:
                logger.warning("Notification FAILED for video_id={vid}", vid=vid)
        except Exception as exc:
            logger.error("Notification exception for video_id={vid}: {err}", vid=vid, err=repr(exc))

        return result