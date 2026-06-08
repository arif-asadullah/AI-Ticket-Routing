import { useState, useEffect } from "react";
import { fetchTicketTimeline } from "../services/api";
import DeskMindSpinner from "./DeskMindSpinner";
import { useTheme } from "../theme/ThemeContext";

function getActionConfig(T) {
  return {
    classified: { color: T.accent, label: "AI Classified", icon: "brain" },
    routed: { color: T.blue, label: "Routed to Team", icon: "arrow" },
    escalated: { color: T.danger, label: "Escalated", icon: "up" },
    in_progress: { color: T.blue, label: "Picked Up", icon: "play" },
    resolved: { color: T.success, label: "Resolved", icon: "check" },
    feedback: { color: T.purple, label: "Feedback", icon: "star" },
    override: { color: T.purple, label: "Overridden", icon: "arrow" },
    closed: { color: T.success, label: "Closed", icon: "check" },
  };
}

function ActionIcon({ type, color }) {
  const icons = {
    brain: (
      <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
        <circle cx="6" cy="6" r="4.5" stroke={color} strokeWidth="1.2" />
        <circle cx="6" cy="4.5" r="1" fill={color} opacity="0.7" />
        <circle cx="4.5" cy="7" r="1" fill={color} opacity="0.7" />
        <circle cx="7.5" cy="7" r="1" fill={color} opacity="0.7" />
      </svg>
    ),
    arrow: (
      <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
        <path d="M2 6h8M7 3l3 3-3 3" stroke={color} strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    ),
    up: (
      <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
        <path d="M6 10V2M3 5l3-3 3 3" stroke={color} strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    ),
    play: (
      <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
        <path d="M4 2.5v7l6-3.5-6-3.5z" stroke={color} strokeWidth="1.2" strokeLinejoin="round" />
      </svg>
    ),
    check: (
      <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
        <path d="M2.5 6.5l2.5 2.5 5-5.5" stroke={color} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    ),
    star: (
      <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
        <path d="M6 1l1.4 2.8 3.1.5-2.2 2.2.5 3.1L6 8.3 3.2 9.6l.5-3.1L1.5 4.3l3.1-.5L6 1z" stroke={color} strokeWidth="1" strokeLinejoin="round" fill="none" />
      </svg>
    ),
  };
  return icons[type] || icons.arrow;
}

function timeAgo(dateStr) {
  if (!dateStr) return "";
  const now = new Date();
  const then = new Date(dateStr);
  const diff = Math.floor((now - then) / 1000);
  if (diff < 60) return "just now";
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  if (diff < 604800) return `${Math.floor(diff / 86400)}d ago`;
  return then.toLocaleDateString();
}

function formatTime(dateStr) {
  if (!dateStr) return "";
  const d = new Date(dateStr);
  return d.toLocaleString("en-US", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function ConfidenceBars({ signals }) {
  const { T } = useTheme();
  if (!signals) return null;
  const classifiers = [
    { key: "llm", label: "LLM", color: T.accent },
    { key: "knn", label: "KNN", color: T.blue },
    { key: "centroid", label: "CEN", color: T.success },
    { key: "keyword", label: "KEY", color: T.purple },
  ];
  return (
    <div style={{ display: "flex", gap: 8, marginTop: 8, flexWrap: "wrap" }}>
      {classifiers.map(({ key, label, color }) => {
        const val = signals[key];
        if (val == null) return null;
        const pct = Math.round(val * 100);
        return (
          <div key={key} style={{ flex: 1, minWidth: 60 }}>
            <div style={{
              display: "flex",
              justifyContent: "space-between",
              fontSize: 9,
              fontFamily: "'JetBrains Mono', monospace",
              color: T.textMuted,
              marginBottom: 3,
            }}>
              <span>{label}</span>
              <span style={{ color }}>{pct}%</span>
            </div>
            <div style={{
              height: 4,
              borderRadius: 2,
              background: "rgba(255,255,255,0.06)",
              overflow: "hidden",
            }}>
              <div style={{
                height: "100%",
                width: `${pct}%`,
                background: color,
                borderRadius: 2,
                transition: "width 0.5s ease",
              }} />
            </div>
          </div>
        );
      })}
    </div>
  );
}

function TimelineEntry({ event, isLast }) {
  const { T } = useTheme();
  const actionConfig = getActionConfig(T);
  const config = actionConfig[event.action] || { color: T.textMuted, label: event.action, icon: "arrow" };

  const isAI = event.actor?.startsWith("ai-");
  const actorDisplay = isAI ? "AI Classifier" : event.actor?.split("@")[0] || "System";

  return (
    <div style={{ display: "flex", gap: 16, minHeight: 60 }}>
      {/* Timeline line + dot */}
      <div style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        width: 28,
        flexShrink: 0,
      }}>
        <div style={{
          width: 28,
          height: 28,
          borderRadius: "50%",
          background: `${config.color}15`,
          border: `2px solid ${config.color}40`,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          flexShrink: 0,
        }}>
          <ActionIcon type={config.icon} color={config.color} />
        </div>
        {!isLast && (
          <div style={{
            flex: 1,
            width: 2,
            background: T.border,
            minHeight: 20,
          }} />
        )}
      </div>

      {/* Event content */}
      <div style={{
        flex: 1,
        paddingBottom: isLast ? 0 : 16,
      }}>
        <div style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "flex-start",
          gap: 12,
        }}>
          <div>
            <span style={{
              fontSize: 13,
              fontWeight: 600,
              color: config.color,
            }}>
              {config.label}
            </span>
            <span style={{
              fontSize: 12,
              color: T.textMuted,
              marginLeft: 8,
            }}>
              by {actorDisplay}
            </span>
          </div>
          <div style={{
            fontSize: 10,
            color: T.textDim,
            fontFamily: "'JetBrains Mono', monospace",
            whiteSpace: "nowrap",
          }}>
            {formatTime(event.created_at)}
            <span style={{ marginLeft: 6, color: T.textMuted }}>
              {timeAgo(event.created_at)}
            </span>
          </div>
        </div>

        {/* Details based on action type */}
        {event.action === "classified" && event.new_value && (
          <div style={{
            marginTop: 6,
            padding: "8px 12px",
            background: "rgba(249,115,22,0.05)",
            border: "1px solid rgba(249,115,22,0.1)",
            borderRadius: 8,
            fontSize: 12,
            color: T.text,
          }}>
            <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
              <span>Category: <strong style={{ color: T.accent }}>{event.new_value.category}</strong></span>
              <span>Priority: <strong>{event.new_value.priority}</strong></span>
              {event.new_value.team && (
                <span>Team: <strong>{event.new_value.team}</strong></span>
              )}
            </div>
            {event.confidence_score != null && (
              <div style={{ marginTop: 4, color: T.textMuted }}>
                Confidence: <strong style={{ color: event.confidence_score >= 0.7 ? T.success : T.warning }}>
                  {Math.round(event.confidence_score * 100)}%
                </strong>
              </div>
            )}
            <ConfidenceBars signals={event.confidence_signals} />
          </div>
        )}

        {event.action === "resolved" && event.new_value && (
          <div style={{
            marginTop: 6,
            padding: "8px 12px",
            background: "rgba(34,197,94,0.05)",
            border: "1px solid rgba(34,197,94,0.1)",
            borderRadius: 8,
            fontSize: 12,
          }}>
            {event.new_value.resolution_steps && (
              <div style={{ color: T.text }}>
                {event.new_value.resolution_steps.slice(0, 3).map((step, i) => (
                  <div key={i} style={{ marginBottom: 2 }}>
                    <span style={{ color: T.success, fontWeight: 600, marginRight: 6 }}>{i + 1}.</span>
                    {step}
                  </div>
                ))}
              </div>
            )}
            {event.new_value.used_ai_suggestion && (
              <div style={{ marginTop: 4, color: T.textMuted }}>
                AI suggestion: <strong style={{ color: event.new_value.used_ai_suggestion === "yes" ? T.success : T.warning }}>
                  {event.new_value.used_ai_suggestion}
                </strong>
              </div>
            )}
          </div>
        )}

        {event.action === "feedback" && event.new_value && (
          <div style={{
            marginTop: 6,
            padding: "8px 12px",
            background: "rgba(139,92,246,0.05)",
            border: "1px solid rgba(139,92,246,0.1)",
            borderRadius: 8,
            fontSize: 12,
          }}>
            <span style={{ color: event.new_value.rating === "helpful" ? T.success : T.danger }}>
              {event.new_value.rating === "helpful" ? "👍 Helpful" : "👎 Not Helpful"}
            </span>
            {event.new_value.comment && (
              <div style={{ marginTop: 4, color: T.textMuted, fontStyle: "italic" }}>
                "{event.new_value.comment}"
              </div>
            )}
          </div>
        )}

        {(event.action === "in_progress" || event.action === "escalated") && event.new_value && (
          <div style={{ marginTop: 4, fontSize: 12, color: T.textMuted }}>
            Status: {event.old_value?.status} → <strong style={{ color: config.color }}>{event.new_value.status}</strong>
            {event.new_value.team && event.new_value.team !== event.old_value?.team && (
              <span> • Team: <strong>{event.new_value.team}</strong></span>
            )}
          </div>
        )}

        {event.action === "override" && event.new_value && (
          <div style={{ marginTop: 4, fontSize: 12, color: T.textMuted }}>
            {event.old_value?.category && event.new_value.category && event.old_value.category !== event.new_value.category && (
              <span>
                Category: <strong style={{ color: T.textDim }}>{event.old_value.category}</strong> → <strong style={{ color: config.color }}>{event.new_value.category}</strong>
              </span>
            )}
            {event.old_value?.priority && event.new_value.priority && event.old_value.priority !== event.new_value.priority && (
              <span> • Priority: {event.old_value.priority} → <strong>{event.new_value.priority}</strong></span>
            )}
            {event.new_value.team && event.new_value.team !== event.old_value?.team && (
              <span> • Team: <strong>{event.new_value.team}</strong></span>
            )}
          </div>
        )}

        {event.reasoning && event.action !== "classified" && (
          <div style={{ marginTop: 4, fontSize: 11, color: T.textDim, fontStyle: "italic" }}>
            {event.reasoning}
          </div>
        )}
      </div>
    </div>
  );
}

export default function AuditTimeline({ ticketId, refreshKey }) {
  const { T } = useTheme();
  const [events, setEvents] = useState([]);
  const [loading, setLoading] = useState(false);

  // Re-fetch on ticketId change AND whenever refreshKey changes (e.g. after an
  // override / enrich / status change) so new audit entries appear without
  // needing to close and reopen the detail view.
  useEffect(() => {
    if (!ticketId) return;
    setLoading(true);
    fetchTicketTimeline(ticketId)
      .then(setEvents)
      .catch(() => setEvents([]))
      .finally(() => setLoading(false));
  }, [ticketId, refreshKey]);

  if (loading) {
    return (
      <div style={{ textAlign: "center", padding: 20 }}>
        <DeskMindSpinner size="sm" />
      </div>
    );
  }

  if (events.length === 0) {
    return (
      <div style={{ color: T.textDim, fontSize: 13, padding: "16px 0", textAlign: "center" }}>
        No audit trail available
      </div>
    );
  }

  return (
    <div style={{
      marginTop: 24,
      padding: "20px 24px",
      background: T.card,
      border: `1px solid ${T.border}`,
      borderRadius: 14,
    }}>
      <div style={{
        fontSize: 11,
        fontWeight: 600,
        color: T.textMuted,
        textTransform: "uppercase",
        letterSpacing: 1,
        fontFamily: "'JetBrains Mono', monospace",
        marginBottom: 16,
      }}>
        Audit Timeline
      </div>
      {events.map((event, i) => (
        <TimelineEntry
          key={i}
          event={event}
          isLast={i === events.length - 1}
        />
      ))}
    </div>
  );
}
