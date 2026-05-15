import { useState } from "react";
import ChipTooltip from "./ChipTooltip";

const CHIP_COLORS = {
  ticket: { bg: "rgba(249,115,22,0.15)", color: "#F97316", border: "rgba(249,115,22,0.3)" },
  engineer: { bg: "rgba(34,197,94,0.15)", color: "#22c55e", border: "rgba(34,197,94,0.3)" },
  team: { bg: "rgba(59,130,246,0.15)", color: "#3b82f6", border: "rgba(59,130,246,0.3)" },
  status: {
    routed: { bg: "rgba(249,115,22,0.12)", color: "#F97316" },
    escalated: { bg: "rgba(239,68,68,0.12)", color: "#ef4444" },
    in_progress: { bg: "rgba(59,130,246,0.12)", color: "#3b82f6" },
    resolved: { bg: "rgba(34,197,94,0.12)", color: "#22c55e" },
    closed: { bg: "rgba(120,113,108,0.12)", color: "#78716C" },
  },
  category: { bg: "rgba(139,92,246,0.12)", color: "#8b5cf6", border: "rgba(139,92,246,0.3)" },
};

// Entity types that show tooltip on click
const CLICKABLE = new Set(["ticket", "engineer", "team"]);

export default function RichMessage({ content, entities }) {
  const [tooltip, setTooltip] = useState(null); // { entity, rect }

  if (!entities || entities.length === 0) {
    return <span style={{ whiteSpace: "pre-wrap", wordBreak: "break-word" }}>{content}</span>;
  }

  // Build a list of replacements sorted by position in text
  const parts = buildParts(content, entities);

  function handleChipClick(entity, e) {
    if (!CLICKABLE.has(entity.type)) return;
    const rect = e.currentTarget.getBoundingClientRect();
    setTooltip((prev) =>
      prev && prev.entity.type === entity.type && prev.entity.value === entity.value
        ? null
        : { entity, rect }
    );
  }

  return (
    <span style={{ whiteSpace: "pre-wrap", wordBreak: "break-word" }}>
      {parts.map((part, i) => {
        if (part.type === "text") {
          return <span key={i}>{part.value}</span>;
        }
        const entity = part.entity;
        const chipStyle = getChipStyle(entity);
        const clickable = CLICKABLE.has(entity.type);
        return (
          <span
            key={i}
            onClick={(e) => handleChipClick(entity, e)}
            style={{
              ...chipStyle,
              display: "inline-flex",
              alignItems: "center",
              gap: 3,
              padding: "1px 8px",
              borderRadius: 6,
              fontSize: 12,
              fontWeight: 600,
              cursor: clickable ? "pointer" : "default",
              transition: "all 0.15s",
              verticalAlign: "baseline",
            }}
            onMouseEnter={(e) => {
              if (clickable) e.currentTarget.style.filter = "brightness(1.3)";
            }}
            onMouseLeave={(e) => {
              if (clickable) e.currentTarget.style.filter = "none";
            }}
          >
            {entity.type === "ticket" && "🎫 "}
            {entity.type === "engineer" && "👤 "}
            {entity.type === "team" && "👥 "}
            {part.display}
          </span>
        );
      })}

      {tooltip && (
        <ChipTooltip
          entity={tooltip.entity}
          anchorRect={tooltip.rect}
          onClose={() => setTooltip(null)}
        />
      )}
    </span>
  );
}

function getChipStyle(entity) {
  if (entity.type === "status") {
    const s = CHIP_COLORS.status[entity.value] || CHIP_COLORS.status.routed;
    return { background: s.bg, color: s.color };
  }
  const c = CHIP_COLORS[entity.type] || CHIP_COLORS.category;
  return { background: c.bg, color: c.color };
}

/**
 * Split content into text parts and entity chip parts.
 * Finds entity values in the text and replaces them with chip markers.
 */
function buildParts(content, entities) {
  // Build replacements: find each entity value in the text
  const replacements = [];
  for (const entity of entities) {
    const value = entity.value;
    if (!value) continue;

    // Escape regex special chars
    const escaped = value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    const regex = new RegExp(escaped, "gi");
    let match;
    while ((match = regex.exec(content)) !== null) {
      replacements.push({
        start: match.index,
        end: match.index + match[0].length,
        display: match[0],
        entity,
      });
    }
  }

  // Sort by position, remove overlaps
  replacements.sort((a, b) => a.start - b.start);
  const filtered = [];
  let lastEnd = 0;
  for (const r of replacements) {
    if (r.start >= lastEnd) {
      filtered.push(r);
      lastEnd = r.end;
    }
  }

  // Build parts
  const parts = [];
  let cursor = 0;
  for (const r of filtered) {
    if (r.start > cursor) {
      parts.push({ type: "text", value: content.slice(cursor, r.start) });
    }
    parts.push({ type: "chip", display: r.display, entity: r.entity });
    cursor = r.end;
  }
  if (cursor < content.length) {
    parts.push({ type: "text", value: content.slice(cursor) });
  }

  return parts;
}
