import { useState, useEffect } from "react";
import DeskMindSplash from "./components/DeskMindSplash";
import DeskMindSpinner from "./components/DeskMindSpinner";
import LoginPage from "./components/LoginPage";
import ChatPanel from "./components/ChatPanel";
import UserManagement from "./components/UserManagement";
import DomainDashboard from "./components/DomainDashboard";
import AnalyticsDashboard from "./components/AnalyticsDashboard";
import { fetchTickets, createTicket, fetchHealth, login, logout, fetchMe, isLoggedIn } from "./services/api";

import logoLandscapeDark from "./assets/logo/deskmind-logo-landscape-dark.svg";
import icon from "./assets/logo/deskmind-icon.svg";

// ── Theme tokens ──
const T = {
  bg: "#0C0C0F",
  card: "rgba(255,255,255,0.04)",
  cardHover: "rgba(255,255,255,0.07)",
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

const inputBase = {
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

const inputFocus = {
  borderColor: T.borderGlow,
  boxShadow: `0 0 0 3px ${T.accentGlow}`,
};

function FocusInput({ as: Tag = "input", style, ...props }) {
  const [focused, setFocused] = useState(false);
  return (
    <Tag
      {...props}
      style={{ ...inputBase, ...style, ...(focused ? inputFocus : {}) }}
      onFocus={(e) => { setFocused(true); props.onFocus?.(e); }}
      onBlur={(e) => { setFocused(false); props.onBlur?.(e); }}
    />
  );
}

export default function App() {
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
            background: "rgba(12,12,15,0.8)",
            backdropFilter: "blur(12px)",
            position: "sticky",
            top: 0,
            zIndex: 100,
          }}>
            <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
              <img src={logoLandscapeDark} alt="DeskMind" style={{ height: 40 }} />
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 20 }}>
              <nav style={{ display: "flex", gap: 20, fontSize: 13, fontWeight: 500, alignItems: "center" }}>
                <a href="#dashboard" onClick={(e) => { e.preventDefault(); setActiveTab("dashboard"); }} style={{ color: activeTab === "dashboard" ? T.accent : T.textMuted, cursor: "pointer" }}>Dashboard</a>
                <a href="#new-ticket" onClick={(e) => { e.preventDefault(); setShowNewTicket(true); setLastResult(null); }} style={{ color: T.textMuted, cursor: "pointer" }}>New Ticket</a>
                <a href="#analytics" onClick={(e) => { e.preventDefault(); setActiveTab("analytics"); }} style={{ color: activeTab === "analytics" ? T.accent : T.textMuted, cursor: "pointer" }}>Analytics</a>
                {user?.role === "admin" && (
                  <a href="#users" onClick={(e) => { e.preventDefault(); setActiveTab("users"); }} style={{ color: activeTab === "users" ? T.accent : T.textMuted, cursor: "pointer" }}>Users</a>
                )}
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

          {/* ── Domain Dashboard Tab ── */}
          {activeTab === "dashboard" && user && (
            <DomainDashboard user={user} onBack={() => setActiveTab("tickets")} />
          )}


          {/* ── Analytics Tab ── */}
          {activeTab === "analytics" && user && (
            <AnalyticsDashboard user={user} />
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
                background: "#141418", borderRadius: 20,
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
                    </div>
                    <button
                      onClick={() => { setLastResult(null); setShowNewTicket(false); }}
                      style={{
                        width: "100%", padding: "11px 24px",
                        background: T.accent, color: "#fff", border: "none",
                        borderRadius: 10, fontSize: 14, fontWeight: 600,
                        cursor: "pointer", fontFamily: "'Inter', system-ui",
                        boxShadow: "0 0 20px rgba(249,115,22,0.3)",
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
              background: "#111114",
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
