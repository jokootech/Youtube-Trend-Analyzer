"""Token Optimization utilities for reducing LLM payload size."""

from __future__ import annotations


def compact_metadata_prompt(
    title: str,
    channel: str,
    view_count: int,
    velocity: float,
    like_count: int,
    comment_count: int,
    hours_old: float,
    comments: list[str],
) -> str:
    """Build a token-minimized prompt payload for the LLM."""
    
    # 1. Select max 10 top comments and format compactly
    top_10 = comments[:10]
    comments_str = "\n".join(f"- {c}" for c in top_10) if top_10 else "N/A"

    # 2. Ultra-dense Markdown format (zero fluff)
    return f"""\
[VIDEO METADATA]
Title: {title}
Channel: {channel}
Views: {view_count} | Velocity: {velocity:.1f} v/h | Hours: {hours_old:.1f}
Stats: Likes={like_count}, Comments={comment_count}

[TOP COMMENTS]
{comments_str}"""