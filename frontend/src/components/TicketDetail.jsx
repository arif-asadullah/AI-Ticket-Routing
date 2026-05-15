import { useState } from "react";
import { useTheme } from "../theme/ThemeContext";
import { updateTicketStatus, resolveTicket, submitFeedback } from "../services/api";
import DeskMindSpinner from "./DeskMindSpinner";
import ResolveForm from "./ResolveForm";
import FeedbackWidget from "./FeedbackWidget";
import AuditTimeline from "./AuditTimeline";


const priorityStyles = {
  critical: { bg: "rgba(239,68,68,0.15)", color: "#ef4444" },
  high: { bg: "rgba(239,68,68,0.12)", color: "#ef4444" },
  medium: { bg: "rgba(245,158,11,0.12)", color: "#f59e0b" },
  low: { bg: "rgba(34,197,94,0.12)", color: "#22c55e" },
};

const statusStyles = {
  routed: { bg: "rgba(249,115,22,0.12)", color: "#F97316" },
  in_progress: { bg: "rgba(59,130,246,0.12)", color: "#3b82f6" },
  escalated: { bg: "rgba(239,68,68,0.12)", color: "#ef4444" },
  resolved: { bg: "rgba(34,197,94,0.12)", color: "#22c55e" },
};

function getLabelStyle(T) {
  return {
    fontSize: 10,
    fontWeight: 600,
    color: T.textDim,
    textTransform: "uppercase",
    letterSpacing: 1,
    fontFamily: "'JetBrains Mono', monospace",
    marginBottom: 4,
  };
}

function timeAgo(dateStr) {
  if (!dateStr) return "";
  const now = new Date();
  const then = new Date(dateStr);
  const diffMs = now - then;
  const diffMin = Math.floor(diffMs / 60000);
  if (diffMin < 1) return "just now";
  if (diffMin < 60) return `${diffMin}m ago`;
  const diffHr = Math.floor(diffMin / 60);
  if (diffHr < 24) return `${diffHr}h ago`;
  const diffDay = Math.floor(diffHr / 24);
  if (diffDay === 1) return "yesterday";
  if (diffDay < 7) return `${diffDay}d ago`;
  const diffWeek = Math.floor(diffDay / 7);
  return `${diffWeek}w ago`;
}

function formatDate(dateStr) {
  if (!dateStr) return "N/A";
  return new Date(dateStr).toLocaleString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

export default function TicketDetail({ ticket, user, onClose, onStatusChange, onResolve, onFeedback }) {
  const { T } = useTheme();
  const labelStyle = getLabelStyle(T);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  // Resolve form state
  const [showResolveForm, setShowResolveForm] = useState(false);
  // Feedback widget state
  const [showFeedback, setShowFeedback] = useState(false);

  const t = ticket;
  const p = priorityStyles[t.priority] || priorityStyles.medium;
  const s = statusStyles[t.status] || statusStyles.routed;
  const confidencePct = Math.round((t.confidence_score || 0) * 100);
  const canAct = user?.role === "engineer" || user?.role === "admin";

  async function handleStatusChange(newStatus) {
    setLoading(true);
    setError(null);
    try {
      await updateTicketStatus(t.id, newStatus);
      onStatusChange(t.id, newStatus);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }



  async function handleFeedbackSubmit() {
    if (feedbackRating < 1) return;
    setLoading(true);
    setError(null);
    try {
      await submitFeedback(t.id, feedbackRating, feedbackComment || null);
      onFeedback(t.id, feedbackRating, feedbackComment);
      setShowFeedback(false);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  // Classifier votes data
  const classifierVotes = [
    { name: "LLM", key: "llm", category: t.llm_category, confidence: t.llm_confidence },
    { name: "KNN", key: "knn", category: t.knn_category, confidence: t.knn_confidence },
    { name: "Centroid", key: "centroid", category: t.centroid_category, confidence: t.centroid_confidence },
    { name: "Keyword", key: "keyword", category: t.keyword_category, confidence: t.keyword_confidence },
  ];
  const hasVotes = classifierVotes.some((v) => v.category);

  return (
    <div
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 1000,
        background: "rgba(0,0,0,0.75)",
        backdropFilter: "blur(8px)",
        display: "flex",
        justifyContent: "center",
        alignItems: "flex-start",
        padding: "40px 24px",
        overflowY: "auto",
      }}
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div
        style={{
          width: "100%",
          maxWidth: 780,
          background: T.bg,
          border: `1px solid ${T.border}`,
          borderRadius: 20,
          overflow: "hidden",
          animation: "detailSlideIn 0.25s ease-out",
          position: "relative",
        }}
      >
        <style>{`
          @keyframes detailSlideIn { from { opacity:0; transform:translateY(16px) } to { opacity:1; transform:translateY(0) } }
        `}</style>

        {/* ── Close button ── */}
        <button
          onClick={onClose}
          style={{
            position: "absolute",
            top: 16,
            right: 16,
            zIndex: 10,
            width: 32,
            height: 32,
            borderRadius: 8,
            border: `1px solid ${T.border}`,
            background: "rgba(255,255,255,0.04)",
            color: T.textMuted,
            cursor: "pointer",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            transition: "all 0.15s",
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.borderColor = T.danger;
            e.currentTarget.style.color = T.danger;
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.borderColor = T.border;
            e.currentTarget.style.color = T.textMuted;
          }}
        >
          <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
            <path d="M2 2l10 10M12 2L2 12" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
          </svg>
        </button>

        {/* ── Header ── */}
        <div style={{
          padding: "28px 28px 20px",
          borderBottom: `1px solid ${T.border}`,
          background: T.card,
        }}>
          <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap", paddingRight: 40 }}>
            <span style={{
              fontFamily: "'JetBrains Mono', monospace",
              fontSize: 13,
              color: T.textMuted,
              fontWeight: 600,
            }}>
              Ticket #{t.id}
            </span>
            <span style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 5,
              fontSize: 11,
              fontWeight: 600,
              padding: "4px 12px",
              borderRadius: 12,
              background: s.bg,
              color: s.color,
              textTransform: "capitalize",
            }}>
              <span style={{ width: 6, height: 6, borderRadius: "50%", background: s.color, boxShadow: `0 0 8px ${s.color}60` }} />
              {(t.status || "").replace("_", " ")}
            </span>
            <span style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 5,
              fontSize: 11,
              fontWeight: 600,
              padding: "4px 12px",
              borderRadius: 12,
              background: p.bg,
              color: p.color,
              textTransform: "capitalize",
            }}>
              <span style={{ width: 6, height: 6, borderRadius: "50%", background: p.color, boxShadow: `0 0 8px ${p.color}40` }} />
              {t.priority}
            </span>
          </div>
          <h1 style={{
            fontSize: 22,
            fontWeight: 700,
            fontFamily: "'Inter', system-ui",
            color: T.text,
            margin: "12px 0 0",
            lineHeight: 1.3,
          }}>
            {t.title}
          </h1>
        </div>

        {/* ── Error bar ── */}
        {error && (
          <div style={{
            background: "rgba(239,68,68,0.1)",
            border: "none",
            borderBottom: "1px solid rgba(239,68,68,0.2)",
            padding: "10px 28px",
            color: T.danger,
            fontSize: 13,
          }}>
            {error}
          </div>
        )}

        {/* ── Content area ── */}
        <div style={{ padding: 28, display: "flex", flexDirection: "column", gap: 24 }}>

          {/* ── Info Section ── */}
          <div>
            <div style={labelStyle}>Description</div>
            <p style={{
              fontSize: 14,
              color: T.text,
              lineHeight: 1.7,
              margin: "6px 0 16px",
              fontFamily: "'Inter', system-ui",
            }}>
              {t.description || "No description provided."}
            </p>

            <div style={{ display: "flex", gap: 32, flexWrap: "wrap" }}>
              <div>
                <div style={labelStyle}>Submitted by</div>
                <div style={{ fontSize: 13, color: T.text, marginTop: 2 }}>
                  {t.submitted_by || t.created_by || "Unknown"}
                </div>
              </div>
              <div>
                <div style={labelStyle}>Created</div>
                <div style={{ fontSize: 13, color: T.text, marginTop: 2 }}>
                  {formatDate(t.created_at)}
                  <span style={{ color: T.textDim, fontSize: 11, marginLeft: 6 }}>
                    ({timeAgo(t.created_at)})
                  </span>
                </div>
              </div>
              {t.resolved_at && (
                <div>
                  <div style={labelStyle}>Resolved</div>
                  <div style={{ fontSize: 13, color: T.success, marginTop: 2 }}>
                    {formatDate(t.resolved_at)}
                  </div>
                </div>
              )}
              {t.routed_to && (
                <div>
                  <div style={labelStyle}>Routed to</div>
                  <div style={{ fontSize: 13, color: T.accent, fontWeight: 600, marginTop: 2 }}>
                    {t.routed_to}
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* ── AI Classification Card ── */}
          <div style={{
            background: "rgba(249,115,22,0.04)",
            border: `1px solid rgba(249,115,22,0.15)`,
            borderRadius: 14,
            padding: 22,
          }}>
            <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 16 }}>
              <div style={{
                width: 32,
                height: 32,
                borderRadius: 8,
                background: "rgba(249,115,22,0.12)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
              }}>
                <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
                  <path d="M8 1v2M8 13v2M1 8h2M13 8h2M3.05 3.05l1.41 1.41M11.54 11.54l1.41 1.41M3.05 12.95l1.41-1.41M11.54 4.46l1.41-1.41" stroke={T.accent} strokeWidth="1.3" strokeLinecap="round" />
                  <circle cx="8" cy="8" r="3" stroke={T.accent} strokeWidth="1.3" fill="none" />
                </svg>
              </div>
              <h3 style={{ margin: 0, fontSize: 15, fontWeight: 600, color: T.text, fontFamily: "'Inter', system-ui" }}>
                AI Classification
              </h3>
            </div>

            <div style={{ display: "flex", gap: 12, flexWrap: "wrap", marginBottom: 16 }}>
              {/* Category badge */}
              {t.category && (
                <span style={{
                  padding: "5px 14px",
                  borderRadius: 16,
                  fontSize: 11,
                  fontWeight: 600,
                  background: "rgba(249,115,22,0.12)",
                  color: T.accent,
                }}>
                  {t.category}
                </span>
              )}
              {/* Quality score badge */}
              {t.quality_score && (
                <span style={{
                  padding: "5px 14px",
                  borderRadius: 16,
                  fontSize: 11,
                  fontWeight: 600,
                  background: t.quality_score === "HIGH"
                    ? "rgba(34,197,94,0.12)"
                    : t.quality_score === "LOW"
                      ? "rgba(239,68,68,0.12)"
                      : "rgba(245,158,11,0.12)",
                  color: t.quality_score === "HIGH"
                    ? T.success
                    : t.quality_score === "LOW"
                      ? T.danger
                      : T.warning,
                }}>
                  {t.quality_score} quality
                </span>
              )}
            </div>

            {/* Confidence score bar */}
            <div style={{ marginBottom: 16 }}>
              <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6 }}>
                <span style={labelStyle}>Confidence</span>
                <span style={{
                  fontFamily: "'JetBrains Mono', monospace",
                  fontSize: 12,
                  fontWeight: 700,
                  color: confidencePct > 70 ? T.success : confidencePct > 50 ? T.warning : T.danger,
                }}>
                  {confidencePct}%
                </span>
              </div>
              <div style={{
                height: 6,
                borderRadius: 3,
                background: "rgba(255,255,255,0.06)",
                overflow: "hidden",
              }}>
                <div style={{
                  width: `${confidencePct}%`,
                  height: "100%",
                  borderRadius: 3,
                  background: confidencePct > 70 ? T.success : confidencePct > 50 ? T.warning : T.danger,
                  boxShadow: `0 0 12px ${confidencePct > 70 ? T.success : confidencePct > 50 ? T.warning : T.danger}40`,
                  transition: "width 0.5s ease-out",
                }} />
              </div>
            </div>

            {/* AI Reasoning */}
            {t.ai_reasoning && (
              <div style={{
                padding: 14,
                borderRadius: 10,
                background: "rgba(255,255,255,0.03)",
                border: `1px solid ${T.border}`,
                borderLeft: `3px solid ${T.accent}`,
              }}>
                <div style={{ ...labelStyle, marginBottom: 6 }}>AI Reasoning</div>
                <p style={{
                  fontSize: 13,
                  color: T.text,
                  lineHeight: 1.6,
                  margin: 0,
                  fontFamily: "'Inter', system-ui",
                }}>
                  {t.ai_reasoning}
                </p>
              </div>
            )}
          </div>

          {/* ── Classifier Votes Section ── */}
          {hasVotes && (
            <div>
              <h3 style={{
                fontSize: 14,
                fontWeight: 600,
                color: T.text,
                fontFamily: "'Inter', system-ui",
                marginBottom: 12,
              }}>
                Classifier Votes
              </h3>
              <div style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))",
                gap: 10,
              }}>
                {classifierVotes.map((v) => {
                  if (!v.category) return null;
                  const agrees =
                    t.category &&
                    (v.category || "").toLowerCase() === (t.category || "").toLowerCase();
                  const confPct = Math.round((v.confidence || 0) * 100);

                  return (
                    <div
                      key={v.key}
                      style={{
                        background: agrees ? "rgba(34,197,94,0.06)" : T.card,
                        border: `1px solid ${agrees ? "rgba(34,197,94,0.2)" : T.border}`,
                        borderRadius: 12,
                        padding: "14px 16px",
                      }}
                    >
                      <div style={{
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "space-between",
                        marginBottom: 8,
                      }}>
                        <span style={{
                          fontSize: 12,
                          fontWeight: 700,
                          color: agrees ? T.success : T.text,
                          fontFamily: "'JetBrains Mono', monospace",
                        }}>
                          {v.name}
                        </span>
                        {agrees && (
                          <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                            <circle cx="7" cy="7" r="6" fill="rgba(34,197,94,0.15)" />
                            <path d="M4 7l2 2 4-4" stroke={T.success} strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round" />
                          </svg>
                        )}
                      </div>
                      <div style={{
                        fontSize: 11,
                        color: agrees ? T.success : T.accent,
                        fontWeight: 600,
                        marginBottom: 4,
                      }}>
                        {v.category}
                      </div>
                      <div style={{
                        fontFamily: "'JetBrains Mono', monospace",
                        fontSize: 11,
                        color: T.textMuted,
                      }}>
                        {confPct}% confidence
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* ── Suggested Resolution ── */}
          {t.suggested_resolution && t.suggested_resolution.length > 0 && (
            <div style={{
              background: T.card,
              border: `1px solid ${T.border}`,
              borderRadius: 14,
              padding: 22,
            }}>
              <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 16 }}>
                <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
                  <circle cx="9" cy="9" r="8" stroke={T.accent} strokeWidth="1.3" fill="none" />
                  <path d="M9 5v4.5M9 12.5v.5" stroke={T.accent} strokeWidth="1.3" strokeLinecap="round" />
                </svg>
                <div>
                  <h3 style={{ margin: 0, fontSize: 14, fontWeight: 600, color: T.text, fontFamily: "'Inter', system-ui" }}>
                    Suggested Resolution
                  </h3>
                  {t.resolution_effectiveness != null && (
                    <span style={{ fontSize: 11, color: T.success }}>
                      {Math.round((t.resolution_effectiveness || 0) * 100)}% effectiveness
                    </span>
                  )}
                </div>
              </div>
              <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                {t.suggested_resolution.map((step, i) => (
                  <div key={i} style={{
                    display: "flex",
                    gap: 12,
                    alignItems: "flex-start",
                    padding: "10px 14px",
                    borderRadius: 10,
                    background: "rgba(255,255,255,0.02)",
                    border: `1px solid ${T.border}`,
                  }}>
                    <span style={{
                      minWidth: 22,
                      height: 22,
                      borderRadius: "50%",
                      background: "rgba(249,115,22,0.15)",
                      color: T.accent,
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      fontSize: 11,
                      fontWeight: 700,
                      fontFamily: "'JetBrains Mono', monospace",
                    }}>
                      {i + 1}
                    </span>
                    <span style={{ fontSize: 13, color: T.text, lineHeight: 1.5 }}>{step}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* ── Recommended Runbook ── */}
          {t.suggested_runbook && (
            <div style={{
              padding: "14px 18px",
              borderRadius: 12,
              background: "rgba(249,115,22,0.06)",
              border: "1px solid rgba(249,115,22,0.15)",
              display: "flex",
              alignItems: "center",
              gap: 12,
            }}>
              <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
                <rect x="2" y="1" width="14" height="16" rx="2" stroke={T.accent} strokeWidth="1.3" fill="none" />
                <line x1="5.5" y1="6" x2="12.5" y2="6" stroke={T.accent} strokeWidth="1" strokeLinecap="round" opacity="0.5" />
                <line x1="5.5" y1="9" x2="12.5" y2="9" stroke={T.accent} strokeWidth="1" strokeLinecap="round" opacity="0.5" />
                <line x1="5.5" y1="12" x2="10" y2="12" stroke={T.accent} strokeWidth="1" strokeLinecap="round" opacity="0.5" />
              </svg>
              <div>
                <div style={labelStyle}>Recommended Runbook</div>
                <div style={{ fontSize: 13, color: T.accent, fontWeight: 600, marginTop: 2 }}>
                  {t.suggested_runbook}
                </div>
              </div>
            </div>
          )}

          {/* ── Recommended Expert ── */}
          {t.recommended_expert && (
            <div style={{
              padding: "14px 18px",
              borderRadius: 12,
              background: "rgba(34,197,94,0.05)",
              border: "1px solid rgba(34,197,94,0.15)",
              display: "flex",
              alignItems: "center",
              gap: 12,
            }}>
              <div style={{
                width: 32,
                height: 32,
                borderRadius: "50%",
                background: "rgba(34,197,94,0.12)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                fontSize: 14,
                fontWeight: 700,
                color: T.success,
                fontFamily: "'Inter', system-ui",
              }}>
                {(t.recommended_expert || "?")[0].toUpperCase()}
              </div>
              <div>
                <div style={labelStyle}>Recommended Expert</div>
                <div style={{ fontSize: 13, color: T.text, fontWeight: 500, marginTop: 2 }}>
                  {t.recommended_expert}
                </div>
              </div>
            </div>
          )}

          {/* ── Action Buttons ── */}
          {canAct && (
            <div style={{
              borderTop: `1px solid ${T.border}`,
              paddingTop: 20,
              display: "flex",
              flexDirection: "column",
              gap: 12,
            }}>
              {loading && (
                <div style={{ textAlign: "center", padding: 8 }}>
                  <DeskMindSpinner size="sm" label="Updating..." />
                </div>
              )}

              {/* Routed status actions */}
              {t.status === "routed" && !loading && (
                <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
                  <ActionButton
                    label="Pick Up"
                    color="#3b82f6"
                    icon={
                      <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                        <path d="M7 1v12M1 7h12" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
                      </svg>
                    }
                    onClick={() => handleStatusChange("in_progress")}
                  />
                  <ActionButton
                    label="Escalate"
                    color={T.danger}
                    icon={
                      <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                        <path d="M7 10V4M4 6l3-3 3 3" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round" />
                      </svg>
                    }
                    onClick={() => handleStatusChange("escalated")}
                  />
                </div>
              )}

              {/* In progress — show who picked it up */}
              {t.status === "in_progress" && t.picked_up_by && (
                <div style={{
                  fontSize: 12,
                  color: "#3b82f6",
                  marginBottom: 10,
                  display: "flex",
                  alignItems: "center",
                  gap: 6,
                }}>
                  <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
                    <circle cx="6" cy="4" r="2.5" stroke="#3b82f6" strokeWidth="1.2" />
                    <path d="M1.5 11c0-2.5 2-4 4.5-4s4.5 1.5 4.5 4" stroke="#3b82f6" strokeWidth="1.2" strokeLinecap="round" />
                  </svg>
                  Picked up by <strong>{t.picked_up_by.split("@")[0]}</strong>
                </div>
              )}

              {/* In progress actions — only for the engineer who picked it up (or admin) */}
              {t.status === "in_progress" && !loading && !showResolveForm &&
               (user?.role === "admin" || !t.picked_up_by || t.picked_up_by === user?.email) && (
                <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
                  <ActionButton
                    label="Resolve"
                    color={T.success}
                    icon={
                      <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                        <path d="M3 7.5l3 3 5-6" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
                      </svg>
                    }
                    onClick={() => setShowResolveForm(true)}
                  />
                  <ActionButton
                    label="Escalate"
                    color={T.danger}
                    icon={
                      <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                        <path d="M7 10V4M4 6l3-3 3 3" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round" />
                      </svg>
                    }
                    onClick={() => handleStatusChange("escalated")}
                  />
                </div>
              )}

              {/* Resolve form */}
              {showResolveForm && !loading && (
                <ResolveForm
                  ticket={t}
                  onSubmit={async (data) => {
                    setLoading(true);
                    try {
                      await resolveTicket(t.id, data);
                      setShowResolveForm(false);
                      onResolve?.(t.id, data);
                    } catch (err) {
                      alert(err.message);
                    } finally {
                      setLoading(false);
                    }
                  }}
                  onCancel={() => setShowResolveForm(false)}
                />
              )}

              {/* Resolved actions */}
              {t.status === "resolved" && !loading && !showFeedback && (
                <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
                  <ActionButton
                    label="Reopen"
                    color={T.warning}
                    icon={
                      <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                        <path d="M2 7a5 5 0 019.33-2.5M12 7a5 5 0 01-9.33 2.5" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" />
                        <path d="M11.33 2v2.5H8.83" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round" />
                      </svg>
                    }
                    onClick={() => handleStatusChange("routed")}
                  />
                  {!t.feedback_rating && (
                    <ActionButton
                      label="Give Feedback"
                      color="#8b5cf6"
                      icon={
                        <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                          <path d="M7 1l1.76 3.57 3.94.57-2.85 2.78.67 3.93L7 10.07l-3.52 1.78.67-3.93L1.3 5.14l3.94-.57L7 1z" stroke="currentColor" strokeWidth="1.2" strokeLinejoin="round" fill="none" />
                        </svg>
                      }
                      onClick={() => setShowFeedback(true)}
                    />
                  )}
                  {t.feedback_rating && (
                    <span style={{
                      display: "inline-flex",
                      alignItems: "center",
                      gap: 4,
                      padding: "8px 14px",
                      fontSize: 12,
                      color: T.success,
                      background: "rgba(34,197,94,0.08)",
                      borderRadius: 8,
                      fontWeight: 500,
                    }}>
                      <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                        <path d="M3 7.5l3 3 5-6" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
                      </svg>
                      Feedback: {t.feedback_rating === "helpful" ? "\uD83D\uDC4D Helpful" : "\uD83D\uDC4E Not Helpful"}
                    </span>
                  )}
                </div>
              )}

              {/* Feedback widget */}
              {showFeedback && !t.feedback_rating && !loading && (
                <FeedbackWidget
                  ticketId={t.id}
                  onSubmit={async ({ rating, comment }) => {
                    await submitFeedback(t.id, rating, comment);
                    onFeedback?.(t.id, rating, comment);
                  }}
                />
              )}

              {/* Escalated actions */}
              {t.status === "escalated" && !loading && (
                <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
                  <ActionButton
                    label="Pick Up"
                    color="#3b82f6"
                    icon={
                      <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                        <path d="M7 1v12M1 7h12" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
                      </svg>
                    }
                    onClick={() => handleStatusChange("in_progress")}
                  />
                </div>
              )}

              {/* ── Audit Timeline ── */}
              <AuditTimeline ticketId={t.id} />
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ── Reusable action button ──
function ActionButton({ label, color, icon, onClick, type = "button", disabled = false }) {
  const { T } = useTheme();
  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled}
      style={{
        padding: "9px 18px",
        background: disabled ? "rgba(255,255,255,0.03)" : `${color}15`,
        border: `1px solid ${disabled ? T.border : color}30`,
        borderRadius: 8,
        color: disabled ? T.textDim : color,
        fontSize: 12,
        fontWeight: 600,
        cursor: disabled ? "not-allowed" : "pointer",
        display: "inline-flex",
        alignItems: "center",
        gap: 6,
        fontFamily: "'Inter', system-ui",
        transition: "all 0.15s",
      }}
      onMouseEnter={(e) => {
        if (!disabled) {
          e.currentTarget.style.background = `${color}25`;
        }
      }}
      onMouseLeave={(e) => {
        if (!disabled) {
          e.currentTarget.style.background = `${color}15`;
        }
      }}
    >
      {icon}
      {label}
    </button>
  );
}
