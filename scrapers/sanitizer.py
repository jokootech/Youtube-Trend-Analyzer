"""Text sanitization and string parsing utilities for YouTube scraping."""

from __future__ import annotations

import re

_URL_RE = re.compile(r"https?://\S+", re.IGNORECASE)
_EMOJI_RE = re.compile(
    r"["
    r"\U0001F600-\U0001F64F"  # emoticons
    r"\U0001F300-\U0001F5FF"  # symbols & pictographs
    r"\U0001F680-\U0001F6FF"  # transport & map
    r"\U0001F1E0-\U0001F1FF"  # flags
    r"\U00002702-\U000027B0"
    r"\U000024C2-\U0001F251"
    r"\U0001f926-\U0001f937"
    r"\U00010000-\U0010ffff"
    r"\u2640-\u2642"
    r"\u2600-\u2B55"
    r"\u200d\u23cf\u23e9\u231a\ufe0f\u3030"
    r"]+",
    flags=re.UNICODE,
)


def sanitize_comment(text: str, max_chars: int = 500) -> str:
    """Strip URLs, collapse excessive emojis, and truncate comments safely."""
    cleaned = _URL_RE.sub("[LINK]", text.strip())
    cleaned = _EMOJI_RE.sub("", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    if len(cleaned) > max_chars:
        cleaned = cleaned[:max_chars].rsplit(" ", 1)[0]
    return cleaned


def extract_video_id(url_or_id: str) -> str | None:
    """Extract an 11-char video ID from a YouTube URL or return string if valid."""
    match = re.search(r"(?:v=|/embed/|/v/|youtu\.be/)([\w-]{11})", url_or_id)
    if match:
        return match.group(1)
    if len(url_or_id) == 11 and re.match(r"^[\w-]+$", url_or_id):
        return url_or_id
    return None