"""
Authentication & Authorization — JWT tokens, password hashing, FastAPI dependencies.

Usage in endpoints:
    from backend.core.auth import get_current_user, require_admin, require_team_access

    @router.get("/protected")
    async def protected(user: dict = Depends(get_current_user)):
        ...

    @router.delete("/admin-only")
    async def admin_only(user: dict = Depends(require_admin)):
        ...
"""

import logging
from datetime import datetime, timedelta, timezone

import bcrypt as _bcrypt
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from backend.core.config import settings

logger = logging.getLogger(__name__)

# ── Password Hashing ──


def hash_password(plain: str) -> str:
    """Hash a plaintext password using bcrypt."""
    return _bcrypt.hashpw(plain.encode(), _bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    """Verify a plaintext password against a bcrypt hash."""
    return _bcrypt.checkpw(plain.encode(), hashed.encode())


# ── JWT Token Creation ──

def create_access_token(data: dict) -> str:
    """Create a short-lived access token (default 30 min)."""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire, "type": "access"})
    return jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_refresh_token(data: dict) -> str:
    """Create a long-lived refresh token (default 7 days)."""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "type": "refresh"})
    return jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_token(token: str) -> dict:
    """Decode and validate a JWT. Raises JWTError on failure."""
    return jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])


# ── FastAPI Dependencies ──

bearer_scheme = HTTPBearer()


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> dict:
    """Extract and validate the current user from the JWT bearer token.

    Returns the full user document from ArangoDB (not just token claims).
    This ensures deactivated users are rejected immediately.
    """
    try:
        payload = decode_token(credentials.credentials)
        if payload.get("type") != "access":
            raise HTTPException(401, "Invalid token type")
        email = payload.get("sub")
        if email is None:
            raise HTTPException(401, "Invalid token")
    except JWTError:
        raise HTTPException(401, "Invalid or expired token")

    db = getattr(request.app.state, "arango_db", None)
    if db is None:
        raise HTTPException(503, "Database unavailable")

    cursor = db.aql.execute(
        "FOR u IN users FILTER u.email == @email LIMIT 1 RETURN u",
        bind_vars={"email": email},
    )
    user = next(cursor, None)
    if user is None or not user.get("is_active"):
        raise HTTPException(401, "User not found or deactivated")

    return user


def require_role(*allowed_roles: str):
    """Factory that returns a FastAPI dependency requiring one of the allowed roles.

    Usage:
        @router.get("/admin-only")
        async def admin_only(user: dict = Depends(require_role("admin"))):
            ...
    """
    async def checker(user: dict = Depends(get_current_user)) -> dict:
        if user["role"] not in allowed_roles:
            raise HTTPException(403, f"Requires one of: {', '.join(allowed_roles)}")
        return user
    return checker


# ── Convenience Aliases ──

require_admin = require_role("admin")
require_engineer_or_admin = require_role("admin", "engineer")
require_any_authenticated = require_role("admin", "engineer", "user")


# ── Team Access Check ──

async def require_team_access(ticket_routed_to: str | None, user: dict, db) -> bool:
    """Check that an engineer belongs to the team that owns the ticket.

    - Admins bypass this check (can access any ticket).
    - Viewers are denied (cannot modify tickets).
    - Engineers must belong to the ticket's routed team.

    This is called inline within endpoint bodies (not as a route-level Depends)
    because it needs the ticket's routed_to value, which is only known after
    fetching the ticket from the database.
    """
    if user["role"] == "admin":
        return True
    if user["role"] == "user":
        raise HTTPException(403, "Viewers cannot modify tickets")

    # Resolve engineer's team_key to team name
    user_team_name = None
    team_key = user.get("team_key")
    if team_key:
        team_doc = db.collection("teams").get(team_key)
        if team_doc:
            user_team_name = team_doc.get("name")

    if user_team_name != ticket_routed_to:
        raise HTTPException(403, "You can only access tickets assigned to your team")
    return True
