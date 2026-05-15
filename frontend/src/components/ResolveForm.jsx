import { useState } from "react";
import DeskMindSpinner from "./DeskMindSpinner";

const T = {
  bg: "#0C0C0F",
  card: "rgba(255,255,255,0.04)",
  border: "rgba(255,255,255,0.08)",
  text: "#F5F5F4",
  textMuted: "#78716C",
  textDim: "#44403C",
  accent: "#F97316",
  success: "#22c55e",
  danger: "#ef4444",
  warning: "#f59e0b",
};

export default function ResolveForm({ ticket, onSubmit, onCancel }) {
  const hasAiSuggestion =
    ticket.suggested_resolution && ticket.suggested_resolution.length > 0;

  // Build initial steps: pre-fill from AI or start with 3 empty
  const initialSteps = hasAiSuggestion
    ? [...ticket.suggested_resolution]
    : ["", "", ""];

  const [steps, setSteps] = useState(initialSteps);
  const [aiFeedback, setAiFeedback] = useState(
    hasAiSuggestion ? "yes" : "no"
  );
  const [runbook, setRunbook] = useState(ticket.suggested_runbook || "");
  const [submitting, setSubmitting] = useState(false);

  function updateStep(index, value) {
    setSteps((prev) => prev.map((s, i) => (i === index ? value : s)));
  }

  function removeStep(index) {
    setSteps((prev) => prev.filter((_, i) => i !== index));
  }

  function addStep() {
    setSteps((prev) => [...prev, ""]);
  }

  async function handleSubmit(e) {
    e.preventDefault();
    const validSteps = steps.filter((s) => s.trim() !== "");
    if (validSteps.length === 0) return;
    setSubmitting(true);
    try {
      await onSubmit({
        resolution_steps: validSteps,
        used_ai_suggestion: aiFeedback,
        used_runbook: runbook.trim() || null,
      });
    } finally {
      setSubmitting(false);
    }
  }

  const feedbackOptions = [
    { value: "yes", label: "Yes" },
    { value: "partially", label: "Partially" },
    { value: "no", label: "No" },
  ];

  return (
    <div style={overlayStyle}>
      <div style={modalStyle}>
        {/* Title */}
        <h2 style={titleStyle}>Resolve Ticket #{ticket.id}</h2>

        {/* AI Suggestion Reference Card */}
        {hasAiSuggestion && (
          <div style={aiCardStyle}>
            <div style={aiCardHeaderStyle}>
              <div style={aiLabelStyle}>
                <span style={aiDotStyle} />
                AI Suggestion
              </div>
              {ticket.resolution_effectiveness != null && (
                <span style={effectivenessStyle}>
                  {Math.round(ticket.resolution_effectiveness * 100)}% effective
                </span>
              )}
            </div>
            <ul style={aiStepsListStyle}>
              {ticket.suggested_resolution.map((step, i) => (
                <li key={i} style={aiStepItemStyle}>
                  <span style={aiStepNumStyle}>{i + 1}</span>
                  {step}
                </li>
              ))}
            </ul>
          </div>
        )}

        <form onSubmit={handleSubmit}>
          {/* Resolution Steps */}
          <div style={{ marginBottom: 24 }}>
            <label style={labelStyle}>Resolution Steps</label>
            {steps.map((step, i) => (
              <div key={i} style={stepRowStyle}>
                <span style={stepNumBadgeStyle}>{i + 1}</span>
                <input
                  type="text"
                  value={step}
                  onChange={(e) => updateStep(i, e.target.value)}
                  placeholder={`Step ${i + 1}...`}
                  style={inputStyle}
                />
                <button
                  type="button"
                  onClick={() => removeStep(i)}
                  style={removeButtonStyle}
                  title="Remove step"
                >
                  &times;
                </button>
              </div>
            ))}
            <button type="button" onClick={addStep} style={addStepButtonStyle}>
              + Add Step
            </button>
          </div>

          {/* AI Feedback */}
          <div style={{ marginBottom: 24 }}>
            <label style={labelStyle}>Did the AI suggestion help?</label>
            <div style={{ display: "flex", gap: 8 }}>
              {feedbackOptions.map((opt) => {
                const isActive = aiFeedback === opt.value;
                return (
                  <button
                    key={opt.value}
                    type="button"
                    onClick={() => setAiFeedback(opt.value)}
                    style={{
                      padding: "8px 18px",
                      borderRadius: 8,
                      fontSize: 13,
                      fontWeight: 600,
                      cursor: "pointer",
                      border: isActive
                        ? `1px solid ${T.accent}`
                        : `1px solid ${T.border}`,
                      background: isActive
                        ? "rgba(249,115,22,0.15)"
                        : "transparent",
                      color: isActive ? T.accent : T.textMuted,
                      transition: "all 0.15s",
                    }}
                  >
                    {opt.label}
                  </button>
                );
              })}
            </div>
          </div>

          {/* Runbook */}
          <div style={{ marginBottom: 28 }}>
            <label style={labelStyle}>Runbook Used</label>
            <input
              type="text"
              value={runbook}
              onChange={(e) => setRunbook(e.target.value)}
              placeholder="KB-0001 (optional)"
              style={{ ...inputStyle, maxWidth: 280 }}
            />
          </div>

          {/* Actions */}
          <div style={actionsRowStyle}>
            <button
              type="button"
              onClick={onCancel}
              disabled={submitting}
              style={cancelButtonStyle}
            >
              Cancel
            </button>
            <button type="submit" disabled={submitting} style={submitButtonStyle}>
              {submitting ? (
                <span style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <DeskMindSpinner size="sm" /> Submitting...
                </span>
              ) : (
                "Resolve Ticket"
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ── Styles ──

const overlayStyle = {
  position: "fixed",
  top: 0,
  left: 0,
  right: 0,
  bottom: 0,
  background: "rgba(0,0,0,0.7)",
  backdropFilter: "blur(6px)",
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  zIndex: 1000,
};

const modalStyle = {
  background: "#111114",
  border: "1px solid rgba(255,255,255,0.08)",
  borderRadius: 20,
  padding: 32,
  width: "100%",
  maxWidth: 580,
  maxHeight: "90vh",
  overflowY: "auto",
  boxShadow: "0 24px 80px rgba(0,0,0,0.6)",
};

const titleStyle = {
  fontSize: 20,
  fontWeight: 700,
  fontFamily: "'Inter', system-ui",
  color: "#F5F5F4",
  margin: "0 0 24px",
};

const labelStyle = {
  display: "block",
  fontSize: 11,
  fontWeight: 600,
  color: "#78716C",
  marginBottom: 8,
  letterSpacing: 1,
  textTransform: "uppercase",
  fontFamily: "'JetBrains Mono', monospace",
};

const inputStyle = {
  width: "100%",
  padding: "10px 14px",
  background: "rgba(255,255,255,0.06)",
  border: "1px solid rgba(255,255,255,0.1)",
  borderRadius: 8,
  color: "#F5F5F4",
  fontSize: 13,
  outline: "none",
  boxSizing: "border-box",
  fontFamily: "'JetBrains Mono', monospace",
};

const stepRowStyle = {
  display: "flex",
  alignItems: "center",
  gap: 8,
  marginBottom: 8,
};

const stepNumBadgeStyle = {
  width: 24,
  height: 24,
  borderRadius: "50%",
  background: "rgba(249,115,22,0.12)",
  color: "#F97316",
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  fontSize: 11,
  fontWeight: 700,
  fontFamily: "'JetBrains Mono', monospace",
  flexShrink: 0,
};

const removeButtonStyle = {
  width: 28,
  height: 28,
  borderRadius: 6,
  background: "rgba(239,68,68,0.08)",
  border: "1px solid rgba(239,68,68,0.15)",
  color: "#ef4444",
  fontSize: 16,
  cursor: "pointer",
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  flexShrink: 0,
  lineHeight: 1,
};

const addStepButtonStyle = {
  marginTop: 4,
  padding: "8px 16px",
  background: "transparent",
  border: `1px dashed rgba(255,255,255,0.12)`,
  borderRadius: 8,
  color: "#78716C",
  fontSize: 12,
  fontWeight: 600,
  cursor: "pointer",
  width: "100%",
  transition: "all 0.15s",
};

const actionsRowStyle = {
  display: "flex",
  justifyContent: "flex-end",
  gap: 12,
};

const cancelButtonStyle = {
  padding: "10px 22px",
  background: "rgba(239,68,68,0.08)",
  border: "1px solid rgba(239,68,68,0.2)",
  borderRadius: 8,
  color: "#ef4444",
  fontSize: 13,
  fontWeight: 600,
  cursor: "pointer",
};

const submitButtonStyle = {
  padding: "10px 24px",
  background: "#F97316",
  border: "none",
  borderRadius: 8,
  color: "#fff",
  fontSize: 13,
  fontWeight: 600,
  cursor: "pointer",
  boxShadow: "0 0 20px rgba(249,115,22,0.3)",
};

// AI Suggestion card styles

const aiCardStyle = {
  background: "rgba(249,115,22,0.05)",
  border: "1px solid rgba(249,115,22,0.15)",
  borderRadius: 12,
  padding: 20,
  marginBottom: 28,
};

const aiCardHeaderStyle = {
  display: "flex",
  justifyContent: "space-between",
  alignItems: "center",
  marginBottom: 12,
};

const aiLabelStyle = {
  display: "flex",
  alignItems: "center",
  gap: 8,
  fontSize: 12,
  fontWeight: 700,
  color: "#F97316",
  fontFamily: "'JetBrains Mono', monospace",
  textTransform: "uppercase",
  letterSpacing: 1,
};

const aiDotStyle = {
  width: 7,
  height: 7,
  borderRadius: "50%",
  background: "#F97316",
  boxShadow: "0 0 8px rgba(249,115,22,0.6)",
  display: "inline-block",
};

const effectivenessStyle = {
  fontSize: 12,
  fontWeight: 600,
  color: "#22c55e",
  fontFamily: "'JetBrains Mono', monospace",
};

const aiStepsListStyle = {
  listStyle: "none",
  margin: 0,
  padding: 0,
  display: "flex",
  flexDirection: "column",
  gap: 6,
};

const aiStepItemStyle = {
  display: "flex",
  alignItems: "center",
  gap: 10,
  fontSize: 13,
  color: "#F5F5F4",
  opacity: 0.85,
};

const aiStepNumStyle = {
  width: 20,
  height: 20,
  borderRadius: "50%",
  background: "rgba(249,115,22,0.18)",
  color: "#F97316",
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  fontSize: 10,
  fontWeight: 700,
  fontFamily: "'JetBrains Mono', monospace",
  flexShrink: 0,
};
