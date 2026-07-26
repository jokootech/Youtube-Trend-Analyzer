"""Pydantic schemas for LLM viral strategy output validation (Fault-Tolerant & Production Ready)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


class ViralHook(BaseModel):
    """A single viral hook identified by the LLM with fallback validation."""

    hook_type: Literal["pattern_interrupt", "curiosity_gap", "emotional_trigger", "social_proof", "controversy"] = "pattern_interrupt"
    description: str = Field(default="", min_length=1, max_length=1000)
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)
    example_phrase: str = Field(default="")

    @field_validator("confidence", mode="before")
    @classmethod
    def _normalize_confidence(cls, v: Any) -> float:
        """Converts percentage inputs (e.g. 30.0 or 85) to a standard float between 0.0 and 1.0."""
        try:
            val = float(v)
            if val > 1.0:
                val = val / 100.0
            return max(0.0, min(1.0, val))
        except (ValueError, TypeError):
            return 0.8

    @field_validator("hook_type", mode="before")
    @classmethod
    def _validate_hook_type(cls, v: str) -> str:
        valid_types = {"pattern_interrupt", "curiosity_gap", "emotional_trigger", "social_proof", "controversy"}
        if isinstance(v, str) and v.lower() in valid_types:
            return v.lower()
        return "pattern_interrupt"  # مقدار جایگزین امن در صورت عدم تطابق دقیق


class SentimentBreakdown(BaseModel):
    """Sentiment distribution across the top comments."""

    positive_pct: float = Field(default=0.0, ge=0.0, le=100.0)
    negative_pct: float = Field(default=0.0, ge=0.0, le=100.0)
    neutral_pct: float = Field(default=0.0, ge=0.0, le=100.0)
    dominant_emotion: str = Field(default="خنثی")
    summary: str = Field(default="تحلیل احساسات ثبت نشده است.")


class VideoGenPrompt(BaseModel):
    """Structured prompt tailored for generative video AI models."""

    target_platform: str = Field(default="YouTube Shorts")
    visual_concept: str = Field(default="")
    scene_description: str = Field(default="")
    pacing_style: str = Field(default="dynamic")
    suggested_duration_seconds: int = Field(default=30, ge=5, le=600)
    audio_mood: str = Field(default="upbeat electronic")
    text_overlay: str = Field(default="")


class StrategyProposal(BaseModel):
    """Validated strategy proposal output from the LLM engine."""

    video_id: str = Field(default="")
    title: str = Field(default="")
    viral_score: float = Field(default=50.0, ge=0.0, le=100.0)
    sentiment: SentimentBreakdown = Field(default_factory=SentimentBreakdown)
    viral_hooks: list[ViralHook] = Field(default_factory=list)
    content_strategy_summary: str = Field(default="استراتژی خاصی ثبت نشده است.")
    suggested_topics: list[str] = Field(default_factory=list)
    video_gen_prompts: list[VideoGenPrompt] = Field(default_factory=list)
    estimated_viral_potential: Literal["low", "medium", "high", "very_high"] = "medium"
    recommended_posting_time_est: str = Field(default="")
    recommended_posting_time_irst: str = Field(default="")

    @field_validator("sentiment", mode="before")
    @classmethod
    def _validate_sentiment(cls, v: Any) -> Any:
        """Handles missing, None, or invalid sentiment payload gracefully."""
        if not v or not isinstance(v, dict):
            return SentimentBreakdown()
        return v

    @field_validator("viral_score", mode="before")
    @classmethod
    def _validate_viral_score(cls, v: Any) -> float:
        """Safely parse viral_score float input."""
        try:
            val = float(v)
            return max(0.0, min(100.0, val))
        except (ValueError, TypeError):
            return 50.0

    @field_validator("estimated_viral_potential", mode="before")
    @classmethod
    def _validate_potential(cls, v: str) -> str:
        valid_potentials = {"low", "medium", "high", "very_high"}
        if isinstance(v, str) and v.lower() in valid_potentials:
            return v.lower()
        return "medium"  # مقدار جایگزین امن

    @field_validator("viral_hooks")
    @classmethod
    def _limit_hooks(cls, v: list[ViralHook]) -> list[ViralHook]:
        return v[:5] if v else [ViralHook()]


@dataclass(slots=True)
class AnalysisResult:
    """Container holding video metadata alongside its validated strategy proposal."""

    video_id: str
    title: str
    channel_title: str
    view_count: int
    view_velocity: float
    published_at: str
    proposal: StrategyProposal