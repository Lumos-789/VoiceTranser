"""Prompt refinement — transforms verbose speech transcript into structured prompt via MiniMax-M3."""

from __future__ import annotations

import sys

from anthropic import Anthropic

# Skip refinement if transcript is already concise
_MIN_LENGTH_FOR_REFINE = 50


def refine(
    transcript: str,
    api_key: str,
    base_url: str = "https://api.minimaxi.com/anthropic",
    model: str = "MiniMax-M3",
    system_prompt: str = "",
) -> str:
    """Refine a verbose speech transcript into a structured prompt.

    Returns the refined prompt, or the original transcript if it's already concise.
    """
    if not transcript:
        return ""

    # Skip refinement for short, already-concise transcripts
    if len(transcript) < _MIN_LENGTH_FOR_REFINE:
        return transcript

    if not system_prompt:
        from voicetranser.config import _PROMPTS_DIR

        system_prompt = (_PROMPTS_DIR / "refine_system.txt").read_text(encoding="utf-8").strip()

    client = Anthropic(api_key=api_key, base_url=base_url)

    try:
        response = client.messages.create(
            model=model,
            max_tokens=2048,
            system=system_prompt,
            messages=[
                {"role": "user", "content": transcript},
            ],
        )
        # MiniMax-M3 may return ThinkingBlock + TextBlock, only extract text
        for block in response.content:
            if block.type == "text":
                result = block.text.strip()
                if result:
                    return result
        return transcript
    except Exception as e:
        sys.stderr.write(f"[Refiner error: {e}]\n")
        return transcript
