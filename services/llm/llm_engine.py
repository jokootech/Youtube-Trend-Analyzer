"""LLM Engine Orchestrator and Facade with automatic provider fallback."""

from __future__ import annotations

import aiohttp
from loguru import logger

from config.settings import Settings, get_settings
from services.llm.base_provider import BaseLLMProvider
from services.llm.gemini_client import GeminiProvider
from services.llm.json_parser import extract_json_payload
from services.llm.schemas import StrategyProposal


class LLMEngine:
    """Async coordinator for multi-provider LLM analysis and Pydantic validation."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._s = settings or get_settings()
        self._session: aiohttp.ClientSession | None = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self._s.llm_request_timeout),
            )
        return self._session

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None

    def _get_providers(self, session: aiohttp.ClientSession) -> list[BaseLLMProvider]:
        """Return prioritized list of LLM providers safely."""
        gemini = GeminiProvider(self._s, session)
        # Only add OpenAI if key is actually provided
        if self._s.openai_api_key:
            from services.llm.openai_client import OpenAIProvider
            openai = OpenAIProvider(self._s, session)
            return [gemini, openai]
        return [gemini]

    async def analyze_video(
        self,
        video_id: str,
        title: str,
        channel_title: str,
        view_count: int,
        like_count: int,
        comment_count: int,
        velocity: float,
        hours_old: float,
        comments: list[str],
    ) -> StrategyProposal:
        """Run analysis pipeline: build prompt -> query provider (with fallback) -> validate JSON."""
        session = await self._get_session()
        
        # Build optimized prompt
        from services.llm.prompt_builder import build_analysis_prompt
        user_prompt = build_analysis_prompt(
            title=title,
            channel=channel_title,
            view_count=view_count,
            velocity=velocity,
            like_count=like_count,
            comment_count=comment_count,
            hours_old=hours_old,
            comments=comments,
        )

        providers = self._get_providers(session)
        last_exception: Exception | None = None
        validated_proposal: StrategyProposal | None = None

        for provider in providers:
            provider_name = provider.__class__.__name__
            try:
                logger.info(
                    "Attempting LLM strategy generation provider={provider} video={vid}",
                    provider=provider_name,
                    vid=video_id[:8],
                )
                raw_response = await provider.generate_strategy(user_prompt)
                
                if not raw_response:
                    raise ValueError("Received empty string from LLM provider")

                # Parsing and Pydantic Schema Validation inside loop to allow fallback if validation fails
                raw_dict = extract_json_payload(raw_response)
                raw_dict.setdefault("video_id", video_id)
                raw_dict.setdefault("title", title)

                validated_proposal = StrategyProposal.model_validate(raw_dict)
                break  # Fully successful, exit loop

            except Exception as exc:
                logger.warning(
                    "LLM provider failed provider={provider} video={vid} error={error!r}",
                    provider=provider_name,
                    vid=video_id[:8],
                    error=exc,
                )
                last_exception = exc

        if validated_proposal is None:
            raise RuntimeError(
                f"All configured LLM providers failed for video {video_id[:8]} | Last error: {last_exception!r}"
            ) from last_exception

        logger.info(
            "LLM analysis completed and validated video={vid} viral_score={score} potential={pot}",
            vid=video_id[:8],
            score=validated_proposal.viral_score,
            pot=validated_proposal.estimated_viral_potential,
        )
        return validated_proposal