"""Telegram Card Formatter with Enterprise Tier Badge & Clean RTL Layout."""

from __future__ import annotations

from datetime import datetime, timezone
from html import escape

from services.llm.schemas import AnalysisResult
from services.notifier.timezone_utils import format_dual_timestamp

HOOK_MAP = {
    "pattern_interrupt": "توقف الگوی بصری",
    "curiosity_gap": "شکاف کنجکاوی",
    "emotional_trigger": "تحریک احساسی",
    "social_proof": "تایید اجتماعی",
    "controversy": "جنجالی / مباحثه‌برانگیز",
}

POTENTIAL_MAP = {
    "low": "کم ⚪",
    "medium": "متوسط 🟡",
    "high": "بالا 🟠",
    "very_high": "بسیار بالا 🔥",
}


def _parse_published_at(pub_raw: str | datetime) -> datetime:
    if isinstance(pub_raw, datetime):
        return pub_raw
    try:
        return datetime.fromisoformat(str(pub_raw))
    except Exception:
        return datetime.now(timezone.utc)


def _get_time_ago_persian(pub_dt: datetime) -> str:
    if pub_dt.tzinfo is None:
        pub_dt = pub_dt.replace(tzinfo=timezone.utc)
    
    diff = datetime.now(timezone.utc) - pub_dt
    seconds = max(int(diff.total_seconds()), 1)
    minutes, hours, days = seconds // 60, seconds // 3600, seconds // 86400

    if days > 0:
        return f"{days} روز پیش"
    if hours > 0:
        return f"{hours} ساعت و {minutes % 60} دقیقه پیش"
    if minutes > 0:
        return f"{minutes} دقیقه پیش"
    return "چند لحظه پیش"


def _get_tier_badge(views: int, velocity: float) -> str:
    """Classifies video into Mega Viral, Breakout, or High Trend tier adaptively."""
    # استاندارد ترکیبی (پوشش فارسی و انگلیسی)
    if views >= 1000000 or (views >= 100000 and velocity >= 2000):
        return "🚀 <b>[مگا وایرال / نرخ رشد فوق‌العاده]</b>"
    if views >= 10000 or velocity >= 300:
        return "⚡ <b>[پدیده BREAKOUT / جهش ترند]</b>"
    return "📈 <b>[ترند پررشد]</b>"


def _get_attr_or_str(obj: object) -> str:
    return str(obj.value) if hasattr(obj, "value") else str(obj)


def build_analysis_html_card(result: AnalysisResult) -> str:
    p = result.proposal
    s = p.sentiment

    pub_dt = _parse_published_at(result.published_at)
    ts_formatted = format_dual_timestamp(pub_dt)
    time_ago = _get_time_ago_persian(pub_dt)
    tier_badge = _get_tier_badge(result.view_count, result.view_velocity)

    raw_pot = _get_attr_or_str(p.estimated_viral_potential).lower()
    pot_str = POTENTIAL_MAP.get(raw_pot, raw_pot)

    lines = [
        f"{tier_badge}",
        f"⏱ زمان انتشار: <b>{time_ago}</b> (<code>{escape(ts_formatted)}</code>)\n",
        f"🎬 <b>{escape(result.title)}</b>",
        f"👤 کانال: <b>{escape(result.channel_title)}</b>",
        f"👁 بازدید: <b>{result.view_count:,}</b> | سرعت: <b>{result.view_velocity:,.1f}</b> بازدید/ساعت",
        f"🔗 <a href='https://youtube.com/watch?v={result.video_id}'>تماشای ویدیو در یوتیوب</a>\n",
        f"📊 پتانسیل وایرال: <b>{pot_str}</b> (امتیاز: {p.viral_score}/100)\n",
        f"💭 <b>تحلیل احساسات مخاطبان:</b>",
        f"🟢 {s.positive_pct}%  🟡 {s.neutral_pct}%  🔴 {s.negative_pct}% | حس غالب: <b>{escape(s.dominant_emotion)}</b>",
        f"<i>{escape(s.summary)}</i>\n",
        f"📌 <b>هوک‌های وایرال شناسایی‌شده:</b>",
    ]

    for i, hook in enumerate(p.viral_hooks, 1):
        raw_h = _get_attr_or_str(hook.hook_type).lower()
        h_type = HOOK_MAP.get(raw_h, raw_h)

        lines.append(f"<b>{i}. {escape(h_type)}</b> ({int(hook.confidence * 100)}%)")
        lines.append(f"└ {escape(hook.description)}")
        if hook.example_phrase:
            lines.append(f"└ <i>«{escape(hook.example_phrase)}»</i>")

    lines.extend([
        f"\n🎯 <b>استراتژی پیشنهادی محتوا:</b>",
        f"{escape(p.content_strategy_summary)}\n",
    ])

    if p.suggested_topics:
        lines.append("🏷 <b>ایده‌های موضوعی مرتبط:</b>")
        for topic in p.suggested_topics[:4]:
            lines.append(f"• {escape(topic)}")

    return "\n".join(lines)