import { useState, useEffect, useRef } from "react";
import DeskMindSpinner from "./DeskMindSpinner";

const T = {
  card: "rgba(255,255,255,0.04)",
  border: "rgba(255,255,255,0.08)",
  text: "#F5F5F4",
  textMuted: "#78716C",
  textDim: "#44403C",
  accent: "#F97316",
  success: "#22c55e",
  warning: "#f59e0b",
  danger: "#ef4444",
  purple: "#8b5cf6",
  blue: "#3b82f6",
};

// ── Animated counter hook ──
function useAnimatedValue(target, duration = 800) {
  const [value, setValue] = useState(0);
  const rafRef = useRef(null);

  useEffect(() => {
    if (target == null || isNaN(target)) return;
    const start = performance.now();
    const from = 0;

    function animate(now) {
      const elapsed = now - start;
      const progress = Math.min(elapsed / duration, 1);
      // Ease out cubic
      const eased = 1 - Math.pow(1 - progress, 3);
      setValue(from + (target - from) * eased);
      if (progress < 1) {
        rafRef.current = requestAnimationFrame(animate);
      }
    }

    rafRef.current = requestAnimationFrame(animate);
    return () => cancelAnimationFrame(rafRef.current);
  }, [target, duration]);

  return value;
}

function MetricCard({ label, value, suffix = "", color, format = "number", icon }) {
  const numericValue = typeof value === "number" ? value : 0;
  const animated = useAnimatedValue(numericValue);

  let displayValue;
  if (format === "percent") {
    displayValue = `${Math.round(animated * 100)}%`;
  } else if (format === "time") {
    const mins = Math.round(animated);
    if (mins >= 60) {
      displayValue = `${Math.floor(mins / 60)}h ${mins % 60}m`;
    } else {
      displayValue = `${mins}m`;
    }
  } else {
    displayValue = Math.round(animated).toLocaleString();
  }

  return (
    <div style={{
      flex: 1,
      minWidth: 140,
      background: T.card,
      border: `1px solid ${T.border}`,
      borderRadius: 14,
      padding: "16px 18px",
      backdropFilter: "blur(8px)",
      transition: "border-color 0.3s",
    }}
      onMouseEnter={(e) => e.currentTarget.style.borderColor = `${color}40`}
      onMouseLeave={(e) => e.currentTarget.style.borderColor = T.border}
    >
      <div style={{
        display: "flex",
        alignItems: "center",
        gap: 8,
        marginBottom: 8,
      }}>
        {icon && (
          <div style={{
            width: 28,
            height: 28,
            borderRadius: 8,
            background: `${color}15`,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
          }}>
            {icon}
          </div>
        )}
        <span style={{
          fontSize: 10,
          fontWeight: 600,
          color: T.textMuted,
          textTransform: "uppercase",
          letterSpacing: 1,
          fontFamily: "'JetBrains Mono', monospace",
        }}>
          {label}
        </span>
      </div>
      <div style={{
        fontSize: 26,
        fontWeight: 700,
        color: color,
        fontFamily: "'JetBrains Mono', monospace",
        lineHeight: 1,
      }}>
        {displayValue}{suffix}
      </div>
    </div>
  );
}

export default function StatsSummaryBar({ stats, loading }) {
  if (loading) {
    return (
      <div style={{
        display: "flex",
        justifyContent: "center",
        padding: 20,
      }}>
        <DeskMindSpinner size="sm" />
      </div>
    );
  }

  if (!stats) return null;

  const confidenceColor = stats.avg_confidence >= 0.8 ? T.success
    : stats.avg_confidence >= 0.6 ? T.warning : T.danger;

  const escalationColor = stats.escalation_rate <= 0.15 ? T.success
    : stats.escalation_rate <= 0.30 ? T.warning : T.danger;

  const agreementColor = stats.classifier_agreement >= 0.7 ? T.success
    : stats.classifier_agreement >= 0.5 ? T.warning : T.danger;

  const totalFeedback = (stats.feedback?.helpful || 0) + (stats.feedback?.not_helpful || 0);
  const helpfulness = totalFeedback > 0
    ? (stats.feedback.helpful / totalFeedback)
    : 0;
  const helpfulnessColor = helpfulness >= 0.7 ? T.success
    : helpfulness >= 0.4 ? T.warning : T.danger;

  return (
    <div style={{
      display: "flex",
      gap: 12,
      flexWrap: "wrap",
      marginBottom: 24,
    }}>
      <MetricCard
        label="Total Tickets"
        value={stats.total}
        color={T.accent}
        icon={
          <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
            <rect x="1" y="2" width="12" height="10" rx="2" stroke={T.accent} strokeWidth="1.2" />
            <line x1="4" y1="5" x2="10" y2="5" stroke={T.accent} strokeWidth="1" strokeLinecap="round" opacity="0.5" />
            <line x1="4" y1="7.5" x2="8" y2="7.5" stroke={T.accent} strokeWidth="1" strokeLinecap="round" opacity="0.5" />
          </svg>
        }
      />
      <MetricCard
        label="Avg Confidence"
        value={stats.avg_confidence}
        format="percent"
        color={confidenceColor}
        icon={
          <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
            <circle cx="7" cy="7" r="5.5" stroke={confidenceColor} strokeWidth="1.2" />
            <path d="M7 4v3.5l2.5 1.5" stroke={confidenceColor} strokeWidth="1.2" strokeLinecap="round" />
          </svg>
        }
      />
      <MetricCard
        label="Escalation Rate"
        value={stats.escalation_rate}
        format="percent"
        color={escalationColor}
        icon={
          <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
            <path d="M7 11V3M4 6l3-3 3 3" stroke={escalationColor} strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        }
      />
      <MetricCard
        label="Avg Resolution"
        value={stats.avg_resolution_minutes}
        format="time"
        color={T.blue}
        icon={
          <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
            <circle cx="7" cy="7" r="5.5" stroke={T.blue} strokeWidth="1.2" />
            <path d="M4 7.5l2 2 4-4" stroke={T.blue} strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        }
      />
      <MetricCard
        label="AI Agreement"
        value={stats.classifier_agreement}
        format="percent"
        color={agreementColor}
        icon={
          <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
            <circle cx="4.5" cy="5" r="2" stroke={agreementColor} strokeWidth="1" />
            <circle cx="9.5" cy="5" r="2" stroke={agreementColor} strokeWidth="1" />
            <circle cx="7" cy="9" r="2" stroke={agreementColor} strokeWidth="1" />
          </svg>
        }
      />
      <MetricCard
        label="AI Helpfulness"
        value={helpfulness}
        format="percent"
        color={helpfulnessColor}
        icon={
          <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
            <path d="M7 1l1.8 3.6L13 5.2l-3 2.9.7 4.1L7 10.1 3.3 12.2l.7-4.1-3-2.9 4.2-.6L7 1z" stroke={helpfulnessColor} strokeWidth="1" strokeLinejoin="round" fill="none" />
          </svg>
        }
      />
    </div>
  );
}
