"""Ticket request/response schemas."""

from pydantic import BaseModel


class TicketCreate(BaseModel):
    title: str
    description: str
    priority: str = "medium"  # critical, high, medium, low
    submitted_by: str | None = None


class TicketResponse(BaseModel):
    id: str
    title: str
    description: str
    category: str | None = None
    priority: str
    status: str
    confidence_score: float | None = None
    ai_reasoning: str | None = None
    submitted_by: str | None = None
    routed_to: str | None = None
    created_at: str | None = None
    resolved_at: str | None = None
