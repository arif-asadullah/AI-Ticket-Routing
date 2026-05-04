# Phase 7: Authentication & RBAC

## What We Did

Added JWT-based authentication with role-based access control (RBAC) and team-scoped data access. Before this, all API endpoints were open — anyone could see, modify, or delete any ticket. Now, users must log in, and what they can see/do depends on their role and team.

## The Auth Flow

```
User opens DeskMind → Login page (email + password)
    → Backend verifies bcrypt hash → Returns JWT tokens
    → Every API call carries the token → Backend checks role + team
    → Engineers see only their team's tickets
```

## What Was Built

### 1. JWT Authentication

**Files**: `backend/core/auth.py`, `backend/api/auth.py`

Two tokens issued on login:
- **Access token** (30 min) — attached to every API call
- **Refresh token** (7 days) — silently renews expired access tokens

Password stored as **bcrypt hash** — plaintext never saved. Token payload contains `{sub: email, role, team_key}` signed with HS256.

### 2. Three Roles

| Role | See Tickets | Create | Update Status | Resolve | Delete | Manage Users |
|------|------------|--------|--------------|---------|--------|-------------|
| **Admin** | All 6 domains | Yes | Yes (any team) | Yes (any team) | Yes | Yes |
| **Engineer** | Own team only | Yes | Yes (own team) | Yes (own team) | No | No |
| **User** | All domains | Yes | No | No | No | No |

### 3. Team-Scoped Access

The key feature. Engineers are linked to teams through the knowledge graph:

```
users.team_key → teams._key → team name
```

When a Database Admin engineer calls `GET /api/tickets`, they only see tickets where `routed_to = "Database Admin"`. They cannot see Network, Security, or Infrastructure tickets. Admins bypass this filter.

This is enforced by three FastAPI dependencies:
- `get_current_user()` — extract user from JWT Bearer token
- `require_role(*roles)` — check role (admin, engineer, user)
- `require_team_access()` — check engineer belongs to ticket's team

### 4. Protected Endpoints

Every ticket endpoint now has an auth guard:

| Endpoint | Auth Guard | Team Scoped |
|----------|-----------|-------------|
| `GET /api/tickets` | Any authenticated | Engineers: own team only |
| `POST /api/tickets` | Any authenticated | submitted_by = user.email from token |
| `GET /api/tickets/{id}` | Any authenticated | Engineers: own team only |
| `PATCH /api/tickets/{id}/status` | Engineer or Admin | require_team_access |
| `POST /api/tickets/{id}/resolve` | Engineer or Admin | require_team_access |
| `DELETE /api/tickets/{id}` | Admin only | — |

### 5. Auth API Endpoints

| Endpoint | Auth | Purpose |
|----------|------|---------|
| `POST /api/auth/login` | Public | Email + password → JWT tokens |
| `POST /api/auth/register` | Admin only | Create new user linked to engineer/team |
| `POST /api/auth/refresh` | Public (needs refresh token) | Get new access token |
| `GET /api/auth/me` | Any authenticated | Current user info |
| `GET /api/auth/users` | Admin only | List all users |
| `PATCH /api/auth/users/{email}/toggle-active` | Admin only | Activate/deactivate user |
| `GET /api/auth/engineers` | Admin only | List engineers for user creation form |
| `POST /api/auth/bootstrap` | Public (only when 0 users) | Create first admin |

### 6. Users Collection

Separate from `engineers` (knowledge graph entities have different lifecycles from auth accounts):

```json
{
  "email": "arif.asadullah@schwettmann.in",
  "password_hash": "$2b$12$...",
  "role": "admin",
  "first_name": "Arif",
  "last_name": "Asadullah",
  "engineer_key": null,
  "team_key": null,
  "is_active": true
}
```

Seeded with 1 admin account. Additional users created via the User Management UI.

### 7. Login Page (Frontend)

**File**: `frontend/src/components/LoginPage.jsx`

Split layout:
- **Left side**: Login form on deep navy background — email, password, sign-in button
- **Right side**: Product showcase with animated background — hero text, "How it works" cards, tech stack pills
- **Center**: Interactive DeskMind logo badge with 3D tilt, pulse rings, and glow on hover

**Interactive background** (`LoginBackground.jsx`): Floating orbs that drift toward cursor, particles that scatter on hover, connection lines that glow brighter near mouse, click ripples, subtle grid overlay.

### 8. User Management Page (Frontend)

**File**: `frontend/src/components/UserManagement.jsx`

Admin-only tab in the dashboard:
- **User list table**: Email, role badge (color-coded), team name, active status with green/red dot
- **Create user form**: Role selector, engineer dropdown (auto-fills email from knowledge graph), password field
- **Activate/Deactivate toggle**: Per-user button, cannot deactivate yourself

### 9. Frontend Auth Integration

**File**: `frontend/src/App.jsx`, `frontend/src/services/api.js`

- Login gate: Shows login page if not authenticated, dashboard if logged in
- Token storage in localStorage with auto-refresh on 401
- `authFetch()` wrapper adds Bearer token to every API call
- User info + role + team shown in header with logout button
- Delete button hidden for non-admin users
- "Users" tab visible only for admins
- Landing page removed — login goes straight to dashboard

### 10. Nasscom R2 Documentation Updated

All 8 hackathon deliverable documents updated to reflect RBAC:
- 13 collections (was 12), 1,796 documents (was 1,795)
- Auth endpoints, guards, and team-scoping documented across all diagrams
- New auth sequence diagram added
- ERD updated with users entity and relationships
- State transitions updated with require_* guard conditions

## File Summary

| File | What |
|------|------|
| `backend/core/auth.py` | Password hashing, JWT creation/validation, FastAPI auth dependencies |
| `backend/api/auth.py` | Auth endpoints: login, register, refresh, me, users, toggle, engineers, bootstrap |
| `backend/schemas/auth.py` | Pydantic models: UserRegister, UserLogin, TokenResponse, UserResponse |
| `backend/api/tickets.py` | All 6 endpoints now protected with role + team guards |
| `backend/api/router.py` | Auth router registered |
| `backend/core/config.py` | JWT_SECRET_KEY, JWT_ALGORITHM, token expiry settings |
| `backend/services/schema.py` | `users` collection + `idx_users_email` unique index |
| `data/seed/seed_data.yaml` | Admin user account (arif.asadullah@schwettmann.in) |
| `scripts/seed_db.py` | `load_users()` with bcrypt hashing |
| `requirements.txt` | Added passlib[bcrypt], bcrypt==4.1.3 |
| `frontend/src/components/LoginPage.jsx` | Split login page with interactive background |
| `frontend/src/components/LoginBackground.jsx` | Mouse-reactive animated background |
| `frontend/src/components/UserManagement.jsx` | Admin user management page |
| `frontend/src/services/api.js` | Token management, authFetch, auth API functions |
| `frontend/src/App.jsx` | Auth gate, user state, logout, role-based UI |
| `frontend/src/components/TicketList.jsx` | Delete button hidden for non-admins |
