import { useState, useEffect } from "react";
import DeskMindSplash from "./components/DeskMindSplash";
import DeskMindSpinner from "./components/DeskMindSpinner";
import LandingPage from "./components/LandingPage";
import StatusBar from "./components/StatusBar";
import TicketList from "./components/TicketList";
import { fetchTickets, createTicket, deleteTicket, fetchHealth } from "./services/api";

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
  const [splashDone, setSplashDone] = useState(false);
  const [showDashboard, setShowDashboard] = useState(false);
  const [isClassifying, setIsClassifying] = useState(false);
  const [tickets, setTickets] = useState([]);
  const [health, setHealth] = useState(null);
  const [error, setError] = useState(null);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [priority, setPriority] = useState("medium");
  const [lastResult, setLastResult] = useState(null);

  useEffect(() => {
    if (splashDone) {
      loadTickets();
      loadHealth();
    }
  }, [splashDone]);

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

      {/* ── Landing Page ── */}
      {splashDone && !showDashboard && (
        <LandingPage
          onEnter={() => setShowDashboard(true)}
          health={health}
          ticketCount={tickets.length}
        />
      )}

      {/* ── Dashboard ── */}
      {splashDone && showDashboard && (
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
              <nav style={{ display: "flex", gap: 20, fontSize: 13, fontWeight: 500 }}>
                <a href="#tickets" style={{ color: T.accent }}>Tickets</a>
                <a href="#dashboard" style={{ color: T.textMuted }}>Dashboard</a>
                <a href="#evaluation" style={{ color: T.textMuted }}>Evaluation</a>
              </nav>
            </div>
          </header>

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
              <div style={{
                padding: 24,
                background: "rgba(34,197,94,0.05)",
                borderRadius: 16,
                border: "1px solid rgba(34,197,94,0.15)",
                marginBottom: 32,
                animation: "fadeIn 0.3s ease-out",
              }}>
                <style>{`@keyframes fadeIn { from { opacity:0; transform:translateY(8px) } to { opacity:1; transform:translateY(0) } }`}</style>

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
                      Ticket #{lastResult.id} routed
                    </h3>
                    <p style={{ margin: 0, fontSize: 12, color: T.textMuted }}>
                      {lastResult.title}
                    </p>
                  </div>
                </div>

                <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
                  <span style={{
                    padding: "5px 12px", borderRadius: 16, fontSize: 11, fontWeight: 600,
                    background: "rgba(249,115,22,0.12)", color: T.accent,
                  }}>
                    {lastResult.routed_to}
                  </span>
                  <span style={{
                    padding: "5px 12px", borderRadius: 16, fontSize: 11, fontWeight: 600,
                    background: "rgba(34,197,94,0.12)", color: T.success,
                  }}>
                    {lastResult.status}
                  </span>
                  <span style={{
                    padding: "5px 12px", borderRadius: 16, fontSize: 11, fontWeight: 600,
                    textTransform: "capitalize",
                    background: lastResult.priority === "high" ? "rgba(239,68,68,0.12)" : lastResult.priority === "medium" ? "rgba(245,158,11,0.12)" : "rgba(34,197,94,0.12)",
                    color: lastResult.priority === "high" ? T.danger : lastResult.priority === "medium" ? T.warning : T.success,
                  }}>
                    {lastResult.priority}
                  </span>
                </div>
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
              <TicketList tickets={tickets} onDelete={handleDelete} />
            </div>
          </main>
        </div>
      )}
    </>
  );
}
