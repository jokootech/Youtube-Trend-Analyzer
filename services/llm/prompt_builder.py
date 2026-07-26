"""User prompt construction logic for YouTube strategy extraction (Token Optimized)."""

from __future__ import annotations

from services.llm.token_optimizer import compact_metadata_prompt


def build_analysis_prompt(
    title: str,
    channel: str,
    view_count: int,
    velocity: float,
    like_count: int,
    comment_count: int,
    hours_old: float,
    comments: list[str],
) -> str:
    """Build a compact, token-optimized text prompt incorporating video metrics and top comments."""
    
    # استفاده از ماژول بهینه‌ساز توکن برای فشرده‌سازی حداکثری
    compact_data = compact_metadata_prompt(
        title=title,
        channel=channel,
        view_count=view_count,
        velocity=velocity,
        like_count=like_count,
        comment_count=comment_count,
        hours_old=hours_old,
        comments=comments,
    )

    return f"""\
Analyze the following YouTube video and produce a viral content strategy.

{compact_data}

Respond with the JSON strategy proposal matching the required schema."""