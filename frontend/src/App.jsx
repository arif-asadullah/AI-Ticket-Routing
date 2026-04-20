import { useState, useEffect } from "react";
import TicketForm from "./components/TicketForm";
import TicketList from "./components/TicketList";
import StatusBar from "./components/StatusBar";
import { fetchTickets, createTicket, deleteTicket, fetchHealth } from "./services/api";
import "./App.css";

function App() {
  const [tickets, setTickets] = useState([]);
  const [health, setHealth] = useState(null);
  const [error, setError] = useState(null);

  async function loadTickets() {
    try {
      const data = await fetchTickets();
      setTickets(data);
      setError(null);
    } catch (err) {
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

  useEffect(() => {
    loadTickets();
    loadHealth();
  }, []);

  async function handleCreate(ticket) {
    const created = await createTicket(ticket);
    setTickets((prev) => [created, ...prev]);
  }

  async function handleDelete(id) {
    await deleteTicket(id);
    setTickets((prev) => prev.filter((t) => t.id !== id));
  }

  return (
    <div className="app">
      <header className="app-header">
        <h1>AI Ticket Routing</h1>
        <p>Intelligent support ticket classification and routing</p>
        <StatusBar health={health} />
      </header>
      <main className="app-main">
        {error && <p className="error">{error}</p>}
        <TicketForm onSubmit={handleCreate} />
        <TicketList tickets={tickets} onDelete={handleDelete} />
      </main>
    </div>
  );
}

export default App;
