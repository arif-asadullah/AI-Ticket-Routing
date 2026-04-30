const priorityStyles = {
  high: { bg: "rgba(239,68,68,0.12)", color: "#ef4444", dot: "#ef4444" },
  medium: { bg: "rgba(245,158,11,0.12)", color: "#f59e0b", dot: "#f59e0b" },
  low: { bg: "rgba(34,197,94,0.12)", color: "#22c55e", dot: "#22c55e" },
};

function TicketList({ tickets, onDelete, user }) {
  if (tickets.length === 0) {
    return (
      <div style={{
        textAlign: "center",
        padding: "48px 24px",
      }}>
        <svg width="48" height="48" viewBox="0 0 48 48" fill="none" style={{ marginBottom: 12, opacity: 0.3 }}>
          <rect x="4" y="8" width="40" height="32" rx="4" stroke="#78716C" strokeWidth="1.5" fill="none"/>
          <line x1="12" y1="18" x2="36" y2="18" stroke="#78716C" strokeWidth="1.5" strokeLinecap="round"/>
          <line x1="12" y1="24" x2="28" y2="24" stroke="#78716C" strokeWidth="1.5" strokeLinecap="round"/>
          <line x1="12" y1="30" x2="32" y2="30" stroke="#78716C" strokeWidth="1.5" strokeLinecap="round"/>
        </svg>
        <p style={{ color: "#44403C", fontSize: 13, margin: 0 }}>
          No tickets yet. Submit one above to get started.
        </p>
      </div>
    );
  }

  return (
    <div>
      <div style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        padding: "16px 20px",
        borderBottom: "1px solid rgba(255,255,255,0.06)",
      }}>
        <h2 style={{
          fontFamily: "'Inter', system-ui",
          fontSize: 15,
          fontWeight: 600,
          color: "#F5F5F4",
          margin: 0,
        }}>
          Recent tickets
        </h2>
        <span style={{
          fontFamily: "'JetBrains Mono', monospace",
          fontSize: 11,
          color: "#78716C",
          background: "rgba(255,255,255,0.05)",
          padding: "3px 10px",
          borderRadius: 10,
        }}>
          {tickets.length}
        </span>
      </div>

      {/* Table header */}
      <div style={{
        display: "grid",
        gridTemplateColumns: "60px 1fr 120px 100px 90px 44px",
        padding: "8px 20px",
        fontSize: 10,
        fontWeight: 600,
        fontFamily: "'JetBrains Mono', monospace",
        color: "#44403C",
        textTransform: "uppercase",
        letterSpacing: 1,
        borderBottom: "1px solid rgba(255,255,255,0.04)",
      }}>
        <span>ID</span>
        <span>Title</span>
        <span>Routed to</span>
        <span>Priority</span>
        <span>Status</span>
        <span></span>
      </div>

      {/* Rows */}
      {tickets.map((t, i) => {
        const p = priorityStyles[t.priority] || priorityStyles.medium;
        return (
          <div
            key={t.id}
            style={{
              display: "grid",
              gridTemplateColumns: "60px 1fr 120px 100px 90px 44px",
              alignItems: "center",
              padding: "12px 20px",
              fontSize: 13,
              color: "#A8A29E",
              borderBottom: "1px solid rgba(255,255,255,0.03)",
              transition: "background 0.15s",
              cursor: "default",
            }}
            onMouseEnter={(e) => e.currentTarget.style.background = "rgba(249,115,22,0.04)"}
            onMouseLeave={(e) => e.currentTarget.style.background = "transparent"}
          >
            <span style={{
              fontFamily: "'JetBrains Mono', monospace",
              fontSize: 11,
              color: "#44403C",
            }}>
              #{t.id}
            </span>

            <div style={{ minWidth: 0 }}>
              <div style={{
                fontWeight: 500,
                color: "#F5F5F4",
                fontSize: 13,
                whiteSpace: "nowrap",
                overflow: "hidden",
                textOverflow: "ellipsis",
              }}>
                {t.title}
              </div>
              <div style={{
                fontSize: 11,
                color: "#44403C",
                marginTop: 2,
                whiteSpace: "nowrap",
                overflow: "hidden",
                textOverflow: "ellipsis",
              }}>
                {t.description}
              </div>
            </div>

            <span style={{
              fontSize: 11,
              fontWeight: 600,
              color: "#F97316",
            }}>
              {t.routed_to}
            </span>

            <div>
              <span style={{
                display: "inline-flex",
                alignItems: "center",
                gap: 4,
                fontSize: 10,
                fontWeight: 600,
                padding: "2px 8px",
                borderRadius: 10,
                background: p.bg,
                color: p.color,
                textTransform: "capitalize",
              }}>
                <span style={{
                  width: 5, height: 5, borderRadius: "50%",
                  background: p.dot,
                  boxShadow: `0 0 6px ${p.dot}40`,
                }} />
                {t.priority}
              </span>
            </div>

            <span style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 4,
              fontSize: 10,
              fontWeight: 500,
              color: "#22c55e",
            }}>
              <span style={{
                width: 5, height: 5, borderRadius: "50%",
                background: "#22c55e",
                boxShadow: "0 0 6px rgba(34,197,94,0.5)",
              }} />
              {t.status}
            </span>

            {user?.role === "admin" && (
            <button
              onClick={() => onDelete(t.id)}
              style={{
                background: "none",
                border: "none",
                cursor: "pointer",
                padding: 6,
                borderRadius: 6,
                color: "#44403C",
                transition: "color 0.15s",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
              }}
              onMouseEnter={(e) => e.currentTarget.style.color = "#ef4444"}
              onMouseLeave={(e) => e.currentTarget.style.color = "#44403C"}
              title="Delete ticket"
            >
              <svg width="14" height="14" viewBox="0 0 16 16" fill="none">
                <path d="M2 4h12M5.33 4V2.67a1.33 1.33 0 011.34-1.34h2.66a1.33 1.33 0 011.34 1.34V4m2 0v9.33a1.33 1.33 0 01-1.34 1.34H4.67a1.33 1.33 0 01-1.34-1.34V4h9.34z"
                  stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
            </button>
            )}
          </div>
        );
      })}

      <div style={{
        padding: "10px 20px",
        fontSize: 10,
        fontFamily: "'JetBrains Mono', monospace",
        color: "#44403C",
        borderTop: "1px solid rgba(255,255,255,0.04)",
      }}>
        {tickets.length} ticket{tickets.length !== 1 ? "s" : ""} · ArangoDB
      </div>
    </div>
  );
}

export default TicketList;
