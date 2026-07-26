"""Data models for YouTube scrapers."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(slots=True)
class VideoMeta:
    """Canonical video metadata produced by the scraper pipeline."""

    video_id: str
    title: str
    channel_id: str
    channel_title: str
    published_at: datetime
    view_count: int
    like_count: int
    comment_count: int
    view_velocity: float = 0.0
    top_comments: list[str] = field(default_factory=list)
    rss_source: str = ""  # topic keyword or channel ID that surfaced this video