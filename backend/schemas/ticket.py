"""Ticket request/response schemas."""

from pydantic import BaseModel


class TicketCreate(BaseModel):
    title: str
    description: str
    priority: str = "medium"  # low, medium, high


class TicketResponse(BaseModel):
    id: str
    title: str
    description: str
    priority: str
    status: str
    routed_to: str | None = None
