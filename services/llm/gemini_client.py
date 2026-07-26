"""Custom GapGPT / OpenAI-compatible API Provider implementation (Token Optimized & Fault-Tolerant)."""

from __future__ import annotations

import aiohttp
from loguru import logger

from services.llm.base_provider import BaseLLMProvider


class GeminiProvider(BaseLLMProvider):
    """Handles interactions with GapGPT / OpenAI-compatible REST APIs."""

    async def generate_strategy(self, user_prompt: str) -> str:
        api_key = self._s.active_llm_api_key.get_secret_value()
        base_url = getattr(self._s, "gemini_base_url", "https://api.gapgpt.app/v1").rstrip("/")
        url = f"{base_url}/chat/completions"
        model_name = self._s.active_llm_model

        # [TOKEN OPTIMIZATION]: Strict minified schema with word count limits
        minified_schema = '{"viral_score":0.0,"sentiment":{"positive_pct":0,"negative_pct":0,"neutral_pct":0,"dominant_emotion":"1-2 words in Persian","summary":"max 15 words in Persian"},"viral_hooks":[{"hook_type":"pattern_interrupt|curiosity_gap|emotional_trigger|social_proof|controversy","description":"max 15 words in Persian","confidence":0.0,"example_phrase":"short quote"}],"content_strategy_summary":"max 25 words in Persian","suggested_topics":["topic 1","topic 2"],"estimated_viral_potential":"low|medium|high|very_high"}'
        
        compact_system = f"{self.SYSTEM_PROMPT}\nCRITICAL: Write ALL text values in short Persian (Farsi). Keep explanations brief. Output EXACTLY this JSON format:\n{minified_schema}"

        payload = {
            "model": model_name,
            "messages": [
                {"role": "system", "content": compact_system},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": self._s.llm_temperature,
            "max_tokens": self._s.llm_max_tokens,
            "response_format": {"type": "json_object"},
        }

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        logger.debug("Dispatching optimized request to GapGPT url={url} model={model}", url=url, model=model_name)
        async with self._session.post(url, json=payload, headers=headers) as resp:
            if resp.status != 200:
                body = await resp.text()
                raise RuntimeError(f"GapGPT API error status={resp.status}: {body[:500]}")
            data = await resp.json()

        try:
            choice = data["choices"][0]
            message = choice.get("message", {})
            
            # 1. بررسی کلید اصلی content
            content = message.get("content")

            # 2. پشتیبانی از مدل‌های reasoning/thinking در صورت خالی بودن content
            if not content and "reasoning_content" in message:
                content = message.get("reasoning_content")

            # 3. ارزیابی نهایی رشته خروجی
            if not content or not str(content).strip():
                finish_reason = choice.get("finish_reason", "unknown")
                raise ValueError(f"Received empty content string from GapGPT (finish_reason={finish_reason})")

            return str(content).strip()

        except (KeyError, IndexError) as exc:
            raise RuntimeError(f"Malformed GapGPT response payload: {data}") from exc