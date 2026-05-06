import { useMemo, useState } from "react";

const T = {
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

const DEPARTMENTS = [
  { name: "Infrastructure Ops", domain: "Infrastructure", color: "#F97316", desc: "Servers, OS, datacenter, capacity" },
  { name: "Application Support", domain: "Application", color: "#3b82f6", desc: "App services, deployments, runtime errors" },
  { name: "Security Ops", domain: "Security", color: "#ef4444", desc: "Auth, intrusion, vulnerabilities, audit" },
  { name: "Database Admin", domain: "Database", color: "#22c55e", desc: "Postgres, replication, queries, backups" },
  { name: "Storage Ops", domain: "Storage", color: "#a855f7", desc: "Volumes, NFS/S3, backup jobs" },
  { name: "Network Engineering", domain: "Network", color: "#06b6d4", desc: "Switches, routers, DNS, firewalls" },
];

const PRIORITY_STYLES = {
  critical: { bg: "rgba(239,68,68,0.18)", color: T.danger },
  high: { bg: "rgba(239,68,68,0.12)", color: T.danger },
  medium: { bg: "rgba(245,158,11,0.12)", color: T.warning },
  low: { bg: "rgba(34,197,94,0.12)", color: T.success },
};

const STATUS_STYLES = {
  routed: { color: "#3b82f6" },
  in_progress: { color: T.warning },
  resolved: { color: T.success },
  escalated: { color: T.danger },
  open: { color: T.textMuted },
  closed: { color: T.textDim },
};

const PAGE_SIZE = 10;

function DepartmentsHome({ tickets, onSelect }) {
  const counts = useMemo(() => {
    const map = {};
    for (const dept of DEPARTMENTS) map[dept.name] = 0;
    for (const t of tickets) {
      if (t.routed_to && map.hasOwnProperty(t.routed_to)) {
        map[t.routed_to] += 1;
      }
    }
    return map;
  }, [tickets]);

  return (
    <div>
      <div style={{ marginBottom: 24 }}>
        <h1 style={{ fontSize: 22, fontWeight: 600, color: T.text, marginBottom: 6 }}>
          Departments
        </h1>
        <p style={{ color: T.textMuted, fontSize: 13 }}>
          Pick a team to see tickets routed to that department.
        </p>
      </div>

      <div style={{
        display: "grid",
        gridTemplateColumns: "repeat(auto-fill, minmax(260px, 1fr))",
        gap: 16,
      }}>
        {DEPARTMENTS.map((dept) => (
          <button
            key={dept.name}
            onClick={() => onSelect(dept.name)}
            style={{
              textAlign: "left",
              background: T.card,
              border: `1px solid ${T.border}`,
              borderRadius: 14,
              padding: 20,
              cursor: "pointer",
              transition: "all 0.15s",
              fontFamily: "inherit",
              color: T.text,
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.background = T.cardHover;
              e.currentTarget.style.borderColor = T.borderGlow;
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.background = T.card;
              e.currentTarget.style.borderColor = T.border;
            }}
          >
            <div style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              marginBottom: 12,
            }}>
              <div style={{
                width: 36, height: 36, borderRadius: 10,
                background: `${dept.color}1a`,
                display: "flex", alignItems: "center", justifyContent: "center",
                fontSize: 13, fontWeight: 700, color: dept.color,
                fontFamily: "'JetBrains Mono', monospace",
              }}>
                {dept.domain.slice(0, 2).toUpperCase()}
              </div>
              <span style={{
                fontFamily: "'JetBrains Mono', monospace",
                fontSize: 11, color: T.textMuted,
                background: "rgba(255,255,255,0.04)",
                padding: "3px 10px", borderRadius: 10,
              }}>
                {counts[dept.name]} tickets
              </span>
            </div>
            <div style={{ fontSize: 15, fontWeight: 600, color: T.text, marginBottom: 4 }}>
              {dept.name}
            </div>
            <div style={{ fontSize: 12, color: T.textMuted, lineHeight: 1.45 }}>
              {dept.desc}
            </div>
          </button>
        ))}
      </div>
    </div>
  );
}

function FilterControls({ status, priority, search, onChange }) {
  const selectStyle = {
    padding: "8px 12px",
    borderRadius: 8,
    border: `1px solid ${T.border}`,
    background: "rgba(255,255,255,0.03)",
    color: T.text,
    fontSize: 12,
    fontFamily: "inherit",
    outline: "none",
    cursor: "pointer",
  };
  const optionStyle = { background: "#1f1f23", color: "#A8A29E" };

  return (
    <div style={{
      display: "flex",
      flexWrap: "wrap",
      gap: 10,
      alignItems: "center",
      marginBottom: 16,
    }}>
      <input
        type="text"
        placeholder="Search by title…"
        value={search}
        onChange={(e) => onChange({ search: e.target.value })}
        style={{
          flex: "1 1 220px",
          padding: "8px 12px",
          borderRadius: 8,
          border: `1px solid ${T.border}`,
          background: "rgba(255,255,255,0.03)",
          color: T.text,
          fontSize: 12,
          outline: "none",
          fontFamily: "inherit",
        }}
      />
      <select
        value={status}
        onChange={(e) => onChange({ status: e.target.value })}
        style={selectStyle}
      >
        <option value="" style={optionStyle}>All statuses</option>
        <option value="routed" style={optionStyle}>Routed</option>
        <option value="in_progress" style={optionStyle}>In progress</option>
        <option value="resolved" style={optionStyle}>Resolved</option>
        <option value="escalated" style={optionStyle}>Escalated</option>
        <option value="open" style={optionStyle}>Open</option>
        <option value="closed" style={optionStyle}>Closed</option>
      </select>
      <select
        value={priority}
        onChange={(e) => onChange({ priority: e.target.value })}
        style={selectStyle}
      >
        <option value="" style={optionStyle}>All priorities</option>
        <option value="critical" style={optionStyle}>Critical</option>
        <option value="high" style={optionStyle}>High</option>
        <option value="medium" style={optionStyle}>Medium</option>
        <option value="low" style={optionStyle}>Low</option>
      </select>
    </div>
  );
}

function ListView({ tickets }) {
  if (tickets.length === 0) {
    return (
      <div style={{ textAlign: "center", padding: "48px 24px", color: T.textDim, fontSize: 13 }}>
        No tickets match these filters.
      </div>
    );
  }
  return (
    <div>
      <div style={{
        display: "grid",
        gridTemplateColumns: "70px 1fr 110px 90px 90px",
        padding: "8px 16px",
        fontSize: 10,
        fontWeight: 600,
        fontFamily: "'JetBrains Mono', monospace",
        color: T.textDim,
        textTransform: "uppercase",
        letterSpacing: 1,
        borderBottom: `1px solid ${T.border}`,
      }}>
        <span>ID</span>
        <span>Title</span>
        <span>Priority</span>
        <span>Status</span>
        <span>Created</span>
      </div>
      {tickets.map((t) => {
        const p = PRIORITY_STYLES[t.priority] || PRIORITY_STYLES.medium;
        const s = STATUS_STYLES[t.status] || STATUS_STYLES.open;
        const created = t.created_at ? new Date(t.created_at).toLocaleDateString() : "—";
        return (
          <div
            key={t.id}
            style={{
              display: "grid",
              gridTemplateColumns: "70px 1fr 110px 90px 90px",
              alignItems: "center",
              padding: "12px 16px",
              fontSize: 13,
              borderBottom: `1px solid rgba(255,255,255,0.03)`,
            }}
          >
            <span style={{
              fontFamily: "'JetBrains Mono', monospace",
              fontSize: 11, color: T.textDim,
            }}>
              #{t.id}
            </span>
            <div style={{ minWidth: 0 }}>
              <div style={{
                fontWeight: 500, color: T.text, fontSize: 13,
                whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis",
              }}>
                {t.title}
              </div>
              <div style={{
                fontSize: 11, color: T.textDim, marginTop: 2,
                whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis",
              }}>
                {t.description}
              </div>
            </div>
            <span style={{
              display: "inline-flex", alignItems: "center", gap: 5,
              fontSize: 10, fontWeight: 600,
              padding: "3px 9px", borderRadius: 10,
              background: p.bg, color: p.color,
              textTransform: "capitalize",
              width: "fit-content",
            }}>
              {t.priority}
            </span>
            <span style={{
              fontSize: 11, color: s.color, fontWeight: 500,
              textTransform: "capitalize",
            }}>
              {t.status?.replace("_", " ")}
            </span>
            <span style={{ fontSize: 11, color: T.textDim, fontFamily: "'JetBrains Mono', monospace" }}>
              {created}
            </span>
          </div>
        );
      })}
    </div>
  );
}

function CardView({ tickets }) {
  if (tickets.length === 0) {
    return (
      <div style={{ textAlign: "center", padding: "48px 24px", color: T.textDim, fontSize: 13 }}>
        No tickets match these filters.
      </div>
    );
  }
  return (
    <div style={{
      display: "grid",
      gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))",
      gap: 12,
      padding: 16,
    }}>
      {tickets.map((t) => {
        const p = PRIORITY_STYLES[t.priority] || PRIORITY_STYLES.medium;
        const s = STATUS_STYLES[t.status] || STATUS_STYLES.open;
        const created = t.created_at ? new Date(t.created_at).toLocaleDateString() : "—";
        return (
          <div
            key={t.id}
            style={{
              background: "rgba(255,255,255,0.02)",
              border: `1px solid ${T.border}`,
              borderRadius: 12,
              padding: 14,
              display: "flex",
              flexDirection: "column",
              gap: 10,
            }}
          >
            <div style={{
              display: "flex", justifyContent: "space-between", alignItems: "center",
            }}>
              <span style={{
                fontFamily: "'JetBrains Mono', monospace",
                fontSize: 11, color: T.textDim,
              }}>
                #{t.id}
              </span>
              <span style={{
                fontSize: 10, fontWeight: 600,
                padding: "2px 8px", borderRadius: 8,
                background: p.bg, color: p.color,
                textTransform: "capitalize",
              }}>
                {t.priority}
              </span>
            </div>
            <div style={{ fontSize: 14, fontWeight: 600, color: T.text, lineHeight: 1.35 }}>
              {t.title}
            </div>
            <div style={{
              fontSize: 12, color: T.textMuted, lineHeight: 1.45,
              display: "-webkit-box",
              WebkitLineClamp: 3,
              WebkitBoxOrient: "vertical",
              overflow: "hidden",
            }}>
              {t.description}
            </div>
            <div style={{
              display: "flex", justifyContent: "space-between", alignItems: "center",
              fontSize: 11, color: T.textDim, paddingTop: 8,
              borderTop: `1px solid ${T.border}`,
            }}>
              <span style={{
                color: s.color, fontWeight: 500,
                textTransform: "capitalize",
              }}>
                {t.status?.replace("_", " ")}
              </span>
              <span style={{ fontFamily: "'JetBrains Mono', monospace" }}>
                {created}
              </span>
            </div>
          </div>
        );
      })}
    </div>
  );
}

function Pagination({ page, totalPages, onChange }) {
  if (totalPages <= 1) return null;
  return (
    <div style={{
      display: "flex",
      alignItems: "center",
      justifyContent: "center",
      gap: 8,
      padding: "16px 0 4px",
      fontSize: 12,
    }}>
      <button
        onClick={() => onChange(page - 1)}
        disabled={page === 1}
        style={{
          padding: "6px 12px",
          borderRadius: 6,
          border: `1px solid ${T.border}`,
          background: "transparent",
          color: page === 1 ? T.textDim : T.text,
          cursor: page === 1 ? "not-allowed" : "pointer",
          fontFamily: "inherit",
        }}
      >
        ‹ Prev
      </button>
      <span style={{
        color: T.textMuted,
        fontFamily: "'JetBrains Mono', monospace",
        fontSize: 11,
      }}>
        {page} / {totalPages}
      </span>
      <button
        onClick={() => onChange(page + 1)}
        disabled={page === totalPages}
        style={{
          padding: "6px 12px",
          borderRadius: 6,
          border: `1px solid ${T.border}`,
          background: "transparent",
          color: page === totalPages ? T.textDim : T.text,
          cursor: page === totalPages ? "not-allowed" : "pointer",
          fontFamily: "inherit",
        }}
      >
        Next ›
      </button>
    </div>
  );
}

function DepartmentPage({ tickets, departmentName, onBack, onCreateTicket }) {
  const dept = DEPARTMENTS.find((d) => d.name === departmentName);
  const [view, setView] = useState("list");
  const [filters, setFilters] = useState({ status: "", priority: "", search: "" });
  const [page, setPage] = useState(1);

  const filtered = useMemo(() => {
    const q = filters.search.trim().toLowerCase();
    return tickets
      .filter((t) => t.routed_to === departmentName)
      .filter((t) => !filters.status || t.status === filters.status)
      .filter((t) => !filters.priority || t.priority === filters.priority)
      .filter((t) => !q || (t.title || "").toLowerCase().includes(q));
  }, [tickets, departmentName, filters]);

  const totalPages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const safePage = Math.min(page, totalPages);
  const pageItems = filtered.slice((safePage - 1) * PAGE_SIZE, safePage * PAGE_SIZE);

  function updateFilters(patch) {
    setFilters((f) => ({ ...f, ...patch }));
    setPage(1);
  }

  return (
    <div>
      <div style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        marginBottom: 20,
        gap: 12,
        flexWrap: "wrap",
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
          <button
            onClick={onBack}
            style={{
              background: "rgba(255,255,255,0.04)",
              border: `1px solid ${T.border}`,
              borderRadius: 8,
              padding: "6px 10px",
              color: T.textMuted,
              cursor: "pointer",
              fontSize: 12,
              fontFamily: "inherit",
            }}
          >
            ← Departments
          </button>
          <div>
            <h1 style={{ fontSize: 22, fontWeight: 600, color: T.text, margin: 0 }}>
              {departmentName}
            </h1>
            <p style={{ color: T.textMuted, fontSize: 12, margin: "4px 0 0" }}>
              {dept?.desc} · {filtered.length} match{filtered.length === 1 ? "" : "es"}
            </p>
          </div>
        </div>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <div style={{
            display: "flex",
            border: `1px solid ${T.border}`,
            borderRadius: 8,
            overflow: "hidden",
          }}>
            {["list", "card"].map((mode) => (
              <button
                key={mode}
                onClick={() => setView(mode)}
                style={{
                  padding: "7px 14px",
                  fontSize: 12,
                  fontFamily: "inherit",
                  border: "none",
                  cursor: "pointer",
                  background: view === mode ? T.accentGlow : "transparent",
                  color: view === mode ? T.accent : T.textMuted,
                  fontWeight: view === mode ? 600 : 400,
                  textTransform: "capitalize",
                }}
              >
                {mode}
              </button>
            ))}
          </div>
          <button
            onClick={onCreateTicket}
            style={{
              padding: "7px 14px",
              borderRadius: 8,
              border: "none",
              background: T.accent,
              color: "#fff",
              fontSize: 12,
              fontWeight: 600,
              cursor: "pointer",
              fontFamily: "inherit",
              boxShadow: "0 0 16px rgba(249,115,22,0.25)",
            }}
          >
            + New ticket
          </button>
        </div>
      </div>

      <FilterControls
        status={filters.status}
        priority={filters.priority}
        search={filters.search}
        onChange={updateFilters}
      />

      <div style={{
        background: T.card,
        borderRadius: 14,
        border: `1px solid ${T.border}`,
        overflow: "hidden",
        backdropFilter: "blur(8px)",
      }}>
        {view === "list" ? <ListView tickets={pageItems} /> : <CardView tickets={pageItems} />}
      </div>

      <Pagination page={safePage} totalPages={totalPages} onChange={setPage} />
    </div>
  );
}

export default function DepartmentsView({ tickets, selectedDepartment, onSelectDepartment, onCreateTicket }) {
  if (!selectedDepartment) {
    return <DepartmentsHome tickets={tickets} onSelect={onSelectDepartment} />;
  }
  return (
    <DepartmentPage
      tickets={tickets}
      departmentName={selectedDepartment}
      onBack={() => onSelectDepartment(null)}
      onCreateTicket={onCreateTicket}
    />
  );
}
