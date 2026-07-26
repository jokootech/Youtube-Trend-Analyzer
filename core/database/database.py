"""Async SQLite database manager and lifecycle facade."""

from __future__ import annotations

from pathlib import Path
from typing import Any
import aiosqlite
from loguru import logger

from config.settings import Settings, get_settings
from core.database.repository import VideoRepository
from core.database.schema import INIT_SCHEMA_SQL


class Database:
    """Async SQLite database interface with automatic repository delegation."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._db_path: Path = self._settings.db_path
        self._connection: aiosqlite.Connection | None = None
        self._repo: VideoRepository | None = None

    async def connect(self) -> None:
        """Establish SQLite connection with WAL mode and apply migrations."""
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = await aiosqlite.connect(
            str(self._db_path),
            timeout=30.0,  # Prevent database locked errors under concurrency
        )
        self._connection.row_factory = aiosqlite.Row
        
        # Apply schema and WAL mode
        await self._connection.executescript(INIT_SCHEMA_SQL)
        await self._connection.commit()

        self._repo = VideoRepository(self._get_connection)
        logger.info("Database connected successfully path={path}", path=self._db_path)

    async def close(self) -> None:
        """Close database connection gracefully."""
        if self._connection:
            await self._connection.close()
            self._connection = None
            self._repo = None
            logger.info("Database connection closed")

    def _get_connection(self) -> aiosqlite.Connection:
        """Internal connection accessor ensuring active connection state."""
        if self._connection is None:
            raise RuntimeError("Database is not connected. Call connect() first.")
        return self._connection

    @property
    def repo(self) -> VideoRepository:
        """Access the repository for database operations."""
        if self._repo is None:
            raise RuntimeError("Database is not connected. Call connect() first.")
        return self._repo

    # Convenience delegators for direct access from db instance
    async def get_processed_video_ids(self) -> set[str]:
        return await self.repo.get_processed_video_ids()

    async def video_exists(self, video_id: str) -> bool:
        return await self.repo.video_exists(video_id)

    async def insert_video(self, **kwargs) -> None:
        await self.repo.insert_video(**kwargs)

    async def save_analysis(self, **kwargs) -> None:
        await self.repo.save_analysis(**kwargs)

    async def get_recent_analyses(self, limit: int = 10) -> list[dict[str, Any]]:
        return await self.repo.get_recent_analyses(limit)

    async def stats(self) -> dict[str, int]:
        return await self.repo.get_stats()