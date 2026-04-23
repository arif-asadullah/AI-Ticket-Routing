"""Chat endpoint — simple proxy to Ollama for testing."""

from pydantic import BaseModel
from fastapi import APIRouter

from backend.services.llm import chat

router = APIRouter(prefix="/api/chat", tags=["chat"])


class ChatRequest(BaseModel):
    message: str
    history: list[dict] | None = None


class ChatResponse(BaseModel):
    reply: str
    model: str


@router.post("", response_model=ChatResponse)
async def chat_endpoint(req: ChatRequest):
    """Send a message to the local LLM and get a response."""
    from backend.core.config import settings

    reply = await chat(req.message, req.history)
    return ChatResponse(reply=reply, model=settings.OLLAMA_MODEL)
