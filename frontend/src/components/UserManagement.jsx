import { useState, useEffect } from "react";
import { fetchUsers, registerUser, toggleUserActive, fetchEngineers } from "../services/api";
import DeskMindSpinner from "./DeskMindSpinner";

const T = {
  bg: "#0C0C0F",
  card: "rgba(255,255,255,0.04)",
  border: "rgba(255,255,255,0.08)",
  text: "#F5F5F4",
  textMuted: "#78716C",
  textDim: "#44403C",
  accent: "#F97316",
  success: "#22c55e",
  danger: "#ef4444",
  warning: "#f59e0b",
};

const roleBadge = {
  admin: { bg: "rgba(249,115,22,0.12)", color: T.accent },
  engineer: { bg: "rgba(34,197,94,0.12)", color: T.success },
  user: { bg: "rgba(245,158,11,0.12)", color: T.warning },
};

export default function UserManagement() {
  const [users, setUsers] = useState([]);
  const [engineers, setEngineers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);
  const [showForm, setShowForm] = useState(false);

  // Form state
  const [formEmail, setFormEmail] = useState("");
  const [formPassword, setFormPassword] = useState("");
  const [formRole, setFormRole] = useState("engineer");
  const [formEngineerKey, setFormEngineerKey] = useState("");
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    loadData();
  }, []);

  async function loadData() {
    setLoading(true);
    try {
      const [u, e] = await Promise.all([fetchUsers(), fetchEngineers()]);
      setUsers(u);
      setEngineers(e);
      setError(null);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  async function handleCreate(e) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    setSuccess(null);
    try {
      const userData = {
        email: formEmail,
        password: formPassword,
        role: formRole,
      };
      if (formRole === "engineer" && formEngineerKey) {
        userData.engineer_key = formEngineerKey;
      }
      await registerUser(userData);
      setSuccess(`User ${formEmail} created successfully`);
      setFormEmail("");
      setFormPassword("");
      setFormRole("engineer");
      setFormEngineerKey("");
      setShowForm(false);
      await loadData();
    } catch (err) {
      setError(err.message);
    } finally {
      setSubmitting(false);
    }
  }

  async function handleToggle(email) {
    setError(null);
    setSuccess(null);
    try {
      const updated = await toggleUserActive(email);
      setSuccess(`User ${email} ${updated.is_active ? "activated" : "deactivated"}`);
      await loadData();
    } catch (err) {
      setError(err.message);
    }
  }

  // Auto-fill email when engineer is selected
  function handleEngineerSelect(key) {
    setFormEngineerKey(key);
    if (key) {
      const eng = engineers.find((e) => e.key === key);
      if (eng?.email && !formEmail) {
        setFormEmail(eng.email);
      }
    }
  }

  if (loading) {
    return (
      <div style={{ textAlign: "center", padding: 60 }}>
        <DeskMindSpinner size="md" label="Loading users..." />
      </div>
    );
  }

  return (
    <div>
      {/* Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 24 }}>
        <div>
          <h1 style={{ fontSize: 22, fontWeight: 600, fontFamily: "'Inter', system-ui", margin: 0 }}>
            User Management
          </h1>
          <p style={{ color: T.textMuted, fontSize: 13, margin: "4px 0 0" }}>
            {users.length} user{users.length !== 1 ? "s" : ""} registered
          </p>
        </div>
        <button
          onClick={() => setShowForm(!showForm)}
          style={{
            padding: "10px 20px",
            background: showForm ? "rgba(239,68,68,0.1)" : T.accent,
            color: showForm ? T.danger : "#fff",
            border: showForm ? "1px solid rgba(239,68,68,0.2)" : "none",
            borderRadius: 8,
            fontSize: 13,
            fontWeight: 600,
            cursor: "pointer",
            boxShadow: showForm ? "none" : "0 0 20px rgba(249,115,22,0.3)",
          }}
        >
          {showForm ? "Cancel" : "+ Create User"}
        </button>
      </div>

      {/* Messages */}
      {error && (
        <div style={{
          background: "rgba(239,68,68,0.1)",
          border: "1px solid rgba(239,68,68,0.2)",
          borderRadius: 10,
          padding: "10px 16px",
          marginBottom: 16,
          color: T.danger,
          fontSize: 13,
        }}>
          {error}
        </div>
      )}
      {success && (
        <div style={{
          background: "rgba(34,197,94,0.1)",
          border: "1px solid rgba(34,197,94,0.2)",
          borderRadius: 10,
          padding: "10px 16px",
          marginBottom: 16,
          color: T.success,
          fontSize: 13,
        }}>
          {success}
        </div>
      )}

      {/* Create User Form */}
      {showForm && (
        <div style={{
          background: T.card,
          border: `1px solid ${T.border}`,
          borderRadius: 16,
          padding: 28,
          marginBottom: 24,
          backdropFilter: "blur(8px)",
        }}>
          <h3 style={{ fontSize: 16, fontWeight: 600, marginBottom: 20, color: T.text }}>
            Create New User
          </h3>
          <form onSubmit={handleCreate}>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, marginBottom: 16 }}>
              {/* Role */}
              <div>
                <label style={labelStyle}>Role</label>
                <select
                  value={formRole}
                  onChange={(e) => { setFormRole(e.target.value); setFormEngineerKey(""); }}
                  style={selectStyle}
                >
                  <option value="engineer">Engineer</option>
                  <option value="user">User</option>
                  <option value="admin">Admin</option>
                </select>
              </div>

              {/* Engineer (only for engineer role) */}
              {formRole === "engineer" && (
                <div>
                  <label style={labelStyle}>Engineer</label>
                  <select
                    value={formEngineerKey}
                    onChange={(e) => handleEngineerSelect(e.target.value)}
                    required
                    style={selectStyle}
                  >
                    <option value="">Select engineer...</option>
                    {engineers.map((eng) => (
                      <option key={eng.key} value={eng.key}>
                        {eng.name} — {eng.team_name || "No team"} ({eng.key})
                      </option>
                    ))}
                  </select>
                </div>
              )}
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, marginBottom: 20 }}>
              {/* Email */}
              <div>
                <label style={labelStyle}>Email</label>
                <input
                  type="email"
                  value={formEmail}
                  onChange={(e) => setFormEmail(e.target.value)}
                  placeholder="user@company.com"
                  required
                  style={inputStyle}
                />
              </div>

              {/* Password */}
              <div>
                <label style={labelStyle}>Password</label>
                <input
                  type="password"
                  value={formPassword}
                  onChange={(e) => setFormPassword(e.target.value)}
                  placeholder="Set a password"
                  required
                  style={inputStyle}
                />
              </div>
            </div>

            <button
              type="submit"
              disabled={submitting}
              style={{
                padding: "10px 24px",
                background: submitting ? "rgba(249,115,22,0.5)" : T.accent,
                color: "#fff",
                border: "none",
                borderRadius: 8,
                fontSize: 13,
                fontWeight: 600,
                cursor: submitting ? "wait" : "pointer",
                display: "flex",
                alignItems: "center",
                gap: 8,
              }}
            >
              {submitting ? <><DeskMindSpinner size="sm" /> Creating...</> : "Create User"}
            </button>
          </form>
        </div>
      )}

      {/* Users Table */}
      <div style={{
        background: T.card,
        border: `1px solid ${T.border}`,
        borderRadius: 16,
        overflow: "hidden",
        backdropFilter: "blur(8px)",
      }}>
        {/* Table Header */}
        <div style={{
          display: "grid",
          gridTemplateColumns: "2fr 1fr 1.5fr 0.8fr 0.8fr",
          gap: 12,
          padding: "14px 20px",
          borderBottom: `1px solid ${T.border}`,
          fontSize: 10,
          fontWeight: 600,
          color: T.textDim,
          textTransform: "uppercase",
          letterSpacing: 1,
          fontFamily: "'JetBrains Mono', monospace",
        }}>
          <span>Email</span>
          <span>Role</span>
          <span>Team</span>
          <span>Status</span>
          <span>Actions</span>
        </div>

        {/* User Rows */}
        {users.map((u) => {
          const badge = roleBadge[u.role] || roleBadge.user;
          return (
            <div
              key={u.email}
              style={{
                display: "grid",
                gridTemplateColumns: "2fr 1fr 1.5fr 0.8fr 0.8fr",
                gap: 12,
                padding: "14px 20px",
                borderBottom: `1px solid ${T.border}`,
                alignItems: "center",
                fontSize: 13,
                transition: "background 0.15s",
              }}
              onMouseEnter={(e) => e.currentTarget.style.background = "rgba(255,255,255,0.02)"}
              onMouseLeave={(e) => e.currentTarget.style.background = "transparent"}
            >
              {/* Email */}
              <span style={{
                color: T.text,
                fontFamily: "'JetBrains Mono', monospace",
                fontSize: 12,
                overflow: "hidden",
                textOverflow: "ellipsis",
                whiteSpace: "nowrap",
              }}>
                {u.email}
              </span>

              {/* Role Badge */}
              <span style={{
                padding: "4px 10px",
                borderRadius: 12,
                fontSize: 11,
                fontWeight: 600,
                background: badge.bg,
                color: badge.color,
                textTransform: "capitalize",
                width: "fit-content",
              }}>
                {u.role}
              </span>

              {/* Team */}
              <span style={{ color: u.team_name ? T.text : T.textDim, fontSize: 12 }}>
                {u.team_name || (u.role === "admin" ? "All teams" : "—")}
              </span>

              {/* Status */}
              <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                <div style={{
                  width: 7,
                  height: 7,
                  borderRadius: "50%",
                  background: u.is_active ? T.success : T.danger,
                  boxShadow: `0 0 6px ${u.is_active ? T.success : T.danger}`,
                }} />
                <span style={{ fontSize: 11, color: u.is_active ? T.success : T.danger }}>
                  {u.is_active ? "Active" : "Inactive"}
                </span>
              </div>

              {/* Toggle Button */}
              <button
                onClick={() => handleToggle(u.email)}
                style={{
                  padding: "5px 10px",
                  background: u.is_active ? "rgba(239,68,68,0.08)" : "rgba(34,197,94,0.08)",
                  border: `1px solid ${u.is_active ? "rgba(239,68,68,0.2)" : "rgba(34,197,94,0.2)"}`,
                  borderRadius: 6,
                  color: u.is_active ? T.danger : T.success,
                  fontSize: 11,
                  fontWeight: 500,
                  cursor: "pointer",
                  width: "fit-content",
                }}
              >
                {u.is_active ? "Deactivate" : "Activate"}
              </button>
            </div>
          );
        })}

        {users.length === 0 && (
          <div style={{ textAlign: "center", padding: 40, color: T.textDim, fontSize: 13 }}>
            No users found. Create the first user above.
          </div>
        )}
      </div>
    </div>
  );
}

// ── Shared Styles ──

const labelStyle = {
  display: "block",
  fontSize: 11,
  fontWeight: 600,
  color: "#78716C",
  marginBottom: 6,
  letterSpacing: 1,
  textTransform: "uppercase",
  fontFamily: "'JetBrains Mono', monospace",
};

const inputStyle = {
  width: "100%",
  padding: "10px 14px",
  background: "rgba(255,255,255,0.06)",
  border: "1px solid rgba(255,255,255,0.1)",
  borderRadius: 8,
  color: "#F5F5F4",
  fontSize: 13,
  outline: "none",
  boxSizing: "border-box",
};

const selectStyle = {
  width: "100%",
  padding: "10px 14px",
  background: "rgba(255,255,255,0.06)",
  border: "1px solid rgba(255,255,255,0.1)",
  borderRadius: 8,
  color: "#F5F5F4",
  fontSize: 13,
  outline: "none",
  boxSizing: "border-box",
  appearance: "none",
};
