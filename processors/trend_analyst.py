"""Trend Analysis Pipeline Orchestrator with Robust Resource Cleanup."""

from __future__ import annotations

import asyncio
from loguru import logger

from config.settings import Settings, get_settings
from core.database.database import Database
from processors.video_processor import VideoProcessorTask
from scrapers.youtube_scraper import YouTubeScraper
from services.llm.llm_engine import LLMEngine
from services.llm.schemas import AnalysisResult
from services.notifier.notifier import TelegramNotifier


class TrendAnalyst:
    """End-to-end pipeline: Scrape → Rank → LLM → Notify."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._s = settings or get_settings()
        self._db = Database(self._s)
        self._scraper = YouTubeScraper(self._s)
        self._llm = LLMEngine(self._s)
        self._notifier = TelegramNotifier(self._s)

    async def startup(self) -> None:
        """Initialise database connection and active sessions."""
        await self._db.connect()
        logger.info(
            "TrendAnalyst started mode={mode} interval={min}m",
            mode=self._s.run_mode.value,
            min=self._s.poll_interval_minutes,
        )

    async def shutdown(self) -> None:
        """Gracefully close all sub-components and network sessions independently."""
        logger.info("Shutting down TrendAnalyst sub-components...")

        # 1. Scraper session cleanup
        try:
            if hasattr(self, "_scraper") and self._scraper:
                await self._scraper.close()
        except Exception as exc:
            logger.warning("Error closing scraper session: {err!r}", err=exc)

        # 2. LLM Engine session cleanup
        try:
            if hasattr(self, "_llm") and self._llm:
                await self._llm.close()
        except Exception as exc:
            logger.warning("Error closing LLM engine session: {err!r}", err=exc)

        # 3. Telegram Notifier session cleanup
        try:
            if hasattr(self, "_notifier") and self._notifier:
                await self._notifier.close()
        except Exception as exc:
            logger.warning("Error closing notifier session: {err!r}", err=exc)

        # 4. Database connection cleanup
        try:
            if hasattr(self, "_db") and self._db:
                await self._db.close()
        except Exception as exc:
            logger.warning("Error closing database connection: {err!r}", err=exc)

        logger.info("TrendAnalyst shut down complete")

    async def run_once(self) -> list[AnalysisResult]:
        """Execute a single full pipeline iteration."""
        logger.info("========== Pipeline Run Started ==========")

        # Stage 1: Deduplication lookups
        existing_ids = await self._db.get_processed_video_ids()

        # Stage 2: Scrape and rank
        top_videos = await self._scraper.fetch_and_rank(existing_ids)

        if not top_videos:
            logger.info("Pipeline: No new qualifying videos found")
            return []

        logger.info("Pipeline: {n} qualifying videos ready for deep analysis", n=len(top_videos))

        # Stage 3 & 4: Deep analysis & Notification
        task_handler = VideoProcessorTask(
            settings=self._s,
            db=self._db,
            scraper=self._scraper,
            llm=self._llm,
            notifier=self._notifier,
        )

        results: list[AnalysisResult] = []
        for idx, video in enumerate(top_videos, 1):
            logger.info("Processing [{idx}/{total}]: {title}", idx=idx, total=len(top_videos), title=video.title)
            res = await task_handler.process_single_video(video)
            if res:
                results.append(res)

        logger.info("========== Pipeline Run Complete processed={n} ==========", n=len(results))
        return results