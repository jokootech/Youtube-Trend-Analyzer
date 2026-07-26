"""OpenAI API Provider implementation."""

from __future__ import annotations

import aiohttp
from loguru import logger

from services.llm.base_provider import BaseLLMProvider


class OpenAIProvider(BaseLLMProvider):
    """Handles interactions with OpenAI Chat Completions API."""

    async def generate_strategy(self, user_prompt: str) -> str:
        api_key = self._s.openai_api_key.get_secret_value()
        model_name = self._s.openai_model
        url = "https://api.openai.com/v1/chat/completions"

        payload = {
            "model": model_name,
            "messages": [
                {"role": "system", "content": self.SYSTEM_PROMPT},
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

        logger.debug("Dispatching request to OpenAI API model={model}", model=model_name)
        async with self._session.post(url, json=payload, headers=headers) as resp:
            if resp.status != 200:
                body = await resp.text()
                raise RuntimeError(f"OpenAI API error status={resp.status}: {body[:500]}")
            data = await resp.json()

        try:
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError) as exc:
            raise RuntimeError(f"Malformed OpenAI API response payload: {data}") from exc