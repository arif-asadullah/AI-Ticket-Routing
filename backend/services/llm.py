"""Ollama LLM client for chat and classification."""

import logging

import httpx

from backend.core.config import settings

logger = logging.getLogger(__name__)

TIMEOUT = 120.0  # LLM responses can be slow on CPU


async def chat(message: str, history: list[dict] | None = None) -> str:
    """Send a message to Ollama and return the response text."""
    messages = []
    if history:
        messages.extend(history)
    messages.append({"role": "user", "content": message})

    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            resp = await client.post(
                f"{settings.OLLAMA_BASE_URL}/v1/chat/completions",
                json={
                    "model": settings.OLLAMA_MODEL,
                    "messages": messages,
                    "temperature": 0.7,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]
    except httpx.ConnectError:
        logger.warning("Ollama not reachable at %s", settings.OLLAMA_BASE_URL)
        return "Error: Ollama is not running. Start it with `open /Applications/Ollama.app`"
    except Exception as exc:
        logger.error("LLM error: %s", exc)
        return f"Error: {exc}"
