import { useState } from "react";
import { createPortal } from "react-dom";
import { useTheme } from "../theme/ThemeContext";
import { overrideClassification } from "../services/api";
import DeskMindSpinner from "./DeskMindSpinner";

const CATEGORIES = [
  "Infrastructure",
  "Application",
  "Database",
  "Network",
  "Security",
  "Access Management",
];

const PRIORITIES = ["critical", "high", "medium", "low"];

const CLASSIFIER_LABELS = {
  llm: "LLM (Qwen 2.5)",
  centroid: "Centroid",
  knn: "KNN",
  keyword: "Keyword",
};

const CLASSIFIER_WEIGHTS = {
  llm: 0.4,
  centroid: 0.3,
  knn: 0.15,
  keyword: 0.15,
};

export default function OverrideModal({ ticket, onClose, onOverride }) {
  const { T } = useTheme();
  const [category, setCategory] = useState(ticket.category || "");
  const [priority, setPriority] = useState(ticket.priority || "medium");
  const [reason, setReason] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const votes = ticket.classifier_votes || {};
  const changed = category !== ticket.category || priority !== ticket.priority;

  async function handleSubmit(e) {
    e.preventDefault();
    if (!reason.trim()) {
      setError("Reason is required");
      return;
    }
    if (!changed) {
      setError("Select a different category or priority");
      return;
    }
    setError("");
    setLoading(true);
    try {
      const updated = await overrideClassification(ticket.id, {
        category,
        priority: priority !== ticket.priority ? priority : null,
        reason: reason.trim(),
      });
      onOverride?.(updated);
      onClose();
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  // Collect top-3 unique category predictions from classifiers
  const predictionMap = {};
  Object.values(votes).forEach((v) => {
    if (v?.category) {
      const cat = v.category;
      if (!predictionMap[cat]) predictionMap[cat] = { count: 0, totalConf: 0 };
      predictionMap[cat].count += 1;
      predictionMap[cat].totalConf += v.confidence || 0;
    }
  });
  const top3 = Object.entries(predictionMap)
    .sort((a, b) => b[1].totalConf - a[1].totalConf)
    .slice(0, 3);

  return createPortal(
    <div
      onClick={onClose}
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 1000,
        background: "rgba(0,0,0,0.5)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        backdropFilter: "blur(4px)",
      }}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          background: T.bgAlt,
          borderRadius: 16,
          border: `1px solid ${T.border}`,
          width: "100%",
          maxWidth: 520,
          maxHeight: "90vh",
          overflow: "auto",
          boxShadow: "0 20px 60px rgba(0,0,0,0.3)",
        }}
      >
        {/* Header */}
        <div
          style={{
            padding: "20px 24px 16px",
            borderBottom: `1px solid ${T.border}`,
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
          }}
        >
          <div>
            <h3
              style={{
                margin: 0,
                fontSize: 16,
                fontWeight: 600,
                color: T.text,
                fontFamily: "'Inter', system-ui",
              }}
            >
              Override Classification
            </h3>
            <p style={{ margin: "4px 0 0", fontSize: 12, color: T.textMuted }}>
              #{ticket.id} — {ticket.title}
            </p>
          </div>
          <button
            onClick={onClose}
            style={{
              background: "none",
              border: "none",
              color: T.textMuted,
              cursor: "pointer",
              fontSize: 18,
              padding: 4,
            }}
          >
            &times;
          </button>
        </div>

        <div style={{ padding: "20px 24px" }}>
          {/* AI Predictions Reference */}
          <div
            style={{
              marginBottom: 20,
              padding: 14,
              background: T.card,
              borderRadius: 10,
              border: `1px solid ${T.border}`,
            }}
          >
            <div
              style={{
                fontSize: 10,
                fontWeight: 600,
                color: T.textDim,
                textTransform: "uppercase",
                letterSpacing: 1,
                fontFamily: "'JetBrains Mono', monospace",
                marginBottom: 10,
              }}
            >
              AI Predictions
            </div>

            {/* Top 3 predictions */}
            {top3.length > 0 && (
              <div style={{ marginBottom: 12 }}>
                {top3.map(([cat, info], i) => (
                  <div
                    key={cat}
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: 8,
                      marginBottom: 6,
                    }}
                  >
                    <span
                      style={{
                        fontSize: 10,
                        fontWeight: 700,
                        color: i === 0 ? T.accent : T.textDim,
                        width: 16,
                        fontFamily: "'JetBrains Mono', monospace",
                      }}
                    >
                      #{i + 1}
                    </span>
                    <span
                      style={{
                        fontSize: 12,
                        color: T.text,
                        fontWeight: i === 0 ? 600 : 400,
                        flex: 1,
                      }}
                    >
                      {cat}
                    </span>
                    <span
                      style={{
                        fontSize: 11,
                        color: T.textMuted,
                        fontFamily: "'JetBrains Mono', monospace",
                      }}
                    >
                      {info.count}/{Object.keys(votes).length} votes
                    </span>
                  </div>
                ))}
              </div>
            )}

            {/* Individual classifier votes */}
            <div
              style={{
                display: "grid",
                gridTemplateColumns: "1fr 1fr",
                gap: 8,
              }}
            >
              {Object.entries(CLASSIFIER_LABELS).map(([key, label]) => {
                const v = votes[key];
                if (!v) return null;
                const conf = Math.round((v.confidence || 0) * 100);
                return (
                  <div
                    key={key}
                    style={{
                      padding: "8px 10px",
                      background: T.bg,
                      borderRadius: 8,
                      border: `1px solid ${T.border}`,
                    }}
                  >
                    <div
                      style={{
                        fontSize: 10,
                        color: T.textDim,
                        marginBottom: 3,
                        fontFamily: "'JetBrains Mono', monospace",
                      }}
                    >
                      {label}{" "}
                      <span style={{ opacity: 0.5 }}>
                        ({Math.round(CLASSIFIER_WEIGHTS[key] * 100)}%)
                      </span>
                    </div>
                    <div
                      style={{
                        fontSize: 12,
                        color: T.text,
                        fontWeight: 500,
                      }}
                    >
                      {v.category || "N/A"}
                    </div>
                    <div
                      style={{
                        marginTop: 4,
                        height: 3,
                        borderRadius: 2,
                        background: T.border,
                        overflow: "hidden",
                      }}
                    >
                      <div
                        style={{
                          width: `${conf}%`,
                          height: "100%",
                          borderRadius: 2,
                          background:
                            conf >= 70
                              ? T.success
                              : conf >= 50
                                ? T.warning
                                : T.danger,
                        }}
                      />
                    </div>
                    <div
                      style={{
                        fontSize: 10,
                        color: T.textMuted,
                        marginTop: 2,
                        fontFamily: "'JetBrains Mono', monospace",
                      }}
                    >
                      {conf}%
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Override Form */}
          <form onSubmit={handleSubmit}>
            {/* Category */}
            <label
              style={{
                display: "block",
                fontSize: 10,
                fontWeight: 600,
                color: T.textDim,
                marginBottom: 6,
                textTransform: "uppercase",
                letterSpacing: 1,
                fontFamily: "'JetBrains Mono', monospace",
              }}
            >
              New Category
            </label>
            <select
              value={category}
              onChange={(e) => setCategory(e.target.value)}
              style={{
                width: "100%",
                padding: "10px 14px",
                background: T.inputBg,
                border: `2px solid ${category !== ticket.category ? "rgba(249,115,22,0.4)" : T.inputBorder}`,
                borderRadius: 10,
                color: T.text,
                fontSize: 13,
                fontWeight: 500,
                marginBottom: 16,
                outline: "none",
                cursor: "pointer",
                appearance: "none",
                WebkitAppearance: "none",
                backgroundImage: `url("data:image/svg+xml,%3Csvg width='12' height='12' viewBox='0 0 12 12' fill='none' xmlns='http://www.w3.org/2000/svg'%3E%3Cpath d='M3 4.5l3 3 3-3' stroke='%23999' stroke-width='1.5' stroke-linecap='round'/%3E%3C/svg%3E")`,
                backgroundRepeat: "no-repeat",
                backgroundPosition: "right 12px center",
                fontFamily: "'Inter', system-ui",
              }}
            >
              {CATEGORIES.map((cat) => (
                <option key={cat} value={cat}>
                  {cat}
                  {cat === ticket.category ? " (current)" : ""}
                </option>
              ))}
            </select>

            {/* Priority */}
            <label
              style={{
                display: "block",
                fontSize: 10,
                fontWeight: 600,
                color: T.textDim,
                marginBottom: 6,
                textTransform: "uppercase",
                letterSpacing: 1,
                fontFamily: "'JetBrains Mono', monospace",
              }}
            >
              Priority
            </label>
            <select
              value={priority}
              onChange={(e) => setPriority(e.target.value)}
              style={{
                width: "100%",
                padding: "10px 14px",
                background: T.inputBg,
                border: `2px solid ${priority !== ticket.priority ? "rgba(249,115,22,0.4)" : T.inputBorder}`,
                borderRadius: 10,
                color: T.text,
                fontSize: 13,
                fontWeight: 500,
                marginBottom: 16,
                outline: "none",
                cursor: "pointer",
                appearance: "none",
                WebkitAppearance: "none",
                backgroundImage: `url("data:image/svg+xml,%3Csvg width='12' height='12' viewBox='0 0 12 12' fill='none' xmlns='http://www.w3.org/2000/svg'%3E%3Cpath d='M3 4.5l3 3 3-3' stroke='%23999' stroke-width='1.5' stroke-linecap='round'/%3E%3C/svg%3E")`,
                backgroundRepeat: "no-repeat",
                backgroundPosition: "right 12px center",
                textTransform: "capitalize",
                fontFamily: "'Inter', system-ui",
              }}
            >
              {PRIORITIES.map((p) => (
                <option key={p} value={p}>
                  {p.charAt(0).toUpperCase() + p.slice(1)}
                  {p === ticket.priority ? " (current)" : ""}
                </option>
              ))}
            </select>

            {/* Reason */}
            <label
              style={{
                display: "block",
                fontSize: 10,
                fontWeight: 600,
                color: T.textDim,
                marginBottom: 6,
                textTransform: "uppercase",
                letterSpacing: 1,
                fontFamily: "'JetBrains Mono', monospace",
              }}
            >
              Reason <span style={{ color: T.danger }}>*</span>
            </label>
            <textarea
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              placeholder="Why is the AI classification incorrect?"
              rows={3}
              style={{
                width: "100%",
                padding: "10px 14px",
                background: T.inputBg,
                border: `2px solid ${reason.trim() ? "rgba(249,115,22,0.4)" : T.inputBorder}`,
                borderRadius: 10,
                color: T.text,
                fontSize: 13,
                resize: "vertical",
                outline: "none",
                fontFamily: "'Inter', system-ui",
                boxSizing: "border-box",
              }}
            />

            {/* Error */}
            {error && (
              <div
                style={{
                  marginTop: 10,
                  padding: "8px 12px",
                  background: "rgba(239,68,68,0.1)",
                  border: "1px solid rgba(239,68,68,0.3)",
                  borderRadius: 8,
                  color: T.danger,
                  fontSize: 12,
                }}
              >
                {error}
              </div>
            )}

            {/* Buttons */}
            <div
              style={{
                display: "flex",
                gap: 10,
                justifyContent: "flex-end",
                marginTop: 20,
              }}
            >
              <button
                type="button"
                onClick={onClose}
                style={{
                  padding: "10px 20px",
                  border: `1px solid ${T.border}`,
                  borderRadius: 8,
                  background: "transparent",
                  color: T.textMuted,
                  fontSize: 13,
                  cursor: "pointer",
                }}
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={loading || !changed}
                style={{
                  padding: "10px 20px",
                  border: "none",
                  borderRadius: 8,
                  background:
                    loading || !changed
                      ? "rgba(249,115,22,0.4)"
                      : "linear-gradient(135deg, #F97316, #EA580C)",
                  color: "#fff",
                  fontSize: 13,
                  fontWeight: 600,
                  cursor: loading || !changed ? "not-allowed" : "pointer",
                  display: "flex",
                  alignItems: "center",
                  gap: 8,
                }}
              >
                {loading ? (
                  <>
                    <DeskMindSpinner size="sm" /> Overriding...
                  </>
                ) : (
                  "Override Classification"
                )}
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>,
    document.body
  );
}
