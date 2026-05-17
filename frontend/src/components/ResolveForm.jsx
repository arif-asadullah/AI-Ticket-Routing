import { useState } from "react";
import { createPortal } from "react-dom";
import { useTheme } from "../theme/ThemeContext";
import DeskMindSpinner from "./DeskMindSpinner";

export default function ResolveForm({ ticket, onSubmit, onCancel }) {
  const { T } = useTheme();
  const hasAiSuggestion =
    ticket.suggested_resolution && ticket.suggested_resolution.length > 0;

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

  const inputStyle = {
    width: "100%",
    padding: "10px 14px",
    background: T.inputBg,
    border: `1px solid ${T.inputBorder}`,
    borderRadius: 8,
    color: T.text,
    fontSize: 13,
    outline: "none",
    boxSizing: "border-box",
    fontFamily: "'JetBrains Mono', monospace",
  };

  const labelStyle = {
    display: "block",
    fontSize: 11,
    fontWeight: 600,
    color: T.textDim,
    marginBottom: 8,
    letterSpacing: 1,
    textTransform: "uppercase",
    fontFamily: "'JetBrains Mono', monospace",
  };

  return createPortal(
    <div
      onClick={onCancel}
      style={{
        position: "fixed",
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        background: "rgba(0,0,0,0.5)",
        backdropFilter: "blur(6px)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        zIndex: 1000,
      }}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          background: T.bgAlt,
          border: `1px solid ${T.border}`,
          borderRadius: 20,
          padding: 32,
          width: "100%",
          maxWidth: 580,
          maxHeight: "90vh",
          overflowY: "auto",
          boxShadow: "0 24px 80px rgba(0,0,0,0.3)",
        }}
      >
        {/* Title */}
        <h2
          style={{
            fontSize: 20,
            fontWeight: 700,
            fontFamily: "'Inter', system-ui",
            color: T.text,
            margin: "0 0 24px",
          }}
        >
          Resolve Ticket #{ticket.id}
        </h2>

        {/* AI Suggestion Reference Card */}
        {hasAiSuggestion && (
          <div
            style={{
              background: "rgba(249,115,22,0.05)",
              border: "1px solid rgba(249,115,22,0.15)",
              borderRadius: 12,
              padding: 20,
              marginBottom: 28,
            }}
          >
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                marginBottom: 12,
              }}
            >
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 8,
                  fontSize: 12,
                  fontWeight: 700,
                  color: T.accent,
                  fontFamily: "'JetBrains Mono', monospace",
                  textTransform: "uppercase",
                  letterSpacing: 1,
                }}
              >
                <span
                  style={{
                    width: 7,
                    height: 7,
                    borderRadius: "50%",
                    background: T.accent,
                    boxShadow: `0 0 8px rgba(249,115,22,0.6)`,
                    display: "inline-block",
                  }}
                />
                AI Suggestion
              </div>
              {ticket.resolution_effectiveness != null && (
                <span
                  style={{
                    fontSize: 12,
                    fontWeight: 600,
                    color: T.success,
                    fontFamily: "'JetBrains Mono', monospace",
                  }}
                >
                  {Math.round(ticket.resolution_effectiveness * 100)}% effective
                </span>
              )}
            </div>
            <ul
              style={{
                listStyle: "none",
                margin: 0,
                padding: 0,
                display: "flex",
                flexDirection: "column",
                gap: 6,
              }}
            >
              {ticket.suggested_resolution.map((step, i) => (
                <li
                  key={i}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 10,
                    fontSize: 13,
                    color: T.text,
                    opacity: 0.85,
                  }}
                >
                  <span
                    style={{
                      width: 20,
                      height: 20,
                      borderRadius: "50%",
                      background: "rgba(249,115,22,0.18)",
                      color: T.accent,
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      fontSize: 10,
                      fontWeight: 700,
                      fontFamily: "'JetBrains Mono', monospace",
                      flexShrink: 0,
                    }}
                  >
                    {i + 1}
                  </span>
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
              <div
                key={i}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 8,
                  marginBottom: 8,
                }}
              >
                <span
                  style={{
                    width: 24,
                    height: 24,
                    borderRadius: "50%",
                    background: "rgba(249,115,22,0.12)",
                    color: T.accent,
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    fontSize: 11,
                    fontWeight: 700,
                    fontFamily: "'JetBrains Mono', monospace",
                    flexShrink: 0,
                  }}
                >
                  {i + 1}
                </span>
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
                  style={{
                    width: 28,
                    height: 28,
                    borderRadius: 6,
                    background: "rgba(239,68,68,0.08)",
                    border: "1px solid rgba(239,68,68,0.15)",
                    color: T.danger,
                    fontSize: 16,
                    cursor: "pointer",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    flexShrink: 0,
                    lineHeight: 1,
                  }}
                  title="Remove step"
                >
                  &times;
                </button>
              </div>
            ))}
            <button
              type="button"
              onClick={addStep}
              style={{
                marginTop: 4,
                padding: "8px 16px",
                background: "transparent",
                border: `1px dashed ${T.border}`,
                borderRadius: 8,
                color: T.textMuted,
                fontSize: 12,
                fontWeight: 600,
                cursor: "pointer",
                width: "100%",
              }}
            >
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
          <div
            style={{
              display: "flex",
              justifyContent: "flex-end",
              gap: 12,
            }}
          >
            <button
              type="button"
              onClick={onCancel}
              disabled={submitting}
              style={{
                padding: "10px 22px",
                background: "transparent",
                border: `1px solid ${T.border}`,
                borderRadius: 8,
                color: T.textMuted,
                fontSize: 13,
                fontWeight: 600,
                cursor: "pointer",
              }}
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={submitting}
              style={{
                padding: "10px 24px",
                background: submitting
                  ? "rgba(249,115,22,0.5)"
                  : "linear-gradient(135deg, #F97316, #EA580C)",
                border: "none",
                borderRadius: 8,
                color: "#fff",
                fontSize: 13,
                fontWeight: 600,
                cursor: submitting ? "wait" : "pointer",
                boxShadow: "0 0 20px rgba(249,115,22,0.3)",
                display: "flex",
                alignItems: "center",
                gap: 8,
              }}
            >
              {submitting ? (
                <>
                  <DeskMindSpinner size="sm" /> Submitting...
                </>
              ) : (
                "Resolve Ticket"
              )}
            </button>
          </div>
        </form>
      </div>
    </div>,
    document.body
  );
}
