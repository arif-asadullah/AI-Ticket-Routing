function TicketList({ tickets, onDelete }) {
  if (tickets.length === 0) {
    return <p className="empty">No tickets yet. Create one above.</p>;
  }

  return (
    <div className="ticket-list">
      <h2>Tickets ({tickets.length})</h2>
      {tickets.map((t) => (
        <div key={t.id} className={`ticket-card priority-${t.priority}`}>
          <div className="ticket-header">
            <span className="ticket-id">#{t.id}</span>
            <span className={`priority-badge ${t.priority}`}>{t.priority}</span>
          </div>
          <h3>{t.title}</h3>
          <p>{t.description}</p>
          <div className="ticket-footer">
            <span className="routed-to">Routed to: <strong>{t.routed_to}</strong></span>
            <span className="status">{t.status}</span>
            <button className="delete-btn" onClick={() => onDelete(t.id)}>Delete</button>
          </div>
        </div>
      ))}
    </div>
  );
}

export default TicketList;
