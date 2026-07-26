"""Database Repository providing async CRUD operations."""

from __future__ import annotations

from typing import Any
import aiosqlite


class VideoRepository:
    """Handles persistence and retrieval for processed videos and analysis history."""

    def __init__(self, conn_getter) -> None:
        self._get_conn = conn_getter

    async def get_processed_video_ids(self) -> set[str]:
        """Fetch all previously processed video IDs as a set for O(1) deduplication lookup."""
        conn: aiosqlite.Connection = self._get_conn()
        async with conn.execute("SELECT video_id FROM processed_videos") as cursor:
            rows = await cursor.fetchall()
            return {row[0] for row in rows}

    async def video_exists(self, video_id: str) -> bool:
        """Check whether a single video ID exists in the database."""
        conn: aiosqlite.Connection = self._get_conn()
        async with conn.execute(
            "SELECT 1 FROM processed_videos WHERE video_id = ? LIMIT 1",
            (video_id,),
        ) as cursor:
            row = await cursor.fetchone()
            return row is not None

    async def insert_video(
        self,
        *,
        video_id: str,
        title: str,
        channel_id: str,
        channel_title: str,
        published_at: str,
        view_count: int,
        view_velocity: float,
    ) -> None:
        """Insert video metadata (ON CONFLICT DO NOTHING)."""
        conn: aiosqlite.Connection = self._get_conn()
        await conn.execute(
            """
            INSERT INTO processed_videos
                (video_id, title, channel_id, channel_title,
                 published_at, view_count, view_velocity)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(video_id) DO NOTHING
            """,
            (video_id, title, channel_id, channel_title, published_at, view_count, view_velocity),
        )
        await conn.commit()

    async def save_analysis(
        self,
        *,
        video_id: str,
        provider: str,
        model: str,
        strategy_json: str,
    ) -> None:
        """Persist analysis result and update analysis_json backfill field."""
        conn: aiosqlite.Connection = self._get_conn()
        await conn.execute(
            """
            INSERT INTO analysis_history (video_id, provider, model, strategy_json)
            VALUES (?, ?, ?, ?)
            """,
            (video_id, provider, model, strategy_json),
        )
        await conn.execute(
            "UPDATE processed_videos SET analysis_json = ? WHERE video_id = ?",
            (strategy_json, video_id),
        )
        await conn.commit()

    async def get_recent_analyses(self, limit: int = 10) -> list[dict[str, Any]]:
        """Retrieve recent analysis history items with joined video details."""
        conn: aiosqlite.Connection = self._get_conn()
        async with conn.execute(
            """
            SELECT
                ah.id, ah.video_id, pv.title, pv.channel_title,
                ah.provider, ah.model, ah.strategy_json, ah.created_at
            FROM analysis_history ah
            JOIN processed_videos pv ON pv.video_id = ah.video_id
            ORDER BY ah.created_at DESC
            LIMIT ?
            """,
            (limit,),
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def get_stats(self) -> dict[str, int]:
        """Return total counts of processed videos and stored analysis histories."""
        conn: aiosqlite.Connection = self._get_conn()
        async with conn.execute("SELECT COUNT(*) FROM processed_videos") as cursor:
            row = await cursor.fetchone()
            videos_count = row[0] if row else 0

        async with conn.execute("SELECT COUNT(*) FROM analysis_history") as cursor:
            row = await cursor.fetchone()
            analyses_count = row[0] if row else 0

        return {"videos": videos_count, "analyses": analyses_count}