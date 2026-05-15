"""Data-grounded chat endpoint — zero hallucination."""

import logging

from pydantic import BaseModel
from fastapi import APIRouter, Depends, Request

from backend.services.llm import chat
from backend.services.chat_intent import parse_intent
from backend.services.chat_data import fetch_chat_data, build_grounded_prompt, extract_entities
from backend.core.auth import require_any_authenticated

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/chat", tags=["chat"])


class ChatRequest(BaseModel):
    message: str
    history: list[dict] | None = None


class ChatResponse(BaseModel):
    reply: str
    model: str
    entities: list[dict] | None = None


GENERAL_SYSTEM_PROMPT = (
    "You are Mindy, DeskMind's AI assistant. You help with general IT questions.\n"
    "STRICT RULES:\n"
    "- If asked about specific tickets, teams, statuses, or data, say: "
    "'I don't have that information. Try asking about a specific ticket by ID (e.g., \"ticket #5\") "
    "or ask about a team or category.'\n"
    "- NEVER invent ticket IDs, team names, engineer names, or statuses.\n"
    "- You can help with general IT troubleshooting advice."
)


@router.post("", response_model=ChatResponse)
async def chat_endpoint(req: ChatRequest, request: Request, user: dict = Depends(require_any_authenticated)):
    """Data-grounded chat: parse intent → query DB → LLM formats answer."""
    from backend.core.config import settings

    db = getattr(request.app.state, "arango_db", None)

    intent = parse_intent(req.message)
    logger.info("Chat intent: %s | entities: %s | user: %s", intent["intent"], intent["entities"], user["email"])

    # ── Data-grounded path ──
    if intent["intent"] != "general_it" and db:
        result = await fetch_chat_data(intent, db, user)

        if not result["found"]:
            return ChatResponse(reply=result["summary"], model="database", entities=None)

        # Extract entities for frontend chips
        ents = extract_entities(intent, result["data"])

        # Build grounded prompt → LLM formats answer
        system_prompt = build_grounded_prompt(intent, result["data"])
        reply = await chat(req.message, history=[
            {"role": "system", "content": system_prompt},
            *(req.history or []),
        ])
        return ChatResponse(reply=reply, model=settings.OLLAMA_MODEL, entities=ents if ents else None)

    # ── General IT path (no DB intent) ──
    reply = await chat(req.message, history=[
        {"role": "system", "content": GENERAL_SYSTEM_PROMPT},
        *(req.history or []),
    ])
    return ChatResponse(reply=reply, model=settings.OLLAMA_MODEL, entities=None)
