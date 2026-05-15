"""Socket.IO manager for real-time ticket updates."""

import logging
import socketio

logger = logging.getLogger(__name__)

# Create async Socket.IO server
sio = socketio.AsyncServer(
    async_mode="asgi",
    cors_allowed_origins="*",
    logger=False,
    engineio_logger=False,
)

# ASGI app to mount on FastAPI
socket_app = socketio.ASGIApp(sio, socketio_path="/socket.io")


@sio.event
async def connect(sid, environ):
    logger.info("Socket.IO client connected: %s", sid)


@sio.event
async def disconnect(sid):
    logger.info("Socket.IO client disconnected: %s", sid)


async def emit_ticket_event(event: str, data: dict):
    """Emit a ticket event to all connected clients.

    Events: ticket:created, ticket:updated, ticket:resolved, ticket:deleted
    """
    try:
        await sio.emit(event, data)
        logger.info("Emitted %s for ticket %s", event, data.get("id", "?"))
    except Exception as exc:
        logger.warning("Failed to emit %s: %s", event, exc)
