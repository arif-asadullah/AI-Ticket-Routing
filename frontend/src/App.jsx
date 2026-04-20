import { useState, useEffect } from "react";
import DeskMindSplash from "./components/DeskMindSplash";
import DeskMindSpinner from "./components/DeskMindSpinner";
import StatusBar from "./components/StatusBar";
import TicketList from "./components/TicketList";
import { fetchTickets, createTicket, deleteTicket, fetchHealth } from "./services/api";

import logo from "./assets/logo/deskmind-logo.svg";
import icon from "./assets/logo/deskmind-icon.svg";

export default function App() {
  const [splashDone, setSplashDone] = useState(false);
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

  async function handleSubmit() {
    if (!title.trim() || !description.trim()) return;
    setIsClassifying(true);
    setLastResult(null);
    setError(null);

    try {
      const created = await createTicket({ title, description, priority });
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
    } catch {
      setError("Failed to delete ticket.");
    }
  }

  return (
    <>
      {!splashDone && <DeskMindSplash onFinished={() => setSplashDone(true)} />}

      {splashDone && (
        <div style={{ minHeight: "100vh", background: "#FAFAF9" }}>

          <header style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            padding: "16px 32px",
            borderBottom: "1px solid #E7E5E4",
            background: "#fff"
          }}>
            <img src={logo} alt="DeskMind" style={{ height: 80 }} />

            <div style={{ display: "flex", alignItems: "center", gap: 24 }}>
              <StatusBar health={health} />
              <nav style={{ display: "flex", gap: 24, fontSize: 14, color: "#78716C" }}>
                <a href="#tickets" style={{ color: "#1C1917", fontWeight: 500 }}>Tickets</a>
                <a href="#dashboard" style={{ color: "#78716C" }}>Dashboard</a>
                <a href="#evaluation" style={{ color: "#78716C" }}>Evaluation</a>
              </nav>
            </div>
          </header>

          <main style={{ maxWidth: 640, margin: "48px auto", padding: "0 24px" }}>

            {error && (
              <div style={{
                background: "#fef2f2",
                color: "#dc2626",
                padding: "12px 16px",
                borderRadius: 8,
                marginBottom: 24,
                fontSize: 14
              }}>
                {error}
              </div>
            )}

            <h1 style={{
              fontFamily: "Georgia, serif",
              fontSize: 28,
              fontWeight: 400,
              color: "#1C1917",
              marginBottom: 8
            }}>
              Submit a ticket
            </h1>
            <p style={{ color: "#78716C", fontSize: 14, marginBottom: 32 }}>
              Enter the ticket description and DeskMind will classify and route it.
            </p>

            <input
              type="text"
              placeholder="Ticket title"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              style={{
                width: "100%",
                padding: 12,
                borderRadius: 10,
                border: "1px solid #D6D3D1",
                fontSize: 14,
                fontFamily: "system-ui, sans-serif",
                outline: "none",
                boxSizing: "border-box",
                marginBottom: 12
              }}
            />

            <textarea
              placeholder="Describe the IT issue..."
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={4}
              style={{
                width: "100%",
                padding: 12,
                borderRadius: 10,
                border: "1px solid #D6D3D1",
                fontSize: 14,
                fontFamily: "system-ui, sans-serif",
                resize: "vertical",
                outline: "none",
                boxSizing: "border-box",
                marginBottom: 12
              }}
            />

            <div style={{ display: "flex", gap: 12, marginBottom: 16 }}>
              <select
                value={priority}
                onChange={(e) => setPriority(e.target.value)}
                style={{
                  padding: "10px 16px",
                  borderRadius: 8,
                  border: "1px solid #D6D3D1",
                  fontSize: 14,
                  fontFamily: "system-ui, sans-serif",
                  outline: "none",
                  background: "#fff"
                }}
              >
                <option value="low">Low</option>
                <option value="medium">Medium</option>
                <option value="high">High</option>
              </select>

              <button
                onClick={handleSubmit}
                disabled={isClassifying || !title.trim() || !description.trim()}
                style={{
                  flex: 1,
                  padding: "12px 32px",
                  background: isClassifying ? "#FED7AA" : "#F97316",
                  color: "#fff",
                  border: "none",
                  borderRadius: 8,
                  fontSize: 14,
                  fontWeight: 500,
                  cursor: isClassifying ? "wait" : "pointer",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  gap: 8,
                  opacity: (!title.trim() || !description.trim()) ? 0.5 : 1
                }}
              >
                {isClassifying ? (
                  <>
                    <DeskMindSpinner size="sm" />
                    Classifying...
                  </>
                ) : (
                  "Classify & Route"
                )}
              </button>
            </div>

            {isClassifying && (
              <div style={{
                marginTop: 32,
                textAlign: "center",
                padding: 48,
                background: "#fff",
                borderRadius: 16,
                border: "1px solid #E7E5E4"
              }}>
                <DeskMindSpinner size="lg" label="Analyzing ticket..." />
                <p style={{ marginTop: 16, color: "#78716C", fontSize: 14 }}>
                  Running classification and searching knowledge graph
                </p>
              </div>
            )}

            {lastResult && !isClassifying && (
              <div style={{
                marginTop: 32,
                padding: 24,
                background: "#fff",
                borderRadius: 16,
                border: "1px solid #E7E5E4"
              }}>
                <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 16 }}>
                  <img src={icon} alt="" style={{ width: 32, height: 32, borderRadius: 8 }} />
                  <div>
                    <h3 style={{ margin: 0, fontSize: 16, fontWeight: 500, color: "#1C1917" }}>Routed successfully</h3>
                    <p style={{ margin: 0, fontSize: 12, color: "#A8A29E" }}>Ticket #{lastResult.id}</p>
                  </div>
                </div>

                <div style={{ display: "flex", gap: 16 }}>
                  <div style={{
                    padding: "8px 16px",
                    background: "#FFF7ED",
                    borderRadius: 8,
                    fontSize: 14,
                    color: "#C2410C",
                    fontWeight: 500
                  }}>
                    {lastResult.routed_to}
                  </div>
                  <div style={{
                    padding: "8px 16px",
                    background: "#F0FDF4",
                    borderRadius: 8,
                    fontSize: 14,
                    color: "#166534",
                    fontWeight: 500
                  }}>
                    {lastResult.status}
                  </div>
                  <div style={{
                    padding: "8px 16px",
                    background: lastResult.priority === "high" ? "#fef2f2" : lastResult.priority === "medium" ? "#fffbeb" : "#f0fdf4",
                    borderRadius: 8,
                    fontSize: 14,
                    color: lastResult.priority === "high" ? "#dc2626" : lastResult.priority === "medium" ? "#d97706" : "#16a34a",
                    fontWeight: 500
                  }}>
                    {lastResult.priority}
                  </div>
                </div>
              </div>
            )}

            <div style={{ marginTop: 48 }}>
              <TicketList tickets={tickets} onDelete={handleDelete} />
            </div>
          </main>
        </div>
      )}
    </>
  );
}
