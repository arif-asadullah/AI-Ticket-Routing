function StatusBar({ health }) {
  if (!health) return null;

  const dot = (connected) => ({
    width: 8,
    height: 8,
    borderRadius: "50%",
    display: "inline-block",
    background: connected ? "#22c55e" : "#ef4444",
    boxShadow: connected ? "0 0 6px rgba(34,197,94,0.5)" : "0 0 6px rgba(239,68,68,0.5)",
  });

  return (
    <div style={{
      display: "inline-flex",
      alignItems: "center",
      gap: 8,
      fontSize: 11,
      color: "#A8A29E",
      background: "rgba(255,255,255,0.08)",
      padding: "5px 14px",
      borderRadius: 20,
      border: "1px solid rgba(255,255,255,0.1)",
    }}>
      <span style={dot(health.arango === "connected")} />
      ArangoDB
      <span style={dot(health.redis === "connected")} />
      Redis
    </div>
  );
}

export default StatusBar;
