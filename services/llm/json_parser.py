"""JSON extraction and normalization utilities for raw LLM text outputs."""

from __future__ import annotations

import json
import re
from typing import Any

from loguru import logger


def extract_json_payload(raw_text: str) -> dict[str, Any]:
    """Extract a valid dictionary from raw LLM text using layered fallback mechanisms."""
    if not raw_text or not raw_text.strip():
        raise ValueError("Cannot parse JSON from empty LLM response.")

    clean_text = raw_text.strip()

    # 1. Direct JSON parse (fast path with strict=False to allow literal control chars)
    try:
        data = json.loads(clean_text, strict=False)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        pass

    # 2. Extract from Markdown code fence (handling multi-block or trailing text)
    fence_pattern = re.compile(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", re.DOTALL | re.IGNORECASE)
    for match in fence_pattern.finditer(clean_text):
        try:
            data = json.loads(match.group(1).strip(), strict=False)
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError:
            continue

    # 3. Substring greedy extraction (first '{' to last '}')
    first_brace = clean_text.find("{")
    last_brace = clean_text.rfind("}")
    if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
        json_candidate = clean_text[first_brace : last_brace + 1]
        try:
            data = json.loads(json_candidate, strict=False)
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError:
            pass

    # 4. Fallback: Search for any valid balanced JSON object structure in response
    brace_matches = [m.start() for m in re.finditer(r"\{", clean_text)]
    for start in brace_matches:
        try:
            data = json.loads(clean_text[start : last_brace + 1], strict=False)
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError:
            continue

    logger.error(
        "Failed to parse JSON from LLM output (length={len}): {sample}",
        len=len(clean_text),
        sample=clean_text[:200],
    )
    raise ValueError("Could not extract valid JSON structure from LLM response.")