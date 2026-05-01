import { useState, useEffect, useMemo } from "react";
import { fetchTickets, createTicket } from "../services/api";
import DeskMindSpinner from "./DeskMindSpinner";
import TicketDetail from "./TicketDetail";

// ── Theme tokens ──
const T = {
  bg: "#0C0C0F",
  card: "rgba(255,255,255,0.04)",
  border: "rgba(255,255,255,0.08)",
  borderGlow: "rgba(249,115,22,0.3)",
  text: "#F5F5F4",
  textMuted: "#78716C",
  textDim: "#44403C",
  accent: "#F97316",
  accentGlow: "rgba(249,115,22,0.15)",
  success: "#22c55e",
  warning: "#f59e0b",
  danger: "#ef4444",
};

const priorityStyles = {
  critical: { bg: "rgba(239,68,68,0.15)", color: "#ef4444", dot: "#ef4444" },
  high: { bg: "rgba(239,68,68,0.12)", color: "#ef4444", dot: "#ef4444" },
  medium: { bg: "rgba(245,158,11,0.12)", color: "#f59e0b", dot: "#f59e0b" },
  low: { bg: "rgba(34,197,94,0.12)", color: "#22c55e", dot: "#22c55e" },
};

const statusStyles = {
  routed: { bg: "rgba(249,115,22,0.12)", color: "#F97316", dot: "#F97316" },
  in_progress: { bg: "rgba(59,130,246,0.12)", color: "#3b82f6", dot: "#3b82f6" },
  escalated: { bg: "rgba(239,68,68,0.12)", color: "#ef4444", dot: "#ef4444" },
  resolved: { bg: "rgba(34,197,94,0.12)", color: "#22c55e", dot: "#22c55e" },
};

const domainCards = [
  { key: "Infrastructure", label: "Infrastructure", icon: "INF", desc: "Servers, VMs, OS, Kubernetes, hardware" },
  { key: "Application", label: "Application", icon: "APP", desc: "APIs, deployments, bugs, HTTP errors" },
  { key: "Database", label: "Database", icon: "DB", desc: "PostgreSQL, Redis, queries, replication" },
  { key: "Network", label: "Network", icon: "NET", desc: "DNS, firewall, VPN, SSL, latency" },
  { key: "Security", label: "Security", icon: "SEC", desc: "Vulnerabilities, breaches, malware" },
  { key: "Access Management", label: "Access Management", icon: "IAM", desc: "LDAP, SSO, MFA, RBAC, permissions" },
];

const labelStyle = {
  display: "block",
  fontSize: 11,
  fontWeight: 600,
  color: T.textMuted,
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
  color: T.text,
  fontSize: 13,
  outline: "none",
  boxSizing: "border-box",
  fontFamily: "'Inter', system-ui",
};

const selectStyle = {
  ...inputStyle,
  appearance: "none",
};

function timeAgo(dateStr) {
  if (!dateStr) return "";
  const now = new Date();
  const then = new Date(dateStr);
  const diffMs = now - then;
  const diffMin = Math.floor(diffMs / 60000);
  if (diffMin < 1) return "just now";
  if (diffMin < 60) return `${diffMin}m ago`;
  const diffHr = Math.floor(diffMin / 60);
  if (diffHr < 24) return `${diffHr}h ago`;
  const diffDay = Math.floor(diffHr / 24);
  if (diffDay === 1) return "yesterday";
  if (diffDay < 7) return `${diffDay}d ago`;
  const diffWeek = Math.floor(diffDay / 7);
  return `${diffWeek}w ago`;
}

export default function DomainDashboard({ user, onBack }) {
  const [tickets, setTickets] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Filters
  const [statusFilter, setStatusFilter] = useState("all");
  const [priorityFilter, setPriorityFilter] = useState("all");
  const [search, setSearch] = useState("");

  // Domain selector (admin only)
  const [selectedDomain, setSelectedDomain] = useState(null);

  // Detail view
  const [selectedTicket, setSelectedTicket] = useState(null);

  // Create ticket form
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [createTitle, setCreateTitle] = useState("");
  const [createDesc, setCreateDesc] = useState("");
  const [createPriority, setCreatePriority] = useState("medium");
  const [isClassifying, setIsClassifying] = useState(false);

  useEffect(() => {
    loadTickets();
  }, []);

  async function loadTickets() {
    setLoading(true);
    try {
      const data = await fetchTickets();
      setTickets(data);
      setError(null);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  // Client-side filtering
  const filtered = useMemo(() => {
    let result = [...tickets];

    // Domain filter: admin picks a domain, engineer sees their team
    if (user?.role === "admin" && selectedDomain) {
      result = result.filter(
        (t) => (t.category || "") === selectedDomain
      );
    } else if (user?.role === "engineer" && user?.team_key) {
      result = result.filter(
        (t) => (t.routed_to || "").toLowerCase() === (user.team_name || user.team_key || "").toLowerCase()
      );
    }

    if (statusFilter !== "all") {
      result = result.filter((t) => t.status === statusFilter);
    }
    if (priorityFilter !== "all") {
      result = result.filter((t) => t.priority === priorityFilter);
    }
    if (search.trim()) {
      const q = search.toLowerCase();
      result = result.filter(
        (t) =>
          (t.title || "").toLowerCase().includes(q) ||
          (t.description || "").toLowerCase().includes(q) ||
          String(t.id).includes(q)
      );
    }
    return result;
  }, [tickets, statusFilter, priorityFilter, search, selectedDomain, user]);

  // Stats
  const stats = useMemo(() => {
    const base = user?.role === "admin" && selectedDomain
      ? tickets.filter((t) => (t.category || "") === selectedDomain)
      : user?.role === "engineer" && user?.team_key
        ? tickets.filter(
            (t) => (t.routed_to || "").toLowerCase() === (user.team_name || user.team_key || "").toLowerCase()
          )
        : tickets;

    return {
      open: base.filter((t) => t.status === "routed" || t.status === "escalated").length,
      in_progress: base.filter((t) => t.status === "in_progress").length,
      resolved: base.filter((t) => t.status === "resolved").length,
      total: base.length,
    };
  }, [tickets, selectedDomain, user]);

  async function handleCreateTicket(e) {
    e.preventDefault();
    if (!createTitle.trim() || !createDesc.trim()) return;
    setIsClassifying(true);
    setError(null);
    try {
      const [created] = await Promise.all([
        createTicket({ title: createTitle, description: createDesc, priority: createPriority }),
        new Promise((r) => setTimeout(r, 1500)),
      ]);
      setTickets((prev) => [created, ...prev]);
      setCreateTitle("");
      setCreateDesc("");
      setCreatePriority("medium");
      setShowCreateForm(false);
    } catch {
      setError("Failed to create ticket. Check backend connection.");
    } finally {
      setIsClassifying(false);
    }
  }

  function handleStatusChange(ticketId, newStatus) {
    setTickets((prev) =>
      prev.map((t) => (t.id === ticketId ? { ...t, status: newStatus } : t))
    );
    if (selectedTicket?.id === ticketId) {
      setSelectedTicket((prev) => ({ ...prev, status: newStatus }));
    }
  }

  function handleResolve(ticketId, data) {
    setTickets((prev) =>
      prev.map((t) =>
        t.id === ticketId
          ? { ...t, status: "resolved", resolved_at: new Date().toISOString(), ...data }
          : t
      )
    );
    if (selectedTicket?.id === ticketId) {
      setSelectedTicket((prev) => ({
        ...prev,
        status: "resolved",
        resolved_at: new Date().toISOString(),
        ...data,
      }));
    }
  }

  function handleFeedback(ticketId, rating, comment) {
    // Optimistic: just mark that feedback was given
    if (selectedTicket?.id === ticketId) {
      setSelectedTicket((prev) => ({ ...prev, feedback_rating: rating }));
    }
  }

  // ── Detail overlay ──
  if (selectedTicket) {
    return (
      <TicketDetail
        ticket={selectedTicket}
        user={user}
        onClose={() => setSelectedTicket(null)}
        onStatusChange={handleStatusChange}
        onResolve={handleResolve}
        onFeedback={handleFeedback}
      />
    );
  }

  // ── Domain selector for admin ──
  if (user?.role === "admin" && !selectedDomain) {
    return (
      <div style={{ minHeight: "100vh", padding: "40px 24px" }}>
        <div style={{ maxWidth: 960, margin: "0 auto" }}>
          {/* Back button */}
          {onBack && (
            <button
              onClick={onBack}
              style={{
                background: "none",
                border: "none",
                color: T.textMuted,
                fontSize: 13,
                cursor: "pointer",
                display: "flex",
                alignItems: "center",
                gap: 6,
                marginBottom: 24,
                padding: 0,
                fontFamily: "'Inter', system-ui",
              }}
              onMouseEnter={(e) => (e.currentTarget.style.color = T.accent)}
              onMouseLeave={(e) => (e.currentTarget.style.color = T.textMuted)}
            >
              <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
                <path d="M10 12L6 8l4-4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
              Back
            </button>
          )}

          <div style={{ marginBottom: 32 }}>
            <h1 style={{
              fontSize: 26,
              fontWeight: 700,
              fontFamily: "'Inter', system-ui",
              color: T.text,
              margin: 0,
            }}>
              Domain Dashboard
            </h1>
            <p style={{ color: T.textMuted, fontSize: 14, marginTop: 6 }}>
              Select a domain to view its tickets and team activity
            </p>
          </div>

          <div style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))",
            gap: 16,
          }}>
            {/* All tickets card */}
            <button
              onClick={() => setSelectedDomain("ALL")}
              style={{
                background: T.card,
                border: `1px solid ${T.border}`,
                borderRadius: 16,
                padding: 24,
                cursor: "pointer",
                textAlign: "left",
                transition: "all 0.2s",
                backdropFilter: "blur(8px)",
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.borderColor = T.accent;
                e.currentTarget.style.background = "rgba(249,115,22,0.06)";
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.borderColor = T.border;
                e.currentTarget.style.background = T.card;
              }}
            >
              <div style={{
                width: 40,
                height: 40,
                borderRadius: 10,
                background: "rgba(249,115,22,0.12)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                marginBottom: 12,
                fontFamily: "'JetBrains Mono', monospace",
                fontSize: 12,
                fontWeight: 700,
                color: T.accent,
              }}>
                ALL
              </div>
              <div style={{ fontSize: 16, fontWeight: 600, color: T.text, fontFamily: "'Inter', system-ui" }}>
                All Tickets
              </div>
              <div style={{ fontSize: 12, color: T.textMuted, marginTop: 4 }}>
                View all domains combined
              </div>
              <div style={{
                marginTop: 12,
                fontFamily: "'JetBrains Mono', monospace",
                fontSize: 20,
                fontWeight: 700,
                color: T.accent,
              }}>
                {tickets.length}
              </div>
            </button>

            {domainCards.map((d) => {
              const count = tickets.filter(
                (t) => (t.category || "").toUpperCase() === d.key ||
                       (t.routed_to || "").toUpperCase().includes(d.key)
              ).length;
              return (
                <button
                  key={d.key}
                  onClick={() => setSelectedDomain(d.key)}
                  style={{
                    background: T.card,
                    border: `1px solid ${T.border}`,
                    borderRadius: 16,
                    padding: 24,
                    cursor: "pointer",
                    textAlign: "left",
                    transition: "all 0.2s",
                    backdropFilter: "blur(8px)",
                  }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.borderColor = T.accent;
                    e.currentTarget.style.background = "rgba(249,115,22,0.06)";
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.borderColor = T.border;
                    e.currentTarget.style.background = T.card;
                  }}
                >
                  <div style={{
                    width: 40,
                    height: 40,
                    borderRadius: 10,
                    background: "rgba(249,115,22,0.12)",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    marginBottom: 12,
                    fontFamily: "'JetBrains Mono', monospace",
                    fontSize: 12,
                    fontWeight: 700,
                    color: T.accent,
                  }}>
                    {d.icon}
                  </div>
                  <div style={{ fontSize: 16, fontWeight: 600, color: T.text, fontFamily: "'Inter', system-ui" }}>
                    {d.label}
                  </div>
                  <div style={{ fontSize: 12, color: T.textMuted, marginTop: 4 }}>
                    {d.desc}
                  </div>
                  <div style={{
                    marginTop: 12,
                    fontFamily: "'JetBrains Mono', monospace",
                    fontSize: 20,
                    fontWeight: 700,
                    color: count > 0 ? T.accent : T.textDim,
                  }}>
                    {count}
                  </div>
                </button>
              );
            })}
          </div>
        </div>
      </div>
    );
  }

  // ── Main dashboard view ──
  const dashboardTitle =
    user?.role === "admin"
      ? selectedDomain === "ALL"
        ? "All Tickets"
        : domainCards.find((d) => d.key === selectedDomain)?.label || selectedDomain
      : user?.team_name || "My Team";

  return (
    <div style={{ minHeight: "100vh", padding: "40px 24px" }}>
      <div style={{ maxWidth: 960, margin: "0 auto" }}>
        {/* Back / breadcrumb */}
        <button
          onClick={() => {
            if (user?.role === "admin") {
              setSelectedDomain(null);
            } else if (onBack) {
              onBack();
            }
          }}
          style={{
            background: "none",
            border: "none",
            color: T.textMuted,
            fontSize: 13,
            cursor: "pointer",
            display: "flex",
            alignItems: "center",
            gap: 6,
            marginBottom: 24,
            padding: 0,
            fontFamily: "'Inter', system-ui",
          }}
          onMouseEnter={(e) => (e.currentTarget.style.color = T.accent)}
          onMouseLeave={(e) => (e.currentTarget.style.color = T.textMuted)}
        >
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
            <path d="M10 12L6 8l4-4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
          {user?.role === "admin" ? "All Domains" : "Back"}
        </button>

        {/* ── Header ── */}
        <div style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "flex-start",
          marginBottom: 24,
          flexWrap: "wrap",
          gap: 16,
        }}>
          <div>
            <h1 style={{
              fontSize: 24,
              fontWeight: 700,
              fontFamily: "'Inter', system-ui",
              color: T.text,
              margin: 0,
            }}>
              {dashboardTitle}
            </h1>
            <div style={{ display: "flex", gap: 16, marginTop: 10 }}>
              <StatBadge label="Open" value={stats.open} color={T.accent} />
              <StatBadge label="In Progress" value={stats.in_progress} color="#3b82f6" />
              <StatBadge label="Resolved" value={stats.resolved} color={T.success} />
            </div>
          </div>

          <button
            onClick={() => setShowCreateForm(!showCreateForm)}
            style={{
              padding: "10px 20px",
              background: showCreateForm ? "rgba(239,68,68,0.1)" : T.accent,
              color: showCreateForm ? T.danger : "#fff",
              border: showCreateForm ? "1px solid rgba(239,68,68,0.2)" : "none",
              borderRadius: 8,
              fontSize: 13,
              fontWeight: 600,
              cursor: "pointer",
              fontFamily: "'Inter', system-ui",
              boxShadow: showCreateForm ? "none" : "0 0 20px rgba(249,115,22,0.3)",
              display: "flex",
              alignItems: "center",
              gap: 6,
            }}
          >
            {showCreateForm ? (
              "Cancel"
            ) : (
              <>
                <svg width="14" height="14" viewBox="0 0 16 16" fill="none">
                  <path d="M8 3v10M3 8h10" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
                </svg>
                Create Ticket
              </>
            )}
          </button>
        </div>

        {/* ── Error ── */}
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

        {/* ── Create Ticket Form ── */}
        {showCreateForm && (
          <div style={{
            background: T.card,
            border: `1px solid ${T.border}`,
            borderRadius: 16,
            padding: 28,
            marginBottom: 24,
            backdropFilter: "blur(8px)",
            animation: "fadeSlideIn 0.2s ease-out",
          }}>
            <style>{`@keyframes fadeSlideIn { from { opacity:0; transform:translateY(-8px) } to { opacity:1; transform:translateY(0) } }`}</style>
            <h3 style={{ fontSize: 16, fontWeight: 600, marginBottom: 20, color: T.text, fontFamily: "'Inter', system-ui" }}>
              New Ticket
            </h3>
            <form onSubmit={handleCreateTicket}>
              <div style={{ marginBottom: 16 }}>
                <label style={labelStyle}>Title</label>
                <input
                  type="text"
                  placeholder="Brief summary of the issue"
                  value={createTitle}
                  onChange={(e) => setCreateTitle(e.target.value)}
                  required
                  style={inputStyle}
                />
              </div>
              <div style={{ marginBottom: 16 }}>
                <label style={labelStyle}>Description</label>
                <textarea
                  placeholder="Provide details -- affected systems, error messages, impact..."
                  value={createDesc}
                  onChange={(e) => setCreateDesc(e.target.value)}
                  rows={4}
                  required
                  style={{ ...inputStyle, resize: "vertical", minHeight: 80 }}
                />
              </div>
              <div style={{ display: "flex", gap: 12, alignItems: "flex-end" }}>
                <div>
                  <label style={labelStyle}>Priority</label>
                  <div style={{ display: "flex", borderRadius: 8, overflow: "hidden", border: `1px solid ${T.border}` }}>
                    {["low", "medium", "high"].map((p) => (
                      <button
                        key={p}
                        type="button"
                        onClick={() => setCreatePriority(p)}
                        style={{
                          padding: "8px 18px",
                          fontSize: 12,
                          fontWeight: createPriority === p ? 600 : 400,
                          border: "none",
                          cursor: "pointer",
                          textTransform: "capitalize",
                          fontFamily: "'Inter', system-ui",
                          background: createPriority === p
                            ? (p === "high" ? "rgba(239,68,68,0.15)" : p === "medium" ? "rgba(245,158,11,0.15)" : "rgba(34,197,94,0.15)")
                            : "transparent",
                          color: createPriority === p
                            ? (p === "high" ? T.danger : p === "medium" ? T.warning : T.success)
                            : T.textDim,
                          borderRight: p !== "high" ? `1px solid ${T.border}` : "none",
                          transition: "all 0.15s",
                        }}
                      >
                        {p}
                      </button>
                    ))}
                  </div>
                </div>
                <button
                  type="submit"
                  disabled={!createTitle.trim() || !createDesc.trim() || isClassifying}
                  style={{
                    flex: 1,
                    padding: "10px 24px",
                    background: isClassifying ? "rgba(249,115,22,0.5)" : T.accent,
                    color: "#fff",
                    border: "none",
                    borderRadius: 8,
                    fontSize: 13,
                    fontWeight: 600,
                    cursor: isClassifying ? "wait" : "pointer",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    gap: 8,
                    fontFamily: "'Inter', system-ui",
                    boxShadow: isClassifying ? "none" : "0 0 20px rgba(249,115,22,0.3)",
                  }}
                >
                  {isClassifying ? (
                    <>
                      <DeskMindSpinner size="sm" />
                      Classifying...
                    </>
                  ) : (
                    <>
                      <svg width="14" height="14" viewBox="0 0 16 16" fill="none">
                        <path d="M14 2L7.5 14L5.5 8.5L2 7L14 2Z" stroke="#fff" strokeWidth="1.5" strokeLinejoin="round" />
                      </svg>
                      Submit
                    </>
                  )}
                </button>
              </div>
            </form>
          </div>
        )}

        {/* ── Filter Bar ── */}
        <div style={{
          display: "flex",
          gap: 12,
          marginBottom: 24,
          flexWrap: "wrap",
          alignItems: "center",
        }}>
          <div style={{ position: "relative" }}>
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              style={{
                ...selectStyle,
                width: "auto",
                paddingRight: 32,
                fontSize: 12,
              }}
            >
              <option value="all">All Statuses</option>
              <option value="routed">Routed</option>
              <option value="in_progress">In Progress</option>
              <option value="escalated">Escalated</option>
              <option value="resolved">Resolved</option>
            </select>
            <svg
              width="12" height="12" viewBox="0 0 12 12" fill="none"
              style={{ position: "absolute", right: 10, top: "50%", transform: "translateY(-50%)", pointerEvents: "none" }}
            >
              <path d="M3 4.5l3 3 3-3" stroke={T.textMuted} strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </div>

          <div style={{ position: "relative" }}>
            <select
              value={priorityFilter}
              onChange={(e) => setPriorityFilter(e.target.value)}
              style={{
                ...selectStyle,
                width: "auto",
                paddingRight: 32,
                fontSize: 12,
              }}
            >
              <option value="all">All Priorities</option>
              <option value="critical">Critical</option>
              <option value="high">High</option>
              <option value="medium">Medium</option>
              <option value="low">Low</option>
            </select>
            <svg
              width="12" height="12" viewBox="0 0 12 12" fill="none"
              style={{ position: "absolute", right: 10, top: "50%", transform: "translateY(-50%)", pointerEvents: "none" }}
            >
              <path d="M3 4.5l3 3 3-3" stroke={T.textMuted} strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </div>

          <div style={{ flex: 1, minWidth: 200, position: "relative" }}>
            <svg
              width="14" height="14" viewBox="0 0 16 16" fill="none"
              style={{ position: "absolute", left: 12, top: "50%", transform: "translateY(-50%)" }}
            >
              <circle cx="7" cy="7" r="5" stroke={T.textDim} strokeWidth="1.2" />
              <path d="M11 11l3 3" stroke={T.textDim} strokeWidth="1.2" strokeLinecap="round" />
            </svg>
            <input
              type="text"
              placeholder="Search tickets..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              style={{
                ...inputStyle,
                paddingLeft: 34,
                fontSize: 12,
              }}
            />
          </div>

          <span style={{
            fontFamily: "'JetBrains Mono', monospace",
            fontSize: 11,
            color: T.textMuted,
            background: "rgba(255,255,255,0.05)",
            padding: "6px 12px",
            borderRadius: 10,
            whiteSpace: "nowrap",
          }}>
            {filtered.length} result{filtered.length !== 1 ? "s" : ""}
          </span>
        </div>

        {/* ── Loading ── */}
        {loading && (
          <div style={{ textAlign: "center", padding: 60 }}>
            <DeskMindSpinner size="md" label="Loading tickets..." />
          </div>
        )}

        {/* ── Empty state ── */}
        {!loading && filtered.length === 0 && (
          <div style={{
            textAlign: "center",
            padding: "60px 24px",
            background: T.card,
            borderRadius: 16,
            border: `1px solid ${T.border}`,
          }}>
            <svg width="48" height="48" viewBox="0 0 48 48" fill="none" style={{ marginBottom: 12, opacity: 0.3 }}>
              <rect x="4" y="8" width="40" height="32" rx="4" stroke={T.textMuted} strokeWidth="1.5" fill="none" />
              <line x1="12" y1="18" x2="36" y2="18" stroke={T.textMuted} strokeWidth="1.5" strokeLinecap="round" />
              <line x1="12" y1="24" x2="28" y2="24" stroke={T.textMuted} strokeWidth="1.5" strokeLinecap="round" />
              <line x1="12" y1="30" x2="32" y2="30" stroke={T.textMuted} strokeWidth="1.5" strokeLinecap="round" />
            </svg>
            <p style={{ color: T.textDim, fontSize: 13, margin: 0 }}>
              No tickets match your filters.
            </p>
          </div>
        )}

        {/* ── Ticket Cards ── */}
        {!loading && filtered.length > 0 && (
          <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            {filtered.map((t) => {
              const p = priorityStyles[t.priority] || priorityStyles.medium;
              const s = statusStyles[t.status] || statusStyles.routed;
              const confidencePct = Math.round((t.confidence_score || 0) * 100);

              return (
                <div
                  key={t.id}
                  onClick={() => setSelectedTicket(t)}
                  style={{
                    background: T.card,
                    border: `1px solid ${T.border}`,
                    borderRadius: 14,
                    padding: "18px 22px",
                    cursor: "pointer",
                    transition: "all 0.2s",
                    backdropFilter: "blur(8px)",
                  }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.borderColor = "rgba(249,115,22,0.25)";
                    e.currentTarget.style.background = "rgba(255,255,255,0.06)";
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.borderColor = T.border;
                    e.currentTarget.style.background = T.card;
                  }}
                >
                  {/* Top row: ID + title + badges */}
                  <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 10 }}>
                    <span style={{
                      fontFamily: "'JetBrains Mono', monospace",
                      fontSize: 11,
                      color: T.textDim,
                      fontWeight: 600,
                      minWidth: 44,
                    }}>
                      #{t.id}
                    </span>
                    <span style={{
                      flex: 1,
                      fontSize: 14,
                      fontWeight: 600,
                      color: T.text,
                      fontFamily: "'Inter', system-ui",
                      whiteSpace: "nowrap",
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                    }}>
                      {t.title}
                    </span>
                    {/* Priority badge */}
                    <span style={{
                      display: "inline-flex",
                      alignItems: "center",
                      gap: 4,
                      fontSize: 10,
                      fontWeight: 600,
                      padding: "3px 10px",
                      borderRadius: 10,
                      background: p.bg,
                      color: p.color,
                      textTransform: "capitalize",
                      whiteSpace: "nowrap",
                    }}>
                      <span style={{
                        width: 5, height: 5, borderRadius: "50%",
                        background: p.dot,
                        boxShadow: `0 0 6px ${p.dot}40`,
                      }} />
                      {t.priority}
                    </span>
                    {/* Status badge */}
                    <span style={{
                      display: "inline-flex",
                      alignItems: "center",
                      gap: 4,
                      fontSize: 10,
                      fontWeight: 600,
                      padding: "3px 10px",
                      borderRadius: 10,
                      background: s.bg,
                      color: s.color,
                      textTransform: "capitalize",
                      whiteSpace: "nowrap",
                    }}>
                      <span style={{
                        width: 5, height: 5, borderRadius: "50%",
                        background: s.dot,
                        boxShadow: `0 0 6px ${s.dot}40`,
                      }} />
                      {(t.status || "").replace("_", " ")}
                    </span>
                  </div>

                  {/* Bottom row: confidence + team + time */}
                  <div style={{ display: "flex", alignItems: "center", gap: 20 }}>
                    {/* Confidence bar */}
                    <div style={{ display: "flex", alignItems: "center", gap: 8, minWidth: 160 }}>
                      <span style={{
                        fontFamily: "'JetBrains Mono', monospace",
                        fontSize: 10,
                        color: T.textMuted,
                        minWidth: 28,
                      }}>
                        {confidencePct}%
                      </span>
                      <div style={{
                        flex: 1,
                        height: 4,
                        borderRadius: 2,
                        background: "rgba(255,255,255,0.06)",
                        overflow: "hidden",
                      }}>
                        <div style={{
                          width: `${confidencePct}%`,
                          height: "100%",
                          borderRadius: 2,
                          background: confidencePct > 70 ? T.success : confidencePct > 50 ? T.warning : T.danger,
                          transition: "width 0.3s",
                        }} />
                      </div>
                    </div>

                    {/* Routed to */}
                    {t.routed_to && (
                      <span style={{
                        fontSize: 11,
                        fontWeight: 600,
                        color: T.accent,
                      }}>
                        {t.routed_to}
                      </span>
                    )}

                    {/* Spacer */}
                    <span style={{ flex: 1 }} />

                    {/* Created at */}
                    <span style={{
                      fontFamily: "'JetBrains Mono', monospace",
                      fontSize: 10,
                      color: T.textDim,
                    }}>
                      {timeAgo(t.created_at)}
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}

// ── Small stat badge component ──
function StatBadge({ label, value, color }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
      <div style={{
        width: 7,
        height: 7,
        borderRadius: "50%",
        background: color,
        boxShadow: `0 0 8px ${color}50`,
      }} />
      <span style={{
        fontFamily: "'JetBrains Mono', monospace",
        fontSize: 18,
        fontWeight: 700,
        color: color,
      }}>
        {value}
      </span>
      <span style={{
        fontSize: 11,
        color: T.textMuted,
        fontFamily: "'Inter', system-ui",
      }}>
        {label}
      </span>
    </div>
  );
}
