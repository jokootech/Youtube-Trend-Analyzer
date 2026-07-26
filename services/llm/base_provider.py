"""Abstract Base Class for LLM Providers."""

from __future__ import annotations

from abc import ABC, abstractmethod

import aiohttp

from config.settings import Settings


class BaseLLMProvider(ABC):
    """Interface defining requirements for LLM API integrations."""

    SYSTEM_PROMPT: str = """\
You are an expert YouTube content strategist and viral marketing analyst. \
Given video metadata and top comments, produce a JSON object that follows \
the schema exactly. Be analytical, concise, and actionable.

Key analysis dimensions:
1. **Viral Score** (0-100): Based on view velocity, engagement ratio, comment sentiment.
2. **Sentiment**: Analyse the provided comments and estimate positive/negative/neutral percentages.
3. **Viral Hooks**: Identify 1-5 specific techniques used in the title/thumbnail/content.
4. **Content Strategy**: Write a 2-3 sentence actionable strategy for creating derivative content.
5. **Video Generation Prompts**: Create 1-3 detailed prompts suitable for AI video generators (Veo, Sora, Runway) that could capture similar virality.
6. **Suggested Topics**: 3-5 related topic ideas for future content.
7. **Viral Potential**: Classify as low/medium/high/very_high.
8. **Posting Time**: Suggest optimal posting time in US Eastern (EST/EDT) and its IRST equivalent.

You MUST respond with valid JSON only. No markdown, no explanation outside the JSON."""

    def __init__(self, settings: Settings, session: aiohttp.ClientSession) -> None:
        self._s = settings
        self._session = session

    @abstractmethod
    async def generate_strategy(self, user_prompt: str) -> str:
        """Send prompt to the model and return raw text response."""
        pass