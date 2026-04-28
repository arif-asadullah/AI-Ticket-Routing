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
    secondary_category: str | None = None
    priority: str
    status: str
    confidence_score: float | None = None
    ai_reasoning: str | None = None
    quality_score: str | None = None  # HIGH, MEDIUM, LOW
    classifier_votes: dict | None = None
    submitted_by: str | None = None
    routed_to: str | None = None
    suggested_resolution: list[str] | None = None
    resolution_effectiveness: float | None = None
    suggested_runbook: str | None = None
    recommended_expert: str | None = None
    created_at: str | None = None
    resolved_at: str | None = None
