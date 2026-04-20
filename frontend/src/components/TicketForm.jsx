import { useState } from "react";

function TicketForm({ onSubmit }) {
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [priority, setPriority] = useState("medium");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e) {
    e.preventDefault();
    if (!title.trim() || !description.trim()) return;
    setLoading(true);
    try {
      await onSubmit({ title, description, priority });
      setTitle("");
      setDescription("");
      setPriority("medium");
    } finally {
      setLoading(false);
    }
  }

  return (
    <form className="ticket-form" onSubmit={handleSubmit}>
      <h2>Create Ticket</h2>
      <input
        type="text"
        placeholder="Ticket title"
        value={title}
        onChange={(e) => setTitle(e.target.value)}
        required
      />
      <textarea
        placeholder="Describe the issue..."
        value={description}
        onChange={(e) => setDescription(e.target.value)}
        rows={3}
        required
      />
      <select value={priority} onChange={(e) => setPriority(e.target.value)}>
        <option value="low">Low</option>
        <option value="medium">Medium</option>
        <option value="high">High</option>
      </select>
      <button type="submit" disabled={loading}>
        {loading ? "Routing..." : "Submit & Route"}
      </button>
    </form>
  );
}

export default TicketForm;
