import { useState, useEffect, useMemo } from "react";
import { useTheme } from "../theme/ThemeContext";
import { fetchTickets, fetchStats, fetchIncidents } from "../services/api";
import DeskMindSpinner from "./DeskMindSpinner";
import TicketDetail from "./TicketDetail";
import StatsSummaryBar from "./StatsSummaryBar";

// Domain card images
import imgAllTickets from "../assets/images/all_tickets.png";
import imgInfrastructure from "../assets/images/infrastructure.png";
import imgApplication from "../assets/images/application.png";
import imgDatabase from "../assets/images/database.png";
import imgNetwork from "../assets/images/network.png";
import imgSecurity from "../assets/images/Security.png";
import imgAccessMgmt from "../assets/images/accessmanagement.png";


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
  pending_human: { bg: "rgba(220,38,38,0.15)", color: "#dc2626", dot: "#dc2626" },
  resolved: { bg: "rgba(34,197,94,0.12)", color: "#22c55e", dot: "#22c55e" },
};

const domainCards = [
  { key: "Infrastructure", label: "Infrastructure", icon: "INF", desc: "Servers, VMs, OS, Kubernetes, hardware", img: imgInfrastructure },
  { key: "Application", label: "Application", icon: "APP", desc: "APIs, deployments, bugs, HTTP errors", img: imgApplication },
  { key: "Database", label: "Database", icon: "DB", desc: "PostgreSQL, Redis, queries, replication", img: imgDatabase },
  { key: "Network", label: "Network", icon: "NET", desc: "DNS, firewall, VPN, SSL, latency", img: imgNetwork },
  { key: "Security", label: "Security", icon: "SEC", desc: "Vulnerabilities, breaches, malware", img: imgSecurity },
  { key: "Access Management", label: "Access Management", icon: "IAM", desc: "LDAP, SSO, MFA, RBAC, permissions", img: imgAccessMgmt },
];

function getStyles(T) {
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
    background: T.inputBg,
    border: `1px solid ${T.inputBorder}`,
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

  return { labelStyle, inputStyle, selectStyle };
}

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

export default function DomainDashboard({ user, onBack, refreshKey }) {
  const { T } = useTheme();
  const { labelStyle, inputStyle, selectStyle } = getStyles(T);
  const [tickets, setTickets] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [stats, setStats] = useState(null);
  const [statsLoading, setStatsLoading] = useState(true);
  const [incidents, setIncidents] = useState([]);

  // Filters
  const [statusFilter, setStatusFilter] = useState("all");
  const [priorityFilter, setPriorityFilter] = useState("all");
  const [search, setSearch] = useState("");

  // Domain selector (admin only)
  const [selectedDomain, setSelectedDomain] = useState(null);

  // Detail view
  const [selectedTicket, setSelectedTicket] = useState(null);

  // View toggle + pagination
  const [view, setView] = useState("card");
  const [page, setPage] = useState(1);
  const PAGE_SIZE = 12;


  function loadStats() {
    fetchStats()
      .then(setStats)
      .catch(() => {})
      .finally(() => setStatsLoading(false));
  }

  function loadIncidents() {
    fetchIncidents().then(setIncidents).catch(() => {});
  }

  useEffect(() => {
    loadTickets();
    loadStats();
    loadIncidents();
  }, [refreshKey]);

  // Also refresh stats when tickets array changes (from Socket.IO)
  useEffect(() => {
    if (tickets.length > 0) {
      loadStats();
      loadIncidents();
    }
  }, [tickets.length]);

  // Auto-refresh incidents every 60s
  useEffect(() => {
    const interval = setInterval(loadIncidents, 60000);
    return () => clearInterval(interval);
  }, []);

  // Reset page when filters or domain change
  useEffect(() => { setPage(1); }, [selectedDomain, statusFilter, priorityFilter, search]);

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
    if (user?.role === "admin" && selectedDomain && selectedDomain !== "ALL") {
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
  const localStats = useMemo(() => {
    const base = user?.role === "admin" && selectedDomain && selectedDomain !== "ALL"
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
    // Optimistic: mark that feedback was given in both tickets array and selected ticket
    setTickets((prev) =>
      prev.map((t) =>
        t.id === ticketId ? { ...t, feedback_rating: rating } : t
      )
    );
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
        onTicketUpdate={(updated) => {
          setSelectedTicket(updated);
          setTickets((prev) => prev.map((t) => t.id === updated.id ? updated : t));
        }}
      />
    );
  }

  // ── Domain selector for admin ──
  if (user?.role === "admin" && !selectedDomain) {
    return (
      <div style={{ minHeight: "100vh", padding: "40px 24px" }}>
        <div style={{ maxWidth: 960, margin: "0 auto" }}>
          {/* Back button — hidden on domain dashboard */}
          {false && onBack && (
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

          {/* Fixed-height slot so the card grid below never shifts while
              stats load/animate (prevents the dashboard cards from "jumping"). */}
          <div style={{ minHeight: 146 }}>
            <StatsSummaryBar stats={stats} loading={statsLoading} />
          </div>

          {/* AI Card Animations */}
          <style>{`
            @keyframes cornerPulse {
              0%, 100% { opacity: 0.25; }
              50% { opacity: 0.7; }
            }
            @keyframes floatDot {
              0%, 100% { transform: translateY(0px); opacity: 0.2; }
              50% { transform: translateY(-8px); opacity: 0.7; }
            }
            @keyframes glowPulse {
              0%, 100% { box-shadow: 0 0 0px rgba(249,115,22,0), 0 0 0px rgba(249,115,22,0); }
              50% { box-shadow: 0 0 20px rgba(249,115,22,0.25), 0 0 40px rgba(249,115,22,0.1); }
            }
            .ai-card { transition: all 0.3s ease; }
            .ai-card:hover { animation: glowPulse 2s ease infinite; }
            .ai-card:hover .card-img { transform: scale(1.08) !important; }
            .ai-card:hover .corner-bracket { opacity: 0.8 !important; }
          `}</style>

          <div style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))",
            gap: 16,
          }}>
            {/* All tickets card + domain cards */}
            {[
              { key: "ALL", label: "All Tickets", desc: "View all domains combined", icon: "ALL", img: imgAllTickets, count: tickets.length },
              ...domainCards.map((d) => ({
                ...d,
                count: tickets.filter(
                  (t) => (t.category || "").toLowerCase() === d.key.toLowerCase() ||
                         (t.routed_to || "").toLowerCase().includes(d.key.toLowerCase())
                ).length,
              })),
            ].map((d, idx) => (
              <button
                className="ai-card"
                key={d.key}
                onClick={() => setSelectedDomain(d.key)}
                onMouseMove={(e) => {
                  const rect = e.currentTarget.getBoundingClientRect();
                  const x = (e.clientX - rect.left) / rect.width - 0.5;
                  const y = (e.clientY - rect.top) / rect.height - 0.5;
                  e.currentTarget.style.transform = `perspective(800px) rotateY(${x * 6}deg) rotateX(${-y * 6}deg)`;
                  e.currentTarget.style.borderColor = "#F97316";
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.transform = "perspective(800px) rotateY(0deg) rotateX(0deg)";
                  e.currentTarget.style.borderColor = T.border;
                }}
                style={{
                  position: "relative",
                  overflow: "hidden",
                  background: T.card,
                  border: `1px solid ${T.border}`,
                  borderRadius: 16,
                  padding: 0,
                  cursor: "pointer",
                  textAlign: "left",
                  transformStyle: "preserve-3d",
                  boxShadow: T.cardShadow,
                }}
              >
                {/* Content */}
                <div style={{ padding: "20px 22px" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 10 }}>
                    <div style={{
                      width: 36, height: 36, borderRadius: 10,
                      background: `${T.accent}15`,
                      display: "flex", alignItems: "center", justifyContent: "center",
                      fontFamily: "'JetBrains Mono', monospace", fontSize: 11, fontWeight: 700, color: T.accent,
                    }}>
                      {d.icon}
                    </div>
                    <div style={{ fontSize: 16, fontWeight: 600, color: T.text, fontFamily: "'Inter', system-ui" }}>
                      {d.label}
                    </div>
                  </div>
                  <div style={{ fontSize: 11, color: T.textMuted, marginBottom: 12 }}>
                    {d.desc}
                  </div>
                  <div style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 22, fontWeight: 700, color: d.count > 0 ? T.accent : T.textDim }}>
                    {d.count}
                  </div>
                </div>
              </button>
            ))}
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
              <StatBadge label="Open" value={localStats.open} color={T.accent} />
              <StatBadge label="In Progress" value={localStats.in_progress} color="#3b82f6" />
              <StatBadge label="Resolved" value={localStats.resolved} color={T.success} />
            </div>
          </div>

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

        {/* ── Stats Summary Bar (fixed-height slot so the ticket list below
              never shifts while stats load/animate — same as the selector view) ── */}
        <div style={{ minHeight: 146 }}>
        {(() => {
          // For specific domains, compute stats from local tickets
          if (selectedDomain && selectedDomain !== "ALL") {
            const domainTickets = tickets.filter((t) => t.category === selectedDomain);
            const total = domainTickets.length;
            const escalated = domainTickets.filter((t) => t.status === "escalated" || t.status === "pending_human").length;
            const confidences = domainTickets.filter((t) => t.confidence_score).map((t) => t.confidence_score);
            const avgConf = confidences.length > 0 ? confidences.reduce((a, b) => a + b, 0) / confidences.length : 0;
            const domainStats = {
              total: total,
              avg_confidence: avgConf,
              escalation_rate: total > 0 ? escalated / total : 0,
              avg_resolution_minutes: stats?.avg_resolution_minutes || 0,
              agreement_rate: stats?.agreement_rate || 0,
              feedback: stats?.feedback || { helpful: 0, not_helpful: 0 },
            };
            return <StatsSummaryBar stats={domainStats} loading={false} />;
          }
          return <StatsSummaryBar stats={stats} loading={statsLoading} />;
        })()}
        </div>

        {/* ── Incident Predictions Banner ── */}
        {(() => {
          // Filter incidents by selected domain
          const filteredIncidents = selectedDomain && selectedDomain !== "ALL"
            ? incidents.filter((i) => i.category === selectedDomain || i.type === "spike")
            : incidents;
          return filteredIncidents.length > 0 && (
          <div style={{
            marginBottom: 20,
            padding: "16px 22px",
            background: "linear-gradient(135deg, rgba(239,68,68,0.06), rgba(245,158,11,0.06))",
            border: `1px solid rgba(239,68,68,0.2)`,
            borderLeft: "4px solid #ef4444",
            borderRadius: 14,
          }}>
            <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 12 }}>
              <div style={{
                width: 10, height: 10, borderRadius: "50%",
                background: "#ef4444",
                boxShadow: "0 0 8px rgba(239,68,68,0.6)",
                animation: "fabPulse 2s infinite",
              }} />
              <div>
                <h3 style={{
                  margin: 0, fontSize: 14, fontWeight: 700,
                  color: T.danger, fontFamily: "'Inter', system-ui",
                }}>
                  AI Predicted Incidents ({filteredIncidents.length})
                </h3>
                <p style={{ margin: "2px 0 0", fontSize: 11, color: T.textMuted }}>
                  DeskMind detected unusual patterns in recent tickets — these are not tickets, they are AI-generated alerts
                </p>
              </div>
            </div>
            {filteredIncidents.map((inc, i) => (
              <div key={i} style={{
                padding: "10px 14px",
                background: T.card,
                border: `1px solid ${T.border}`,
                borderRadius: 10,
                marginBottom: i < filteredIncidents.length - 1 ? 8 : 0,
              }}>
                <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
                  <span style={{
                    padding: "2px 8px", borderRadius: 4,
                    fontSize: 9, fontWeight: 700, textTransform: "uppercase", letterSpacing: 0.5,
                    fontFamily: "'JetBrains Mono', monospace",
                    background: inc.severity === "critical" ? "rgba(239,68,68,0.12)" : inc.severity === "high" ? "rgba(249,115,22,0.12)" : "rgba(245,158,11,0.12)",
                    color: inc.severity === "critical" ? T.danger : inc.severity === "high" ? T.accent : T.warning,
                  }}>
                    {inc.severity}
                  </span>
                  <span style={{
                    padding: "2px 8px", borderRadius: 4,
                    fontSize: 9, fontWeight: 600, textTransform: "uppercase",
                    fontFamily: "'JetBrains Mono', monospace",
                    background: "rgba(59,130,246,0.08)", color: "#3b82f6",
                  }}>
                    {inc.type}
                  </span>
                </div>
                <div style={{ fontSize: 13, fontWeight: 600, color: T.text, marginBottom: 2 }}>
                  {inc.title}
                </div>
                <div style={{ fontSize: 12, color: T.textMuted }}>
                  {inc.details}
                </div>
                {inc.suggested_action && (
                  <div style={{ fontSize: 11, color: T.accent, marginTop: 4, fontStyle: "italic" }}>
                    Suggested: {inc.suggested_action}
                  </div>
                )}
              </div>
            ))}
          </div>
        );
        })()}

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
              <option value="pending_human">Pending Human</option>
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

          {/* View toggle */}
          <div style={{
            display: "flex",
            border: `1px solid ${T.border}`,
            borderRadius: 8,
            overflow: "hidden",
          }}>
            {["card", "list"].map((mode) => (
              <button
                key={mode}
                onClick={() => setView(mode)}
                style={{
                  padding: "7px 14px",
                  fontSize: 12,
                  fontFamily: "'Inter', system-ui",
                  border: "none",
                  cursor: "pointer",
                  background: view === mode ? T.accentGlow : "transparent",
                  color: view === mode ? T.accent : T.textMuted,
                  fontWeight: view === mode ? 600 : 400,
                  textTransform: "capitalize",
                }}
              >
                {mode}
              </button>
            ))}
          </div>
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

        {/* ── Ticket List/Card View ── */}
        {!loading && filtered.length > 0 && (() => {
          const totalPages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
          const safePage = Math.min(page, totalPages);
          const pageItems = filtered.slice((safePage - 1) * PAGE_SIZE, safePage * PAGE_SIZE);

          return (
            <>
              {view === "list" ? (
                /* ── List View ── */
                <div>
                  {/* Header row */}
                  <div style={{
                    display: "grid",
                    gridTemplateColumns: "70px 1fr 100px 100px 90px",
                    padding: "8px 16px",
                    fontSize: 10,
                    fontWeight: 600,
                    fontFamily: "'JetBrains Mono', monospace",
                    color: T.textDim,
                    textTransform: "uppercase",
                    letterSpacing: 1,
                    borderBottom: `1px solid ${T.border}`,
                  }}>
                    <span>ID</span>
                    <span>Title</span>
                    <span>Priority</span>
                    <span>Status</span>
                    <span>Created</span>
                  </div>
                  {pageItems.map((t) => {
                    const p = priorityStyles[t.priority] || priorityStyles.medium;
                    const s = statusStyles[t.status] || statusStyles.routed;
                    return (
                      <div
                        key={t.id}
                        onClick={() => setSelectedTicket(t)}
                        style={{
                          display: "grid",
                          gridTemplateColumns: "70px 1fr 100px 100px 90px",
                          padding: "12px 16px",
                          fontSize: 12,
                          color: T.text,
                          borderBottom: `1px solid ${T.border}`,
                          cursor: "pointer",
                          transition: "background 0.15s",
                          alignItems: "center",
                        }}
                        onMouseEnter={(e) => (e.currentTarget.style.background = "rgba(255,255,255,0.04)")}
                        onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
                      >
                        <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 11, color: T.textDim }}>
                          #{t.id}
                        </span>
                        <span style={{
                          fontWeight: 500,
                          whiteSpace: "nowrap",
                          overflow: "hidden",
                          textOverflow: "ellipsis",
                          paddingRight: 12,
                        }}>
                          {t.title}
                        </span>
                        <span style={{
                          display: "inline-flex", alignItems: "center", gap: 4,
                          fontSize: 10, fontWeight: 600, color: p.color, textTransform: "capitalize",
                        }}>
                          <span style={{ width: 5, height: 5, borderRadius: "50%", background: p.dot, boxShadow: `0 0 6px ${p.dot}40` }} />
                          {t.priority}
                        </span>
                        <span style={{
                          display: "inline-flex", alignItems: "center", gap: 4,
                          fontSize: 10, fontWeight: 500, color: s.color, textTransform: "capitalize",
                        }}>
                          <span style={{ width: 5, height: 5, borderRadius: "50%", background: s.dot, boxShadow: `0 0 6px ${s.dot}40` }} />
                          {(t.status || "").replace(/_/g, " ")}
                        </span>
                        <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 10, color: T.textDim }}>
                          {timeAgo(t.created_at)}
                        </span>
                      </div>
                    );
                  })}
                </div>
              ) : (
                /* ── Card View ── */
                <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(300px, 1fr))", gap: 12 }}>
                  {pageItems.map((t) => {
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
                        {/* Top row: ID + badges */}
                        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
                          <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 11, color: T.textDim, fontWeight: 600 }}>
                            #{t.id}
                          </span>
                          <span style={{ flex: 1 }} />
                          <span style={{
                            display: "inline-flex", alignItems: "center", gap: 4,
                            fontSize: 10, fontWeight: 600, padding: "3px 10px", borderRadius: 10,
                            background: p.bg, color: p.color, textTransform: "capitalize",
                          }}>
                            <span style={{ width: 5, height: 5, borderRadius: "50%", background: p.dot, boxShadow: `0 0 6px ${p.dot}40` }} />
                            {t.priority}
                          </span>
                          <span style={{
                            display: "inline-flex", alignItems: "center", gap: 4,
                            fontSize: 10, fontWeight: 600, padding: "3px 10px", borderRadius: 10,
                            background: s.bg, color: s.color, textTransform: "capitalize",
                          }}>
                            <span style={{ width: 5, height: 5, borderRadius: "50%", background: s.dot, boxShadow: `0 0 6px ${s.dot}40` }} />
                            {(t.status || "").replace(/_/g, " ")}
                          </span>
                        </div>
                        {/* Title */}
                        <div style={{ fontSize: 14, fontWeight: 600, color: T.text, fontFamily: "'Inter', system-ui", marginBottom: 8, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                          {t.title}
                        </div>
                        {/* Description preview */}
                        <div style={{ fontSize: 12, color: T.textMuted, marginBottom: 12, display: "-webkit-box", WebkitLineClamp: 2, WebkitBoxOrient: "vertical", overflow: "hidden", lineHeight: 1.5 }}>
                          {t.description}
                        </div>
                        {/* Bottom row: confidence + team + time */}
                        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                          <div style={{ display: "flex", alignItems: "center", gap: 6, minWidth: 120 }}>
                            <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 10, color: T.textMuted }}>
                              {confidencePct}%
                            </span>
                            <div style={{ flex: 1, height: 4, borderRadius: 2, background: "rgba(255,255,255,0.06)", overflow: "hidden" }}>
                              <div style={{
                                width: `${confidencePct}%`, height: "100%", borderRadius: 2,
                                background: confidencePct > 70 ? T.success : confidencePct > 50 ? T.warning : T.danger,
                              }} />
                            </div>
                          </div>
                          {t.routed_to && (
                            <span style={{ fontSize: 10, fontWeight: 600, color: T.accent }}>{t.routed_to}</span>
                          )}
                          <span style={{ flex: 1 }} />
                          <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 10, color: T.textDim }}>
                            {timeAgo(t.created_at)}
                          </span>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}

              {/* ── Pagination ── */}
              {totalPages > 1 && (
                <div style={{
                  display: "flex",
                  justifyContent: "center",
                  alignItems: "center",
                  gap: 16,
                  marginTop: 24,
                  fontSize: 12,
                  color: T.textMuted,
                  fontFamily: "'JetBrains Mono', monospace",
                }}>
                  <button
                    disabled={safePage <= 1}
                    onClick={() => setPage((p) => Math.max(1, p - 1))}
                    style={{
                      background: "none", border: `1px solid ${T.border}`, borderRadius: 6,
                      color: safePage <= 1 ? T.textDim : T.text, padding: "6px 14px",
                      cursor: safePage <= 1 ? "default" : "pointer", fontSize: 12,
                    }}
                  >
                    ‹ Prev
                  </button>
                  <span>{safePage} / {totalPages}</span>
                  <button
                    disabled={safePage >= totalPages}
                    onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                    style={{
                      background: "none", border: `1px solid ${T.border}`, borderRadius: 6,
                      color: safePage >= totalPages ? T.textDim : T.text, padding: "6px 14px",
                      cursor: safePage >= totalPages ? "default" : "pointer", fontSize: 12,
                    }}
                  >
                    Next ›
                  </button>
                </div>
              )}
            </>
          );
        })()}
      </div>
    </div>
  );
}

// ── Small stat badge component ──
function StatBadge({ label, value, color }) {
  const { T } = useTheme();
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
