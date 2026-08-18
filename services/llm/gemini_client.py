"""Gemini LLM provider using Google's official OpenAI-compatible API."""

from __future__ import annotations

from services.llm.base_provider import BaseLLMProvider


class GeminiProvider(BaseLLMProvider):
    """Handles requests to Google's official Gemini API."""

    async def generate_strategy(self, user_prompt: str) -> str:
        api_key = self._s.gemini_api_key.get_secret_value()

        base_url = (
            getattr(
                self._s,
                "gemini_base_url",
                "https://generativelanguage.googleapis.com/v1beta/openai",
            )
            .rstrip("/")
        )

        url = f"{base_url}/chat/completions"

        model_name = self._s.gemini_model

        minified_schema = (
            '{"viral_score":0.0,'
            '"sentiment":{'
            '"positive_pct":0,'
            '"negative_pct":0,'
            '"neutral_pct":0,'
            '"dominant_emotion":"1-2 words in Persian",'
            '"summary":"max 15 words in Persian"},'
            '"viral_hooks":['
            '{"hook_type":"pattern_interrupt|curiosity_gap|'
            'emotional_trigger|social_proof|controversy",'
            '"description":"max 15 words in Persian",'
            '"confidence":0.0,'
            '"example_phrase":"short quote"}'
            '],'
            '"content_strategy_summary":"max 25 words in Persian",'
            '"suggested_topics":["topic 1","topic 2"],'
            '"estimated_viral_potential":"low|medium|high|very_high"}'
        )

        compact_system = (
            f"{self.SYSTEM_PROMPT}\n"
            "CRITICAL: Write ALL text values in short Persian (Farsi). "
            "Keep explanations brief. "
            "Output EXACTLY this JSON format:\n"
            f"{minified_schema}"
        )

        payload = {
            "model": model_name,
            "messages": [
                {
                    "role": "system",
                    "content": compact_system,
                },
                {
                    "role": "user",
                    "content": user_prompt,
                },
            ],
            "temperature": self._s.llm_temperature,
            "max_tokens": self._s.llm_max_tokens,
            "response_format": {
                "type": "json_object",
            },
        }

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        async with self._session.post(
            url,
            json=payload,
            headers=headers,
        ) as resp:

            body = await resp.text()

            if resp.status != 200:
                raise RuntimeError(
                    f"Gemini API error status={resp.status}: "
                    f"{body[:1000]}"
                )

            try:
                data = await resp.json()
            except Exception as exc:
                raise RuntimeError(
                    f"Gemini API returned invalid JSON: {body[:1000]}"
                ) from exc

        try:
            choice = data["choices"][0]
            message = choice.get("message", {})

            content = message.get("content")

            if not content and "reasoning_content" in message:
                content = message.get("reasoning_content")

            if not content or not str(content).strip():
                finish_reason = choice.get(
                    "finish_reason",
                    "unknown",
                )

                raise ValueError(
                    "Gemini returned empty content "
                    f"(finish_reason={finish_reason})"
                )

            return str(content).strip()

        except (KeyError, IndexError, TypeError) as exc:
            raise RuntimeError(
                f"Malformed Gemini response payload: {data}"
            ) from exc
