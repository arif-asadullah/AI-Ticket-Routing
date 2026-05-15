import { useEffect, useRef } from "react";

const T = {
  bg: "#1a1a1f",
  card: "rgba(255,255,255,0.04)",
  border: "rgba(255,255,255,0.12)",
  text: "#F5F5F4",
  textMuted: "#78716C",
  textDim: "#44403C",
  accent: "#F97316",
  success: "#22c55e",
  danger: "#ef4444",
  blue: "#3b82f6",
  purple: "#8b5cf6",
};

const labelStyle = {
  fontSize: 9,
  fontWeight: 600,
  color: T.textDim,
  textTransform: "uppercase",
  letterSpacing: 1,
  fontFamily: "'JetBrains Mono', monospace",
  marginBottom: 2,
};

export default function ChipTooltip({ entity, anchorRect, onClose }) {
  const ref = useRef(null);

  useEffect(() => {
    function handleClick(e) {
      if (ref.current && !ref.current.contains(e.target)) onClose();
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, [onClose]);

  if (!entity) return null;

  // Position: below and aligned to anchor
  const style = {
    position: "fixed",
    top: (anchorRect?.bottom || 0) + 6,
    left: Math.min(anchorRect?.left || 0, window.innerWidth - 280),
    zIndex: 500,
    width: 260,
    background: T.bg,
    border: `1px solid ${T.border}`,
    borderRadius: 12,
    padding: 14,
    boxShadow: "0 12px 40px rgba(0,0,0,0.5)",
    backdropFilter: "blur(12px)",
    animation: "chipFadeIn 0.15s ease-out",
  };

  const { type, data } = entity;

  return (
    <>
      <style>{`@keyframes chipFadeIn { from { opacity:0; transform:translateY(-4px) } to { opacity:1; transform:translateY(0) } }`}</style>
      <div ref={ref} style={style}>
        {type === "ticket" && <TicketTooltip data={data} />}
        {type === "engineer" && <EngineerTooltip data={data} />}
        {type === "team" && <TeamTooltip data={data} />}
      </div>
    </>
  );
}

function TicketTooltip({ data }) {
  const statusColor = { routed: T.accent, escalated: T.danger, in_progress: T.blue, resolved: T.success, closed: T.textDim };
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <span style={{ fontSize: 13, fontWeight: 600, color: T.accent, fontFamily: "'JetBrains Mono', monospace" }}>#{data.id}</span>
        {data.status && (
          <span style={{
            fontSize: 10, fontWeight: 600, padding: "2px 8px", borderRadius: 8,
            background: `${statusColor[data.status] || T.textDim}20`,
            color: statusColor[data.status] || T.textDim,
            textTransform: "capitalize",
          }}>
            {(data.status || "").replace(/_/g, " ")}
          </span>
        )}
      </div>
      {data.title && <div style={{ fontSize: 12, fontWeight: 500, color: T.text, lineHeight: 1.4 }}>{data.title}</div>}
      <div style={{ display: "flex", gap: 16, flexWrap: "wrap" }}>
        {data.category && <Field label="Category" value={data.category} />}
        {data.priority && <Field label="Priority" value={data.priority} />}
      </div>
      {data.routed_to && <Field label="Team" value={data.routed_to} />}
      {data.created_at && <Field label="Created" value={new Date(data.created_at).toLocaleDateString()} />}
      {data.confidence != null && <Field label="Confidence" value={`${Math.round(data.confidence * 100)}%`} />}
    </div>
  );
}

function EngineerTooltip({ data }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <div style={{
          width: 28, height: 28, borderRadius: "50%",
          background: "rgba(34,197,94,0.15)", color: T.success,
          display: "flex", alignItems: "center", justifyContent: "center",
          fontSize: 12, fontWeight: 700,
        }}>
          {(data.name || "?")[0].toUpperCase()}
        </div>
        <span style={{ fontSize: 13, fontWeight: 600, color: T.text }}>{data.name}</span>
      </div>
      {data.email && <Field label="Email" value={data.email} />}
      {data.expertise && data.expertise.length > 0 && (
        <div>
          <div style={labelStyle}>Expertise</div>
          <div style={{ display: "flex", gap: 4, flexWrap: "wrap" }}>
            {data.expertise.map((s, i) => (
              <span key={i} style={{
                fontSize: 10, padding: "2px 8px", borderRadius: 6,
                background: "rgba(34,197,94,0.1)", color: T.success,
              }}>{s}</span>
            ))}
          </div>
        </div>
      )}
      {data.note && <div style={{ fontSize: 11, color: T.textMuted, fontStyle: "italic" }}>{data.note}</div>}
    </div>
  );
}

function TeamTooltip({ data }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
      <div style={{ fontSize: 13, fontWeight: 600, color: T.blue }}>{data.name}</div>
      {data.domain && <Field label="Domain" value={data.domain} />}
      {data.members && data.members.length > 0 && (
        <div>
          <div style={labelStyle}>Members</div>
          {data.members.map((m, i) => (
            <div key={i} style={{ fontSize: 11, color: T.text, marginBottom: 2 }}>
              {m.name}{m.expertise?.length ? ` — ${m.expertise.slice(0, 3).join(", ")}` : ""}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function Field({ label, value }) {
  return (
    <div>
      <div style={labelStyle}>{label}</div>
      <div style={{ fontSize: 12, color: T.text, fontWeight: 500, textTransform: "capitalize" }}>{value}</div>
    </div>
  );
}
