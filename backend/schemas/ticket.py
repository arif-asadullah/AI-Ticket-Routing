"""Ticket request/response schemas."""

from pydantic import BaseModel


class TicketCreate(BaseModel):
    title: str
    description: str
    priority: str = "medium"  # critical, high, medium, low
    submitted_by: str | None = None


class TicketStatusUpdate(BaseModel):
    status: str  # in_progress, escalated, routed
    assigned_to: str | None = None  # team name (for manual reassignment)
    updated_by: str | None = None  # engineer email


class TicketResolve(BaseModel):
    resolution_steps: list[str]  # what was done to fix it
    used_ai_suggestion: str = "no"  # "yes", "partially", "no"
    used_runbook: str | None = None  # "KB-0001" or null
    resolved_by: str | None = None  # engineer email


class TicketEnrich(BaseModel):
    answers: dict  # {"server": "prod-db-01", "error": "Connection refused", ...}


class TicketOverride(BaseModel):
    category: str  # new classification category
    priority: str | None = None  # optional priority change
    reason: str  # required justification


class TicketFeedback(BaseModel):
    rating: str  # "helpful", "not_helpful"
    comment: str | None = None


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
    override: dict | None = None
    top3_predictions: list[dict] | None = None
    sla_deadline: str | None = None
    sla_hours: int | None = None
    enrichment: dict | None = None
    picked_up_by: str | None = None
    created_at: str | None = None
    resolved_at: str | None = None
