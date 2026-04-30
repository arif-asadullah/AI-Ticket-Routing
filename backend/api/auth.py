"""Auth API — register, login, refresh, me, bootstrap."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request

from backend.core.auth import (
    create_access_token,
    create_refresh_token,
    decode_token,
    get_current_user,
    hash_password,
    require_admin,
    verify_password,
)
from backend.schemas.auth import (
    TokenRefreshRequest,
    TokenResponse,
    UserLogin,
    UserRegister,
    UserResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["auth"])

VALID_ROLES = {"admin", "engineer", "viewer"}


def _get_db(request: Request):
    """Get ArangoDB handle from app state."""
    db = getattr(request.app.state, "arango_db", None)
    if db is None:
        raise HTTPException(503, "Database unavailable")
    return db


@router.post("/bootstrap", response_model=TokenResponse)
async def bootstrap(body: UserRegister, request: Request):
    """Create the first admin account. Only works when zero users exist."""
    db = _get_db(request)

    count = db.collection("users").count()
    if count > 0:
        raise HTTPException(403, "Bootstrap is disabled — users already exist")

    if body.role != "admin":
        raise HTTPException(400, "First user must be admin")

    doc = db.collection("users").insert({
        "email": body.email,
        "password_hash": hash_password(body.password),
        "role": "admin",
        "engineer_key": None,
        "team_key": None,
        "is_active": True,
    })

    token_data = {"sub": body.email, "role": "admin", "team_key": None}
    logger.info("Bootstrap: admin account created for %s", body.email)

    return TokenResponse(
        access_token=create_access_token(token_data),
        refresh_token=create_refresh_token(token_data),
    )


@router.post("/login", response_model=TokenResponse)
async def login(body: UserLogin, request: Request):
    """Authenticate with email + password, returns JWT tokens."""
    db = _get_db(request)

    cursor = db.aql.execute(
        "FOR u IN users FILTER u.email == @email LIMIT 1 RETURN u",
        bind_vars={"email": body.email},
    )
    user = next(cursor, None)

    if user is None or not verify_password(body.password, user["password_hash"]):
        raise HTTPException(401, "Invalid email or password")

    if not user.get("is_active"):
        raise HTTPException(403, "Account is deactivated")

    token_data = {
        "sub": user["email"],
        "role": user["role"],
        "team_key": user.get("team_key"),
    }

    logger.info("Login: %s (role=%s, team=%s)", user["email"], user["role"], user.get("team_key"))

    return TokenResponse(
        access_token=create_access_token(token_data),
        refresh_token=create_refresh_token(token_data),
    )


@router.post("/register", response_model=UserResponse, status_code=201)
async def register(
    body: UserRegister,
    request: Request,
    admin: dict = Depends(require_admin),
):
    """Create a new user account. Admin only."""
    db = _get_db(request)

    if body.role not in VALID_ROLES:
        raise HTTPException(400, f"Invalid role. Must be one of: {VALID_ROLES}")

    # If engineer, validate engineer_key and resolve team
    team_key = None
    team_name = None
    if body.role == "engineer":
        if not body.engineer_key:
            raise HTTPException(400, "engineer_key is required for engineer role")

        eng = db.collection("engineers").get(body.engineer_key)
        if eng is None:
            raise HTTPException(404, f"Engineer '{body.engineer_key}' not found")

        # Look up team via member_of edge
        cursor = db.aql.execute(
            "FOR t IN 1..1 OUTBOUND CONCAT('engineers/', @key) member_of RETURN t",
            bind_vars={"key": body.engineer_key},
        )
        team = next(cursor, None)
        if team:
            team_key = team["_key"]
            team_name = team.get("name")

    # Check email uniqueness
    existing = db.aql.execute(
        "FOR u IN users FILTER u.email == @email RETURN 1",
        bind_vars={"email": body.email},
    )
    if next(existing, None) is not None:
        raise HTTPException(409, "Email already registered")

    # Insert user
    db.collection("users").insert({
        "email": body.email,
        "password_hash": hash_password(body.password),
        "role": body.role,
        "engineer_key": body.engineer_key if body.role == "engineer" else None,
        "team_key": team_key,
        "is_active": True,
    })

    logger.info("Register: %s (role=%s, team=%s) by admin %s",
                body.email, body.role, team_key, admin["email"])

    return UserResponse(
        email=body.email,
        role=body.role,
        team_key=team_key,
        team_name=team_name,
        engineer_key=body.engineer_key if body.role == "engineer" else None,
        is_active=True,
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh(body: TokenRefreshRequest, request: Request):
    """Exchange a valid refresh token for new access + refresh tokens."""
    try:
        payload = decode_token(body.refresh_token)
        if payload.get("type") != "refresh":
            raise HTTPException(401, "Not a refresh token")
    except Exception:
        raise HTTPException(401, "Invalid or expired refresh token")

    db = _get_db(request)

    cursor = db.aql.execute(
        "FOR u IN users FILTER u.email == @email AND u.is_active == true LIMIT 1 RETURN u",
        bind_vars={"email": payload["sub"]},
    )
    user = next(cursor, None)
    if user is None:
        raise HTTPException(401, "User not found or deactivated")

    token_data = {
        "sub": user["email"],
        "role": user["role"],
        "team_key": user.get("team_key"),
    }

    return TokenResponse(
        access_token=create_access_token(token_data),
        refresh_token=create_refresh_token(token_data),
    )


@router.get("/me", response_model=UserResponse)
async def me(request: Request, user: dict = Depends(get_current_user)):
    """Get current authenticated user info."""
    db = _get_db(request)

    # Resolve team name if user has a team
    team_name = None
    if user.get("team_key"):
        team_doc = db.collection("teams").get(user["team_key"])
        if team_doc:
            team_name = team_doc.get("name")

    return UserResponse(
        email=user["email"],
        role=user["role"],
        team_key=user.get("team_key"),
        team_name=team_name,
        engineer_key=user.get("engineer_key"),
        is_active=user.get("is_active", True),
    )


@router.get("/users", response_model=list[UserResponse])
async def list_users(request: Request, admin: dict = Depends(require_admin)):
    """List all user accounts. Admin only."""
    db = _get_db(request)

    # Build a team_key → team_name lookup (6 teams, fast)
    team_names = {}
    for team in db.collection("teams").all():
        team_names[team["_key"]] = team.get("name")

    users = []
    for doc in db.collection("users").all():
        users.append(UserResponse(
            email=doc["email"],
            role=doc["role"],
            team_key=doc.get("team_key"),
            team_name=team_names.get(doc.get("team_key")),
            engineer_key=doc.get("engineer_key"),
            is_active=doc.get("is_active", True),
        ))
    return users


@router.patch("/users/{email}/toggle-active", response_model=UserResponse)
async def toggle_user_active(email: str, request: Request, admin: dict = Depends(require_admin)):
    """Activate or deactivate a user account. Admin only."""
    db = _get_db(request)

    cursor = db.aql.execute(
        "FOR u IN users FILTER u.email == @email LIMIT 1 RETURN u",
        bind_vars={"email": email},
    )
    user = next(cursor, None)
    if user is None:
        raise HTTPException(404, "User not found")

    # Prevent admin from deactivating themselves
    if user["email"] == admin["email"]:
        raise HTTPException(400, "Cannot deactivate your own account")

    new_status = not user.get("is_active", True)
    db.collection("users").update({"_key": user["_key"], "is_active": new_status})

    team_name = None
    if user.get("team_key"):
        team_doc = db.collection("teams").get(user["team_key"])
        if team_doc:
            team_name = team_doc.get("name")

    action = "activated" if new_status else "deactivated"
    logger.info("User %s %s by admin %s", email, action, admin["email"])

    return UserResponse(
        email=user["email"],
        role=user["role"],
        team_key=user.get("team_key"),
        team_name=team_name,
        engineer_key=user.get("engineer_key"),
        is_active=new_status,
    )


@router.get("/engineers")
async def list_engineers(request: Request, admin: dict = Depends(require_admin)):
    """List all engineers with their team info. Admin only. Used for user creation form."""
    db = _get_db(request)

    engineers = []
    for eng in db.collection("engineers").all():
        # Find team via member_of edge
        cursor = db.aql.execute(
            "FOR t IN 1..1 OUTBOUND CONCAT('engineers/', @key) member_of RETURN t",
            bind_vars={"key": eng["_key"]},
        )
        team = next(cursor, None)
        engineers.append({
            "key": eng["_key"],
            "name": eng.get("name", ""),
            "role": eng.get("role", ""),
            "email": eng.get("email", ""),
            "team_key": team["_key"] if team else None,
            "team_name": team.get("name") if team else None,
        })
    return engineers
