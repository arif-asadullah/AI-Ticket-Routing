"""Dummy tickets API — CRUD backed by ArangoDB."""

from fastapi import APIRouter, HTTPException, Request

from backend.schemas.ticket import TicketCreate, TicketResponse

router = APIRouter(prefix="/api/tickets", tags=["tickets"])

DUMMY_TEAMS = ["Infrastructure", "Application Support", "Networking", "Security", "Database"]


@router.get("", response_model=list[TicketResponse])
async def list_tickets(request: Request):
    """List all tickets."""
    db = getattr(request.app.state, "arango_db", None)
    if db is None:
        raise HTTPException(503, "Database unavailable")

    collection = db.collection("tickets")
    tickets = []
    for doc in collection.all():
        tickets.append(TicketResponse(
            id=doc["_key"],
            title=doc["title"],
            description=doc["description"],
            priority=doc["priority"],
            status=doc["status"],
            routed_to=doc.get("routed_to"),
        ))
    return tickets


@router.post("", response_model=TicketResponse, status_code=201)
async def create_ticket(ticket: TicketCreate, request: Request):
    """Create a new ticket and auto-route it to a team."""
    db = getattr(request.app.state, "arango_db", None)
    if db is None:
        raise HTTPException(503, "Database unavailable")

    import hashlib
    # Dummy routing: hash the title to pick a team
    team_index = int(hashlib.md5(ticket.title.encode()).hexdigest(), 16) % len(DUMMY_TEAMS)
    routed_to = DUMMY_TEAMS[team_index]

    collection = db.collection("tickets")
    doc = collection.insert({
        "title": ticket.title,
        "description": ticket.description,
        "priority": ticket.priority,
        "status": "routed",
        "routed_to": routed_to,
    })

    return TicketResponse(
        id=doc["_key"],
        title=ticket.title,
        description=ticket.description,
        priority=ticket.priority,
        status="routed",
        routed_to=routed_to,
    )


@router.get("/{ticket_id}", response_model=TicketResponse)
async def get_ticket(ticket_id: str, request: Request):
    """Get a single ticket by ID."""
    db = getattr(request.app.state, "arango_db", None)
    if db is None:
        raise HTTPException(503, "Database unavailable")

    collection = db.collection("tickets")
    doc = collection.get(ticket_id)
    if doc is None:
        raise HTTPException(404, "Ticket not found")

    return TicketResponse(
        id=doc["_key"],
        title=doc["title"],
        description=doc["description"],
        priority=doc["priority"],
        status=doc["status"],
        routed_to=doc.get("routed_to"),
    )


@router.delete("/{ticket_id}", status_code=204)
async def delete_ticket(ticket_id: str, request: Request):
    """Delete a ticket."""
    db = getattr(request.app.state, "arango_db", None)
    if db is None:
        raise HTTPException(503, "Database unavailable")

    collection = db.collection("tickets")
    if not collection.has(ticket_id):
        raise HTTPException(404, "Ticket not found")
    collection.delete(ticket_id)
