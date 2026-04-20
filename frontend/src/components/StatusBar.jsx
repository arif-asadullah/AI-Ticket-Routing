function StatusBar({ health }) {
  if (!health) return null;

  return (
    <div className="status-bar">
      <span className={`dot ${health.arango === "connected" ? "green" : "red"}`} />
      ArangoDB: {health.arango}
      <span className={`dot ${health.redis === "connected" ? "green" : "red"}`} />
      Redis: {health.redis}
    </div>
  );
}

export default StatusBar;
