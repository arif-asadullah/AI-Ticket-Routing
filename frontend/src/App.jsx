import { useState, useEffect } from "react";
import DeskMindSplash from "./components/DeskMindSplash";
import DeskMindSpinner from "./components/DeskMindSpinner";
import LoginPage from "./components/LoginPage";
import StatusBar from "./components/StatusBar";
import TicketList from "./components/TicketList";
import ChatPanel from "./components/ChatPanel";
import UserManagement from "./components/UserManagement";
import DomainDashboard from "./components/DomainDashboard";
import { fetchTickets, createTicket, deleteTicket, fetchHealth, login, logout, fetchMe, isLoggedIn } from "./services/api";

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

  async function handleDelete(id) {
    try {
      await deleteTicket(id);
      setTickets((prev) => prev.filter((t) => t.id !== id));
      if (lastResult?.id === id) setLastResult(null);
    } catch {
      setError("Failed to delete ticket.");
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
              <StatusBar health={health} />
              <nav style={{ display: "flex", gap: 20, fontSize: 13, fontWeight: 500, alignItems: "center" }}>
                <a href="#dashboard" onClick={(e) => { e.preventDefault(); setActiveTab("dashboard"); }} style={{ color: activeTab === "dashboard" ? T.accent : T.textMuted, cursor: "pointer" }}>Dashboard</a>
                <a href="#tickets" onClick={(e) => { e.preventDefault(); setActiveTab("tickets"); }} style={{ color: activeTab === "tickets" ? T.accent : T.textMuted, cursor: "pointer" }}>New Ticket</a>
                <a href="#chat" onClick={(e) => { e.preventDefault(); setActiveTab("chat"); }} style={{ color: activeTab === "chat" ? T.accent : T.textMuted, cursor: "pointer" }}>Chat AI</a>
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

          {/* ── Chat Tab ── */}
          {activeTab === "chat" && <ChatPanel />}

          {/* ── Users Tab (admin only) ── */}
          {activeTab === "users" && user?.role === "admin" && (
            <main style={{ maxWidth: 960, margin: "0 auto", padding: "40px 24px 80px" }}>
              <UserManagement />
            </main>
          )}

          {/* ── Tickets Tab ── */}
          {activeTab === "tickets" && (
          <main style={{ maxWidth: 860, margin: "0 auto", padding: "40px 24px 80px" }}>

            {/* Error */}
            {error && (
              <div style={{
                display: "flex", alignItems: "center", gap: 10,
                background: "rgba(239,68,68,0.1)",
                color: T.danger,
                padding: "12px 16px", borderRadius: 10,
                marginBottom: 24, fontSize: 13,
                border: "1px solid rgba(239,68,68,0.2)",
              }}>
                <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
                  <circle cx="8" cy="8" r="7" stroke={T.danger} strokeWidth="1.5"/>
                  <line x1="8" y1="4.5" x2="8" y2="8.5" stroke={T.danger} strokeWidth="1.5" strokeLinecap="round"/>
                  <circle cx="8" cy="11" r="0.75" fill={T.danger}/>
                </svg>
                {error}
              </div>
            )}

            {/* ── Create Ticket Card ── */}
            <div style={{
              background: T.card,
              borderRadius: 16,
              border: `1px solid ${T.border}`,
              padding: 32,
              marginBottom: 32,
              backdropFilter: "blur(8px)",
            }}>
              <div style={{ marginBottom: 24 }}>
                <h1 style={{
                  fontFamily: "'Inter', system-ui",
                  fontSize: 22,
                  fontWeight: 600,
                  color: T.text,
                  marginBottom: 6,
                }}>
                  Submit a ticket
                </h1>
                <p style={{ color: T.textMuted, fontSize: 13 }}>
                  Describe the issue and DeskMind will classify and route it automatically.
                </p>
              </div>

              <form onSubmit={handleSubmit}>
                <div style={{ marginBottom: 16 }}>
                  <label style={{ display: "block", fontSize: 11, fontWeight: 600, color: T.textMuted, marginBottom: 6, letterSpacing: 1, textTransform: "uppercase", fontFamily: "'JetBrains Mono', monospace" }}>
                    Title
                  </label>
                  <FocusInput
                    type="text"
                    placeholder="Brief summary of the issue"
                    value={title}
                    onChange={(e) => setTitle(e.target.value)}
                  />
                </div>

                <div style={{ marginBottom: 16 }}>
                  <label style={{ display: "block", fontSize: 11, fontWeight: 600, color: T.textMuted, marginBottom: 6, letterSpacing: 1, textTransform: "uppercase", fontFamily: "'JetBrains Mono', monospace" }}>
                    Description
                  </label>
                  <FocusInput
                    as="textarea"
                    placeholder="Provide details — affected systems, error messages, impact..."
                    value={description}
                    onChange={(e) => setDescription(e.target.value)}
                    rows={4}
                    style={{ resize: "vertical", minHeight: 100 }}
                  />
                </div>

                <div style={{ display: "flex", gap: 12, alignItems: "flex-end" }}>
                  <div>
                    <label style={{ display: "block", fontSize: 11, fontWeight: 600, color: T.textMuted, marginBottom: 6, letterSpacing: 1, textTransform: "uppercase", fontFamily: "'JetBrains Mono', monospace" }}>
                      Priority
                    </label>
                    <div style={{ display: "flex", borderRadius: 8, overflow: "hidden", border: `1px solid ${T.border}` }}>
                      {["low", "medium", "high"].map((p) => (
                        <button
                          key={p}
                          type="button"
                          onClick={() => setPriority(p)}
                          style={{
                            padding: "8px 18px",
                            fontSize: 12,
                            fontWeight: priority === p ? 600 : 400,
                            border: "none",
                            cursor: "pointer",
                            textTransform: "capitalize",
                            fontFamily: "'Inter', system-ui",
                            background: priority === p
                              ? (p === "high" ? "rgba(239,68,68,0.15)" : p === "medium" ? "rgba(245,158,11,0.15)" : "rgba(34,197,94,0.15)")
                              : "transparent",
                            color: priority === p
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
                    disabled={!canSubmit}
                    style={{
                      flex: 1,
                      padding: "11px 24px",
                      background: canSubmit ? T.accent : "rgba(249,115,22,0.3)",
                      color: "#fff",
                      border: "none",
                      borderRadius: 10,
                      fontSize: 14,
                      fontWeight: 600,
                      fontFamily: "'Inter', system-ui",
                      cursor: canSubmit ? "pointer" : "not-allowed",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      gap: 8,
                      transition: "all 0.2s",
                      boxShadow: canSubmit ? "0 0 20px rgba(249,115,22,0.3)" : "none",
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
                          <path d="M14 2L7.5 14L5.5 8.5L2 7L14 2Z" stroke="#fff" strokeWidth="1.5" strokeLinejoin="round"/>
                        </svg>
                        Submit
                      </>
                    )}
                  </button>
                </div>
              </form>
            </div>

            {/* ── Classifying Spinner ── */}
            {isClassifying && (
              <div style={{
                textAlign: "center",
                padding: 48,
                background: T.card,
                borderRadius: 16,
                border: `1px solid ${T.border}`,
                marginBottom: 32,
                backdropFilter: "blur(8px)",
              }}>
                <DeskMindSpinner size="lg" label="Analyzing ticket..." />
                <p style={{ marginTop: 16, color: T.textMuted, fontSize: 13 }}>
                  Running classification and searching knowledge graph
                </p>
              </div>
            )}

            {/* ── Result Card ── */}
            {lastResult && !isClassifying && (
              <div style={{ marginBottom: 32, animation: "fadeIn 0.3s ease-out" }}>
                <style>{`@keyframes fadeIn { from { opacity:0; transform:translateY(8px) } to { opacity:1; transform:translateY(0) } }`}</style>

                {/* ── Classification Result ── */}
                <div style={{
                  padding: 24,
                  background: "rgba(34,197,94,0.05)",
                  borderRadius: 16,
                  border: "1px solid rgba(34,197,94,0.15)",
                  marginBottom: 12,
                }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 16 }}>
                    <div style={{
                      width: 36, height: 36, borderRadius: 10,
                      background: "rgba(34,197,94,0.1)",
                      display: "flex", alignItems: "center", justifyContent: "center",
                    }}>
                      <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
                        <path d="M3.75 9.75L7.5 13.5L14.25 4.5" stroke={T.success} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                      </svg>
                    </div>
                    <div>
                      <h3 style={{ margin: 0, fontSize: 15, fontWeight: 600, color: T.text }}>
                        Ticket #{lastResult.id} — {lastResult.status === "routed" ? "Routed" : "Escalated"}
                      </h3>
                      <p style={{ margin: 0, fontSize: 12, color: T.textMuted }}>
                        {lastResult.title}
                      </p>
                    </div>
                  </div>

                  <div style={{ display: "flex", gap: 10, flexWrap: "wrap", marginBottom: 16 }}>
                    <span style={{
                      padding: "5px 12px", borderRadius: 16, fontSize: 11, fontWeight: 600,
                      background: "rgba(249,115,22,0.12)", color: T.accent,
                    }}>
                      {lastResult.category}
                    </span>
                    <span style={{
                      padding: "5px 12px", borderRadius: 16, fontSize: 11, fontWeight: 600,
                      background: "rgba(34,197,94,0.12)", color: T.success,
                    }}>
                      {Math.round((lastResult.confidence_score || 0) * 100)}% confidence
                    </span>
                    <span style={{
                      padding: "5px 12px", borderRadius: 16, fontSize: 11, fontWeight: 600,
                      textTransform: "capitalize",
                      background: lastResult.priority === "high" || lastResult.priority === "critical" ? "rgba(239,68,68,0.12)" : lastResult.priority === "medium" ? "rgba(245,158,11,0.12)" : "rgba(34,197,94,0.12)",
                      color: lastResult.priority === "high" || lastResult.priority === "critical" ? T.danger : lastResult.priority === "medium" ? T.warning : T.success,
                    }}>
                      {lastResult.priority}
                    </span>
                  </div>

                  {/* Team + Expert */}
                  <div style={{ display: "flex", gap: 24, fontSize: 13, color: T.textMuted }}>
                    {lastResult.routed_to && (
                      <div>
                        <span style={{ color: T.textDim, fontSize: 10, textTransform: "uppercase", letterSpacing: 1, fontFamily: "'JetBrains Mono', monospace" }}>Team</span>
                        <div style={{ color: T.accent, fontWeight: 600, marginTop: 2 }}>{lastResult.routed_to}</div>
                      </div>
                    )}
                    {lastResult.recommended_expert && (
                      <div>
                        <span style={{ color: T.textDim, fontSize: 10, textTransform: "uppercase", letterSpacing: 1, fontFamily: "'JetBrains Mono', monospace" }}>Expert</span>
                        <div style={{ color: T.text, fontWeight: 500, marginTop: 2 }}>{lastResult.recommended_expert}</div>
                      </div>
                    )}
                    {lastResult.quality_score && (
                      <div>
                        <span style={{ color: T.textDim, fontSize: 10, textTransform: "uppercase", letterSpacing: 1, fontFamily: "'JetBrains Mono', monospace" }}>Input Quality</span>
                        <div style={{ color: lastResult.quality_score === "HIGH" ? T.success : lastResult.quality_score === "LOW" ? T.danger : T.warning, fontWeight: 500, marginTop: 2 }}>{lastResult.quality_score}</div>
                      </div>
                    )}
                  </div>

                  {/* AI Reasoning */}
                  {lastResult.ai_reasoning && (
                    <div style={{
                      marginTop: 16, padding: 12, borderRadius: 10,
                      background: "rgba(255,255,255,0.03)", border: `1px solid ${T.border}`,
                      fontSize: 12, color: T.textMuted, lineHeight: 1.5,
                    }}>
                      <span style={{ color: T.textDim, fontSize: 10, textTransform: "uppercase", letterSpacing: 1, fontFamily: "'JetBrains Mono', monospace" }}>AI Reasoning</span>
                      <div style={{ marginTop: 4, color: T.text }}>{lastResult.ai_reasoning}</div>
                    </div>
                  )}
                </div>

                {/* ── Suggested Resolution ── */}
                {lastResult.suggested_resolution && lastResult.suggested_resolution.length > 0 && (
                  <div style={{
                    padding: 24,
                    background: T.card,
                    borderRadius: 16,
                    border: `1px solid ${T.border}`,
                    marginBottom: 12,
                  }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 16 }}>
                      <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
                        <circle cx="10" cy="10" r="9" stroke={T.accent} strokeWidth="1.5" fill="none"/>
                        <path d="M10 5v5.5M10 13.5v.5" stroke={T.accent} strokeWidth="1.5" strokeLinecap="round"/>
                      </svg>
                      <div>
                        <h4 style={{ margin: 0, fontSize: 14, fontWeight: 600, color: T.text }}>Suggested Resolution</h4>
                        <p style={{ margin: 0, fontSize: 11, color: T.textMuted }}>
                          Based on similar past tickets
                          {lastResult.resolution_effectiveness && (
                            <span style={{ color: T.success }}> — {Math.round(lastResult.resolution_effectiveness * 100)}% effective</span>
                          )}
                        </p>
                      </div>
                    </div>

                    <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                      {lastResult.suggested_resolution.map((step, i) => (
                        <div key={i} style={{
                          display: "flex", gap: 12, alignItems: "flex-start",
                          padding: "10px 14px", borderRadius: 10,
                          background: "rgba(255,255,255,0.02)",
                          border: `1px solid ${T.border}`,
                        }}>
                          <span style={{
                            minWidth: 22, height: 22, borderRadius: "50%",
                            background: "rgba(249,115,22,0.15)", color: T.accent,
                            display: "flex", alignItems: "center", justifyContent: "center",
                            fontSize: 11, fontWeight: 700, fontFamily: "'JetBrains Mono', monospace",
                          }}>
                            {i + 1}
                          </span>
                          <span style={{ fontSize: 13, color: T.text, lineHeight: 1.5 }}>{step}</span>
                        </div>
                      ))}
                    </div>

                    {/* Runbook */}
                    {lastResult.suggested_runbook && (
                      <div style={{
                        marginTop: 16, padding: "10px 14px", borderRadius: 10,
                        background: "rgba(249,115,22,0.06)", border: "1px solid rgba(249,115,22,0.15)",
                        display: "flex", alignItems: "center", gap: 10,
                      }}>
                        <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
                          <rect x="2" y="1" width="12" height="14" rx="2" stroke={T.accent} strokeWidth="1.2" fill="none"/>
                          <line x1="5" y1="5" x2="11" y2="5" stroke={T.accent} strokeWidth="1" strokeLinecap="round" opacity="0.5"/>
                          <line x1="5" y1="8" x2="11" y2="8" stroke={T.accent} strokeWidth="1" strokeLinecap="round" opacity="0.5"/>
                          <line x1="5" y1="11" x2="9" y2="11" stroke={T.accent} strokeWidth="1" strokeLinecap="round" opacity="0.5"/>
                        </svg>
                        <div>
                          <span style={{ fontSize: 10, color: T.textDim, textTransform: "uppercase", letterSpacing: 1, fontFamily: "'JetBrains Mono', monospace" }}>Runbook</span>
                          <div style={{ fontSize: 12, color: T.accent, fontWeight: 500, marginTop: 1 }}>{lastResult.suggested_runbook}</div>
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}

            {/* ── Tickets Table ── */}
            <div style={{
              background: T.card,
              borderRadius: 16,
              border: `1px solid ${T.border}`,
              overflow: "hidden",
              backdropFilter: "blur(8px)",
            }}>
              <TicketList tickets={tickets} onDelete={handleDelete} user={user} />
            </div>
          </main>
          )}
        </div>
      )}
    </>
  );
}
