const API_BASE = "/api";

// ── Token Management ──

function getAccessToken() {
  return localStorage.getItem("access_token");
}

function getRefreshToken() {
  return localStorage.getItem("refresh_token");
}

function setTokens(access, refresh) {
  localStorage.setItem("access_token", access);
  localStorage.setItem("refresh_token", refresh);
}

function clearTokens() {
  localStorage.removeItem("access_token");
  localStorage.removeItem("refresh_token");
}

export function isLoggedIn() {
  return !!getAccessToken();
}

// ── Authenticated Fetch Wrapper ──

// Mutex: only one refresh at a time; concurrent 401s share the same refresh promise
let _refreshPromise = null;

async function authFetch(url, options = {}) {
  const headers = {
    ...options.headers,
    Authorization: `Bearer ${getAccessToken()}`,
  };
  let res = await fetch(url, { ...options, headers });

  // If 401, try refreshing the token and retry once
  if (res.status === 401) {
    // Deduplicate concurrent refresh attempts
    if (!_refreshPromise) {
      _refreshPromise = refreshTokens().finally(() => { _refreshPromise = null; });
    }
    const refreshed = await _refreshPromise;
    if (refreshed) {
      headers.Authorization = `Bearer ${getAccessToken()}`;
      res = await fetch(url, { ...options, headers });
    } else if (!getRefreshToken()) {
      // Refresh token was cleared → genuinely invalid session; force a clean logout.
      // If the refresh token is still present, the failure was transient (backend
      // down/restarting) — keep the session and let the caller handle the error so a
      // restart doesn't log the user out.
      logout();
      window.location.reload();
    }
  }
  return res;
}

// ── Authenticated media loading ──

// Fetch a protected file (e.g. an uploaded screenshot) WITH the auth token and
// return a temporary in-memory object URL the browser can render. Needed because
// the /api/upload/{id} endpoint now requires auth, and plain <img src> / <a href>
// requests don't carry the Authorization header. Caller must URL.revokeObjectURL().
export async function fetchAuthedObjectUrl(path) {
  const res = await authFetch(path);
  if (!res.ok) throw new Error("Failed to load file");
  const blob = await res.blob();
  return URL.createObjectURL(blob);
}

// ── Auth Endpoints ──

export async function login(email, password) {
  const res = await fetch(`${API_BASE}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Invalid credentials");
  }
  const data = await res.json();
  setTokens(data.access_token, data.refresh_token);
  return data;
}

export async function refreshTokens() {
  const rt = getRefreshToken();
  if (!rt) return false;
  try {
    const res = await fetch(`${API_BASE}/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: rt }),
    });
    if (res.ok) {
      const data = await res.json();
      setTokens(data.access_token, data.refresh_token);
      return true;
    }
    // Only a real auth rejection means the refresh token is invalid → clear the session.
    // A 5xx (backend unhealthy/restarting) is transient — keep tokens so the session recovers.
    if (res.status === 401 || res.status === 403) {
      clearTokens();
    }
    return false;
  } catch {
    // Network error (backend unreachable, e.g. during a Docker restart) — transient; keep tokens.
    return false;
  }
}

export function logout() {
  clearTokens();
}

export async function fetchMe() {
  const res = await authFetch(`${API_BASE}/auth/me`);
  if (!res.ok) throw new Error("Not authenticated");
  return res.json();
}

// ── User Management (Admin) ──

export async function fetchUsers() {
  const res = await authFetch(`${API_BASE}/auth/users`);
  if (!res.ok) throw new Error("Failed to fetch users");
  return res.json();
}

export async function registerUser(userData) {
  const res = await authFetch(`${API_BASE}/auth/register`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(userData),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Failed to register user");
  }
  return res.json();
}

export async function toggleUserActive(email) {
  const res = await authFetch(`${API_BASE}/auth/users/${encodeURIComponent(email)}/toggle-active`, {
    method: "PATCH",
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Failed to toggle user status");
  }
  return res.json();
}

export async function fetchEngineers() {
  const res = await authFetch(`${API_BASE}/auth/engineers`);
  if (!res.ok) throw new Error("Failed to fetch engineers");
  return res.json();
}

// ── Ticket Endpoints (now authenticated) ──

export async function fetchTickets() {
  const res = await authFetch(`${API_BASE}/tickets`);
  if (!res.ok) throw new Error("Failed to fetch tickets");
  return res.json();
}

export async function fetchTicket(id) {
  const res = await authFetch(`${API_BASE}/tickets/${id}`);
  if (!res.ok) throw new Error("Failed to fetch ticket");
  return res.json();
}

export async function updateTicketStatus(id, status, assignedTo = null) {
  const body = { status };
  if (assignedTo) body.assigned_to = assignedTo;
  const res = await authFetch(`${API_BASE}/tickets/${id}/status`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Failed to update ticket status");
  }
  return res.json();
}

export async function resolveTicket(id, data) {
  const res = await authFetch(`${API_BASE}/tickets/${id}/resolve`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Failed to resolve ticket");
  }
  return res.json();
}

export async function submitFeedback(id, rating, comment = null) {
  const res = await authFetch(`${API_BASE}/tickets/${id}/feedback`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ rating, comment }),
  });
  if (!res.ok) throw new Error("Failed to submit feedback");
  return res.json();
}

export async function createTicket(ticket) {
  const res = await authFetch(`${API_BASE}/tickets`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(ticket),
  });
  if (!res.ok) throw new Error("Failed to create ticket");
  return res.json();
}

export async function overrideClassification(id, { category, priority, reason }) {
  const res = await authFetch(`${API_BASE}/tickets/${id}/override`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ category, priority: priority || undefined, reason }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Failed to override classification");
  }
  return res.json();
}

export async function deleteTicket(id) {
  const res = await authFetch(`${API_BASE}/tickets/${id}`, { method: "DELETE" });
  if (!res.ok) throw new Error("Failed to delete ticket");
}

export async function getRunbook(id) {
  const res = await authFetch(`${API_BASE}/runbooks/${encodeURIComponent(id)}`);
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Failed to load runbook");
  }
  return res.json();
}

// ── Chat (authenticated) ──

export async function sendChat(message, history = []) {
  const res = await authFetch(`${API_BASE}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, history }),
  });
  if (!res.ok) throw new Error("Failed to send chat");
  return res.json();
}

// ── Graph ──

export async function fetchGraph(category) {
  const url = category ? `${API_BASE}/graph?category=${encodeURIComponent(category)}` : `${API_BASE}/graph`;
  const res = await authFetch(url);
  if (!res.ok) throw new Error("Failed to fetch graph");
  return res.json();
}

// ── Health (public, no auth needed) ──

// ── Incidents ──

export async function fetchIncidents() {
  const res = await authFetch(`${API_BASE}/incidents`);
  if (!res.ok) return [];
  return res.json();
}

// ── Screenshot Upload ──

export async function uploadScreenshot(file) {
  const formData = new FormData();
  formData.append("file", file);
  const token = getAccessToken();
  const res = await fetch(`${API_BASE}/upload`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
    body: formData,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Failed to upload screenshot");
  }
  return res.json();
}

// ── Enrichment ──

export async function enrichTicket(id, answers) {
  const res = await authFetch(`${API_BASE}/tickets/${id}/enrich`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ answers }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Failed to enrich ticket");
  }
  return res.json();
}

// ── Corrections ──

export async function fetchCorrectionStats() {
  const res = await authFetch(`${API_BASE}/corrections/stats`);
  if (!res.ok) throw new Error("Failed to fetch correction stats");
  return res.json();
}

// ── Stats (authenticated) ──

export async function fetchStats() {
  const res = await authFetch(`${API_BASE}/stats`);
  if (!res.ok) throw new Error("Failed to fetch stats");
  return res.json();
}

export async function fetchTicketTimeline(ticketId) {
  const res = await authFetch(`${API_BASE}/stats/tickets/${ticketId}/timeline`);
  if (!res.ok) throw new Error("Failed to fetch timeline");
  return res.json();
}

// ── Health (public, no auth needed) ──

export async function fetchHealth() {
  const res = await fetch("/health");
  if (!res.ok) throw new Error("Failed to fetch health");
  return res.json();
}
