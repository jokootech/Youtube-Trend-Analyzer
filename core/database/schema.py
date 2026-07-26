"""Database schema and migration definitions for SQLite."""

from __future__ import annotations

INIT_SCHEMA_SQL = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS processed_videos (
    video_id        TEXT PRIMARY KEY,
    title           TEXT NOT NULL,
    channel_id      TEXT,
    channel_title   TEXT,
    published_at    TEXT NOT NULL,
    view_count      INTEGER DEFAULT 0,
    view_velocity   REAL    DEFAULT 0.0,
    fetched_at      TEXT NOT NULL DEFAULT (datetime('now')),
    analysis_json   TEXT
);

CREATE INDEX IF NOT EXISTS idx_processed_videos_published
    ON processed_videos(published_at);

CREATE INDEX IF NOT EXISTS idx_processed_videos_velocity
    ON processed_videos(view_velocity DESC);

CREATE TABLE IF NOT EXISTS analysis_history (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    video_id        TEXT NOT NULL REFERENCES processed_videos(video_id),
    provider        TEXT NOT NULL,
    model           TEXT NOT NULL,
    strategy_json   TEXT NOT NULL,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_analysis_history_video
    ON analysis_history(video_id);
"""