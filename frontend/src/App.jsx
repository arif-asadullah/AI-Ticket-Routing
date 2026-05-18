import { useState, useEffect, useCallback } from "react";
import DeskMindSplash from "./components/DeskMindSplash";
import DeskMindSpinner from "./components/DeskMindSpinner";
import LoginPage from "./components/LoginPage";
import ChatPanel from "./components/ChatPanel";
import UserManagement from "./components/UserManagement";
import DomainDashboard from "./components/DomainDashboard";
import AnalyticsDashboard from "./components/AnalyticsDashboard";
import GraphVisualization from "./components/GraphVisualization";
import EnrichmentCard from "./components/EnrichmentCard";
import { fetchTickets, createTicket, fetchHealth, login, logout, fetchMe, isLoggedIn } from "./services/api";
import { useSocket } from "./services/socket";
import { ThemeProvider, useTheme } from "./theme/ThemeContext";

import logoLandscapeDark from "./assets/logo/deskmind-logo-landscape-dark.svg";
import logoLandscapeLight from "./assets/logo/deskmind-logo-landscape.svg";
import icon from "./assets/logo/deskmind-icon.svg";

function getInputBase(T) {
  return {
    width: "100%",
    padding: "12px 16px",
    borderRadius: 10,
    border: `1px solid ${T.border}`,
    fontSize: 14,
    fontFamily: "'Inter', system-ui, sans-serif",
    outline: "none",
    boxSizing: "border-box",
    background: "rgba(255,255,255,0.03)",
    color: T.text,
    transition: "border-color 0.2s, box-shadow 0.2s",
  };
}

function getInputFocus(T) {
  return {
    borderColor: T.borderGlow,
    boxShadow: `0 0 0 3px ${T.accentGlow}`,
  };
}

function FocusInput({ as: Tag = "input", style, ...props }) {
  const { T } = useTheme();
  const [focused, setFocused] = useState(false);
  const inputBase = getInputBase(T);
  const inputFocus = getInputFocus(T);
  return (
    <Tag
      {...props}
      style={{ ...inputBase, ...style, ...(focused ? inputFocus : {}) }}
      onFocus={(e) => { setFocused(true); props.onFocus?.(e); }}
      onBlur={(e) => { setFocused(false); props.onBlur?.(e); }}
    />
  );
}

function AppContent() {
  const { T, mode, toggleTheme } = useTheme();
  const [user, setUser] = useState(null);
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [splashDone, setSplashDone] = useState(false);
  const [activeTab, setActiveTab] = useState("dashboard");
  const [showNewTicket, setShowNewTicket] = useState(false);
  const [showChat, setShowChat] = useState(false);
  const [isClassifying, setIsClassifying] = useState(false);
  const [tickets, setTickets] = useState([]);
  const [health, setHealth] = useState(null);
  const [error, setError] = useState(null);
  const [toasts, setToasts] = useState([]);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [priority, setPriority] = useState("medium");
  const [lastResult, setLastResult] = useState(null);

  // Check if already logged in on mount
  useEffect(() => {
    if (isLoggedIn()) {
      fetchMe()
        .then((u) => { setUser(u); setIsAuthenticated(true); })
        .catch(() => { logout(); setIsAuthenticated(false); });
    }
  }, []);

  useEffect(() => {
    if (splashDone && isAuthenticated) {
      loadTickets();
      loadHealth();
    }
  }, [splashDone, isAuthenticated]);

  // Socket.IO real-time updates
  const handleSocketEvent = useCallback((event, data) => {
    const labels = {
      "ticket:created": "New ticket",
      "ticket:updated": "Ticket updated",
      "ticket:resolved": "Ticket resolved",
      "ticket:deleted": "Ticket deleted",
    };
    const msg = `${labels[event] || event}: #${data.id || "?"} ${data.title ? "— " + data.title : ""}`;
    setToasts((prev) => [...prev.slice(-4), { id: Date.now(), msg }]);
    // Refresh tickets list
    loadTickets();
  }, []);
  useSocket(isAuthenticated ? handleSocketEvent : null);

  // Auto-dismiss toasts
  useEffect(() => {
    if (toasts.length === 0) return;
    const timer = setTimeout(() => setToasts((prev) => prev.slice(1)), 5000);
    return () => clearTimeout(timer);
  }, [toasts]);

  async function handleLogin(email, password) {
    await login(email, password);
    const u = await fetchMe();
    setUser(u);
    setIsAuthenticated(true);
  }

  function handleLogout() {
    logout();
    setUser(null);
    setIsAuthenticated(false);
    setTickets([]);
    setLastResult(null);
  }

  async function loadTickets() {
    try {
      const data = await fetchTickets();
      setTickets(data);
      setError(null);
    } catch {
      setError("Could not load tickets. Is the backend running?");
    }
  }

  async function loadHealth() {
    try {
      const data = await fetchHealth();
      setHealth(data);
    } catch {
      setHealth(null);
    }
  }

  // Poll health every 30s to detect degradation / recovery
  useEffect(() => {
    if (!isAuthenticated || !splashDone) return;
    const interval = setInterval(loadHealth, 30000);
    return () => clearInterval(interval);
  }, [isAuthenticated, splashDone]);

  async function handleSubmit(e) {
    e.preventDefault();
    if (!title.trim() || !description.trim()) return;
    setIsClassifying(true);
    setLastResult(null);
    setError(null);

    try {
      const [created] = await Promise.all([
        createTicket({ title, description, priority }),
        new Promise((r) => setTimeout(r, 1500)),
      ]);
      setLastResult(created);
      setTickets((prev) => [created, ...prev]);
      setTitle("");
      setDescription("");
      setPriority("medium");
    } catch {
      setError("Failed to create ticket. Check backend connection.");
    } finally {
      setIsClassifying(false);
    }
  }


  const canSubmit = title.trim() && description.trim() && !isClassifying;

  return (
    <>
      <style>{`
        *, *::before, *::after { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: 'Inter', system-ui, -apple-system, sans-serif; background: ${T.bg}; color: ${T.text}; }
        a { text-decoration: none; }
        ::placeholder { color: ${T.textDim}; }
        ::-webkit-scrollbar { width: 6px; }
        ::-webkit-scrollbar-track { background: transparent; }
        ::-webkit-scrollbar-thumb { background: rgba(255,255,255,0.1); border-radius: 3px; }
      `}</style>

      {/* ── Splash ── */}
      {!splashDone && <DeskMindSplash onFinished={() => setSplashDone(true)} />}

      {/* ── Login Gate ── */}
      {splashDone && !isAuthenticated && (
        <LoginPage onLogin={handleLogin} />
      )}

      {/* ── Dashboard ── */}
      {splashDone && isAuthenticated && (
        <div style={{ minHeight: "100vh" }}>

          {/* Header */}
          <header style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            padding: "12px 32px",
            borderBottom: `1px solid ${T.border}`,
            background: mode === "dark" ? "rgba(12,12,15,0.8)" : "rgba(255,255,255,0.85)",
            backdropFilter: "blur(12px)",
            position: "sticky",
            top: 0,
            zIndex: 100,
          }}>
            <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
              <img src={mode === "dark" ? logoLandscapeDark : logoLandscapeLight} alt="DeskMind" style={{ height: 40 }} />
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 20 }}>
              <nav style={{ display: "flex", gap: 20, fontSize: 13, fontWeight: 500, alignItems: "center" }}>
                <a href="#dashboard" onClick={(e) => { e.preventDefault(); setActiveTab("dashboard"); }} style={{ color: activeTab === "dashboard" ? T.accent : T.textMuted, cursor: "pointer" }}>Dashboard</a>
                <a href="#new-ticket" onClick={(e) => { e.preventDefault(); setShowNewTicket(true); setLastResult(null); }} style={{ color: T.textMuted, cursor: "pointer" }}>New Ticket</a>
                <a href="#analytics" onClick={(e) => { e.preventDefault(); setActiveTab("analytics"); }} style={{ color: activeTab === "analytics" ? T.accent : T.textMuted, cursor: "pointer" }}>Analytics</a>
                {user?.role === "admin" && (
                  <a href="#graph" onClick={(e) => { e.preventDefault(); setActiveTab("graph"); }} style={{ color: activeTab === "graph" ? T.accent : T.textMuted, cursor: "pointer" }}>Graph</a>
                )}
                {user?.role === "admin" && (
                  <a href="#users" onClick={(e) => { e.preventDefault(); setActiveTab("users"); }} style={{ color: activeTab === "users" ? T.accent : T.textMuted, cursor: "pointer" }}>Users</a>
                )}
                {/* Theme toggle */}
                <button
                  onClick={toggleTheme}
                  title={mode === "dark" ? "Switch to light mode" : "Switch to dark mode"}
                  style={{
                    background: "none",
                    border: `1px solid ${T.border}`,
                    borderRadius: 8,
                    padding: "6px 8px",
                    cursor: "pointer",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    color: T.textMuted,
                    transition: "all 0.2s",
                  }}
                  onMouseEnter={(e) => { e.currentTarget.style.borderColor = T.accent; e.currentTarget.style.color = T.accent; }}
                  onMouseLeave={(e) => { e.currentTarget.style.borderColor = T.border; e.currentTarget.style.color = T.textMuted; }}
                >
                  {mode === "dark" ? (
                    <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
                      <circle cx="8" cy="8" r="3.5" stroke="currentColor" strokeWidth="1.5" />
                      <path d="M8 1.5v1M8 13.5v1M1.5 8h1M13.5 8h1M3.4 3.4l.7.7M11.9 11.9l.7.7M3.4 12.6l.7-.7M11.9 4.1l.7-.7" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" />
                    </svg>
                  ) : (
                    <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
                      <path d="M14 9.3A6 6 0 016.7 2 6 6 0 1014 9.3z" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
                    </svg>
                  )}
                </button>
                <div style={{ width: 1, height: 20, background: T.border, margin: "0 4px" }} />
                <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                  <div style={{ textAlign: "right" }}>
                    <div style={{ fontSize: 12, color: T.text, fontWeight: 500 }}>{user?.email}</div>
                    <div style={{ fontSize: 10, color: T.accent, textTransform: "uppercase", fontFamily: "'JetBrains Mono', monospace" }}>
                      {user?.role}{user?.team_name ? ` \u2022 ${user.team_name}` : ""}
                    </div>
                  </div>
                  <button
                    onClick={handleLogout}
                    style={{
                      padding: "6px 12px",
                      background: "rgba(239,68,68,0.1)",
                      border: "1px solid rgba(239,68,68,0.2)",
                      borderRadius: 6,
                      color: T.danger,
                      fontSize: 11,
                      fontWeight: 500,
                      cursor: "pointer",
                    }}
                  >
                    Logout
                  </button>
                </div>
              </nav>
            </div>
          </header>

          {/* ── Degraded Mode Banner ── */}
          {health && health.degradation_level < 4 && (
            <div style={{
              padding: "10px 32px",
              background: health.degradation_level <= 1
                ? "linear-gradient(90deg, #dc2626, #b91c1c)"
                : "linear-gradient(90deg, #d97706, #b45309)",
              color: "#fff",
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              fontSize: 13,
              fontWeight: 500,
              fontFamily: "'Inter', system-ui",
            }}>
              <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
                  <path d="M8 1l7 13H1L8 1z" fill="none" stroke="#fff" strokeWidth="1.5" strokeLinejoin="round" />
                  <path d="M8 6v3" stroke="#fff" strokeWidth="1.5" strokeLinecap="round" />
                  <circle cx="8" cy="11.5" r="0.75" fill="#fff" />
                </svg>
                <span>
                  <strong>Degraded Mode (Level {health.degradation_level}/4)</strong>
                  {" — "}{health.message}
                </span>
              </div>
              <div style={{ display: "flex", alignItems: "center", gap: 16, fontSize: 12 }}>
                {health.pending_human_count > 0 && (
                  <span style={{
                    padding: "3px 10px",
                    background: "rgba(255,255,255,0.2)",
                    borderRadius: 12,
                    fontWeight: 600,
                  }}>
                    {health.pending_human_count} ticket{health.pending_human_count !== 1 ? "s" : ""} awaiting human review
                  </span>
                )}
                <span style={{ opacity: 0.7 }}>
                  Ollama: {health.ollama === "connected" ? "UP" : "DOWN"}
                </span>
              </div>
            </div>
          )}

          {/* ── Domain Dashboard Tab ── */}
          {activeTab === "dashboard" && user && (
            <DomainDashboard user={user} onBack={() => setActiveTab("tickets")} refreshKey={tickets.length} />
          )}


          {/* ── Analytics Tab ── */}
          {activeTab === "analytics" && user && (
            <AnalyticsDashboard user={user} />
          )}

          {/* ── Graph Tab (admin only) ── */}
          {activeTab === "graph" && user?.role === "admin" && (
            <GraphVisualization user={user} />
          )}

          {/* ── Users Tab (admin only) ── */}
          {activeTab === "users" && user?.role === "admin" && (
            <main style={{ maxWidth: 960, margin: "0 auto", padding: "40px 24px 80px" }}>
              <UserManagement />
            </main>
          )}

          {/* ── Tickets Tab ── */}
          {/* ── New Ticket Modal ── */}
          {showNewTicket && (
            <div
              style={{
                position: "fixed", inset: 0, zIndex: 200,
                background: "rgba(0,0,0,0.6)", backdropFilter: "blur(4px)",
                display: "flex", alignItems: "center", justifyContent: "center",
                padding: 24,
              }}
              onClick={(e) => { if (e.target === e.currentTarget && !isClassifying) setShowNewTicket(false); }}
            >
              <div style={{
                background: T.bgAlt, borderRadius: 20,
                border: `1px solid ${T.border}`,
                padding: 32, width: "100%", maxWidth: 560,
                maxHeight: "90vh", overflowY: "auto",
                boxShadow: "0 24px 80px rgba(0,0,0,0.5)",
              }}>
                {/* Header */}
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 24 }}>
                  <div>
                    <h2 style={{ margin: 0, fontSize: 20, fontWeight: 600, color: T.text, fontFamily: "'Inter', system-ui" }}>
                      {lastResult ? "Ticket Created" : "New Ticket"}
                    </h2>
                    {!lastResult && (
                      <p style={{ margin: "4px 0 0", fontSize: 12, color: T.textMuted }}>
                        DeskMind will classify and route it automatically.
                      </p>
                    )}
                  </div>
                  {!isClassifying && (
                    <button
                      onClick={() => setShowNewTicket(false)}
                      style={{ background: "none", border: "none", color: T.textMuted, cursor: "pointer", fontSize: 20, padding: 4 }}
                    >
                      ✕
                    </button>
                  )}
                </div>

                {/* Classifying state */}
                {isClassifying && (
                  <div style={{ textAlign: "center", padding: "40px 0" }}>
                    <DeskMindSpinner size="lg" label="Analyzing ticket..." />
                    <p style={{ marginTop: 16, color: T.textMuted, fontSize: 13 }}>
                      Running classification and searching knowledge graph
                    </p>
                  </div>
                )}

                {/* Result */}
                {lastResult && !isClassifying && (
                  <div>
                    <div style={{
                      padding: 20, borderRadius: 14,
                      background: "rgba(34,197,94,0.05)", border: "1px solid rgba(34,197,94,0.15)",
                      marginBottom: 16,
                    }}>
                      <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 12 }}>
                        <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
                          <path d="M3.75 9.75L7.5 13.5L14.25 4.5" stroke={T.success} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                        </svg>
                        <h3 style={{ margin: 0, fontSize: 15, fontWeight: 600, color: T.text }}>
                          #{lastResult.id} — {lastResult.status === "routed" ? "Routed" : "Escalated"}
                        </h3>
                      </div>
                      <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 12 }}>
                        <span style={{ padding: "4px 10px", borderRadius: 12, fontSize: 11, fontWeight: 600, background: "rgba(249,115,22,0.12)", color: T.accent }}>{lastResult.category}</span>
                        <span style={{ padding: "4px 10px", borderRadius: 12, fontSize: 11, fontWeight: 600, background: "rgba(34,197,94,0.12)", color: T.success }}>{Math.round((lastResult.confidence_score || 0) * 100)}%</span>
                        {lastResult.routed_to && <span style={{ padding: "4px 10px", borderRadius: 12, fontSize: 11, fontWeight: 600, background: "rgba(59,130,246,0.12)", color: "#3b82f6" }}>{lastResult.routed_to}</span>}
                      </div>
                      {lastResult.ai_reasoning && (
                        <div style={{ fontSize: 12, color: T.textMuted, lineHeight: 1.5 }}>{lastResult.ai_reasoning}</div>
                      )}
                      {/* Enrichment Agent — interactive questions for vague tickets */}
                      <EnrichmentCard
                        enrichment={lastResult.enrichment}
                        ticket={lastResult}
                        interactive={true}
                        onEnriched={(updated) => {
                          setLastResult(updated);
                          loadTickets();
                        }}
                      />
                    </div>
                    <button
                      onClick={() => { setLastResult(null); setShowNewTicket(false); }}
                      style={{
                        width: "100%", padding: "11px 24px",
                        background: T.accent, color: "#fff", border: "none",
                        borderRadius: 10, fontSize: 14, fontWeight: 600,
                        cursor: "pointer", fontFamily: "'Inter', system-ui",
                        boxShadow: "0 0 20px rgba(249,115,22,0.3)",
                        display: lastResult.enrichment?.needed && !lastResult.enrichment?.answers ? "none" : "block",
                      }}
                    >
                      Done
                    </button>
                  </div>
                )}

                {/* Form */}
                {!lastResult && !isClassifying && (
                  <form onSubmit={handleSubmit}>
                    {error && (
                      <div style={{ color: T.danger, fontSize: 13, marginBottom: 14, padding: "8px 12px", background: "rgba(239,68,68,0.1)", borderRadius: 8 }}>
                        {error}
                      </div>
                    )}
                    <div style={{ marginBottom: 16 }}>
                      <label style={{ display: "block", fontSize: 11, fontWeight: 600, color: T.textMuted, marginBottom: 6, letterSpacing: 1, textTransform: "uppercase", fontFamily: "'JetBrains Mono', monospace" }}>Title</label>
                      <FocusInput type="text" placeholder="Brief summary of the issue" value={title} onChange={(e) => setTitle(e.target.value)} />
                    </div>
                    <div style={{ marginBottom: 16 }}>
                      <label style={{ display: "block", fontSize: 11, fontWeight: 600, color: T.textMuted, marginBottom: 6, letterSpacing: 1, textTransform: "uppercase", fontFamily: "'JetBrains Mono', monospace" }}>Description</label>
                      <FocusInput as="textarea" placeholder="Provide details — affected systems, error messages, impact..." value={description} onChange={(e) => setDescription(e.target.value)} rows={4} style={{ resize: "vertical", minHeight: 100 }} />
                    </div>
                    <div style={{ display: "flex", gap: 12, alignItems: "flex-end" }}>
                      <div>
                        <label style={{ display: "block", fontSize: 11, fontWeight: 600, color: T.textMuted, marginBottom: 6, letterSpacing: 1, textTransform: "uppercase", fontFamily: "'JetBrains Mono', monospace" }}>Priority</label>
                        <div style={{ display: "flex", borderRadius: 8, overflow: "hidden", border: `1px solid ${T.border}` }}>
                          {["low", "medium", "high"].map((p) => (
                            <button key={p} type="button" onClick={() => setPriority(p)} style={{
                              padding: "8px 18px", fontSize: 12, fontWeight: priority === p ? 600 : 400,
                              border: "none", cursor: "pointer", textTransform: "capitalize", fontFamily: "'Inter', system-ui",
                              background: priority === p ? (p === "high" ? "rgba(239,68,68,0.15)" : p === "medium" ? "rgba(245,158,11,0.15)" : "rgba(34,197,94,0.15)") : "transparent",
                              color: priority === p ? (p === "high" ? T.danger : p === "medium" ? T.warning : T.success) : T.textDim,
                              borderRight: p !== "high" ? `1px solid ${T.border}` : "none",
                            }}>{p}</button>
                          ))}
                        </div>
                      </div>
                      <button type="submit" disabled={!canSubmit} style={{
                        flex: 1, padding: "11px 24px",
                        background: canSubmit ? T.accent : "rgba(249,115,22,0.3)",
                        color: "#fff", border: "none", borderRadius: 10, fontSize: 14, fontWeight: 600,
                        fontFamily: "'Inter', system-ui", cursor: canSubmit ? "pointer" : "not-allowed",
                        display: "flex", alignItems: "center", justifyContent: "center", gap: 8,
                        boxShadow: canSubmit ? "0 0 20px rgba(249,115,22,0.3)" : "none",
                      }}>
                        <svg width="14" height="14" viewBox="0 0 16 16" fill="none">
                          <path d="M14 2L7.5 14L5.5 8.5L2 7L14 2Z" stroke="#fff" strokeWidth="1.5" strokeLinejoin="round"/>
                        </svg>
                        Submit
                      </button>
                    </div>
                  </form>
                )}
              </div>
            </div>
          )}
          {/* ── Toast Notifications ── */}
          {toasts.length > 0 && (
            <div style={{ position: "fixed", top: 76, right: 24, zIndex: 400, display: "flex", flexDirection: "column", gap: 8 }}>
              {toasts.map((t) => (
                <div key={t.id} style={{
                  background: "rgba(17,17,20,0.95)",
                  border: `1px solid ${T.border}`,
                  borderLeft: `3px solid ${T.accent}`,
                  borderRadius: 10,
                  padding: "10px 16px",
                  fontSize: 12,
                  color: T.text,
                  backdropFilter: "blur(8px)",
                  boxShadow: "0 8px 24px rgba(0,0,0,0.4)",
                  maxWidth: 320,
                  animation: "chatSlideUp 0.2s ease-out",
                  fontFamily: "'Inter', system-ui",
                }}>
                  {t.msg}
                </div>
              ))}
            </div>
          )}

          {/* ── Floating Chat ── */}
          <style>{`
            @keyframes chatSlideUp { from { opacity:0; transform:translateY(16px) } to { opacity:1; transform:translateY(0) } }
            @keyframes fabPulse { 0%,100% { box-shadow: 0 0 0 0 rgba(249,115,22,0.4); } 50% { box-shadow: 0 0 0 10px rgba(249,115,22,0); } }
          `}</style>

          {/* FAB — Nexa AI */}
          <button
            onClick={() => setShowChat((v) => !v)}
            style={{
              position: "fixed",
              bottom: 24,
              right: 24,
              zIndex: 301,
              height: 48,
              borderRadius: 24,
              border: "1px solid rgba(249,115,22,0.3)",
              background: "linear-gradient(135deg, #F97316, #ea580c)",
              color: "#fff",
              cursor: "pointer",
              display: "flex",
              alignItems: "center",
              gap: 8,
              padding: showChat ? "0 16px" : "0 18px 0 14px",
              boxShadow: "0 4px 24px rgba(249,115,22,0.4)",
              animation: showChat ? "none" : "fabPulse 2.5s ease-in-out infinite",
              transition: "all 0.2s",
              fontFamily: "'Inter', system-ui",
              fontSize: 13,
              fontWeight: 600,
              letterSpacing: 0.3,
            }}
          >
            {showChat ? (
              <>
                <svg width="16" height="16" viewBox="0 0 20 20" fill="none">
                  <path d="M5 5l10 10M15 5L5 15" stroke="#fff" strokeWidth="2" strokeLinecap="round" />
                </svg>
                Close
              </>
            ) : (
              <>
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
                  <path d="M21 11.5a8.38 8.38 0 01-.9 3.8 8.5 8.5 0 01-7.6 4.7 8.38 8.38 0 01-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 01-.9-3.8 8.5 8.5 0 014.7-7.6 8.38 8.38 0 013.8-.9h.5a8.48 8.48 0 018 8v.5z" stroke="#fff" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
                Ask Mindy
              </>
            )}
          </button>

          {/* Chat Panel */}
          {showChat && (
            <div style={{
              position: "fixed",
              bottom: 84,
              right: 24,
              zIndex: 300,
              width: 420,
              height: "calc(100vh - 140px)",
              maxHeight: 700,
              borderRadius: 16,
              border: `1px solid ${T.border}`,
              background: T.bgAlt,
              boxShadow: "0 16px 60px rgba(0,0,0,0.5)",
              overflow: "hidden",
              animation: "chatSlideUp 0.2s ease-out",
              display: "flex",
              flexDirection: "column",
            }}>
              <ChatPanel compact onClose={() => setShowChat(false)} />
            </div>
          )}
        </div>
      )}
    </>
  );
}

export default function App() {
  return (
    <ThemeProvider>
      <AppContent />
    </ThemeProvider>
  );
}
