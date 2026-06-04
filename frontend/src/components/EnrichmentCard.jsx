import { useState } from "react";
import { useTheme } from "../theme/ThemeContext";
import { enrichTicket } from "../services/api";
import DeskMindSpinner from "./DeskMindSpinner";

export default function EnrichmentCard({ enrichment, ticket, interactive = false, onEnriched }) {
  const { T } = useTheme();
  const [answers, setAnswers] = useState({});
  const [customInputs, setCustomInputs] = useState({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  // Read-only mode — show what was answered (after enrichment, 'needed' may not exist)
  if (!interactive && enrichment?.answers) {
    return (
      <div style={{
        background: "rgba(34,197,94,0.04)",
        border: `1px solid rgba(34,197,94,0.2)`,
        borderLeft: `4px solid ${T.success}`,
        borderRadius: 14,
        padding: 22,
        marginTop: 16,
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 14 }}>
          <div style={{
            width: 32, height: 32, borderRadius: 8,
            background: "rgba(34,197,94,0.12)",
            display: "flex", alignItems: "center", justifyContent: "center",
            fontSize: 16,
          }}>
            AI
          </div>
          <div>
            <h4 style={{ margin: 0, fontSize: 14, fontWeight: 600, color: T.text, fontFamily: "'Inter', system-ui" }}>
              Enrichment Applied
            </h4>
            <span style={{
              fontSize: 12, color: T.success, fontWeight: 600,
              fontFamily: "'JetBrains Mono', monospace",
            }}>
              Additional details provided by user
            </span>
          </div>
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          {Object.entries(enrichment.answers).map(([key, val]) => (
            <div key={key} style={{ display: "flex", gap: 8, fontSize: 13 }}>
              <span style={{ color: T.textMuted, minWidth: 100, fontFamily: "'JetBrains Mono', monospace", fontSize: 11, textTransform: "uppercase" }}>
                {key}:
              </span>
              <span style={{ color: T.text, fontWeight: 500 }}>{val}</span>
            </div>
          ))}
        </div>
      </div>
    );
  }

  // Interactive mode requires 'needed' flag
  if (!enrichment?.needed) return null;

  function setAnswer(qId, value) {
    setAnswers((prev) => ({ ...prev, [qId]: value }));
    // Clear custom input when a chip is selected
    setCustomInputs((prev) => ({ ...prev, [qId]: "" }));
  }

  function setCustom(qId, value) {
    setCustomInputs((prev) => ({ ...prev, [qId]: value }));
    setAnswers((prev) => ({ ...prev, [qId]: value }));
  }

  async function handleSubmit() {
    // Filter out empty answers
    const filled = {};
    for (const [k, v] of Object.entries(answers)) {
      if (v && v.trim()) filled[k] = v.trim();
    }
    if (Object.keys(filled).length === 0) {
      setError("Please answer at least one question");
      return;
    }

    setLoading(true);
    setError(null);
    try {
      const updated = await enrichTicket(ticket.id, filled);
      onEnriched?.(updated);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  const questions = enrichment.questions || [];
  const similar = enrichment.similar_tickets || [];

  return (
    <div style={{
      background: "rgba(245,158,11,0.04)",
      border: "1px solid rgba(245,158,11,0.2)",
      borderLeft: "4px solid #f59e0b",
      borderRadius: 14,
      padding: 22,
      marginTop: 16,
    }}>
      {/* Header */}
      <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 6 }}>
        <div style={{
          width: 32, height: 32, borderRadius: 8,
          background: "rgba(245,158,11,0.12)",
          display: "flex", alignItems: "center", justifyContent: "center",
          fontSize: 16,
        }}>
          AI
        </div>
        <div>
          <h4 style={{ margin: 0, fontSize: 14, fontWeight: 600, color: T.text, fontFamily: "'Inter', system-ui" }}>
            DeskMind needs more details
          </h4>
          <p style={{ margin: "2px 0 0", fontSize: 12, color: T.textMuted }}>
            {enrichment.reason}
          </p>
        </div>
      </div>

      {/* User context hint */}
      {enrichment.user_context?.ticket_count > 0 && (
        <div style={{
          margin: "12px 0",
          padding: "8px 12px",
          borderRadius: 8,
          background: T.card,
          border: `1px solid ${T.border}`,
          fontSize: 12,
          color: T.textMuted,
          display: "flex", alignItems: "center", gap: 6,
        }}>
          <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
            <circle cx="7" cy="7" r="5.5" stroke={T.textMuted} strokeWidth="1" />
            <path d="M7 4v3.5M7 9v.5" stroke={T.textMuted} strokeWidth="1.2" strokeLinecap="round" />
          </svg>
          Based on your {enrichment.user_context.ticket_count} previous tickets
          {enrichment.user_context.common_categories?.length > 0 && (
            <> &mdash; you often report <strong style={{ color: T.text }}>{enrichment.user_context.common_categories[0]}</strong> issues</>
          )}
        </div>
      )}

      {/* Questions */}
      <div style={{ display: "flex", flexDirection: "column", gap: 18, marginTop: 16 }}>
        {questions.map((q) => (
          <div key={q.id}>
            <label style={{
              display: "block", fontSize: 13, fontWeight: 600, color: T.text,
              marginBottom: 8, fontFamily: "'Inter', system-ui",
            }}>
              {q.question}
            </label>

            {/* Suggestion chips */}
            {q.suggestions?.length > 0 && (
              <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginBottom: q.type === "text" ? 8 : 0 }}>
                {q.suggestions.map((s) => {
                  const isSelected = answers[q.id] === s && !customInputs[q.id];
                  return (
                    <button
                      key={s}
                      onClick={() => setAnswer(q.id, s)}
                      style={{
                        padding: "7px 14px",
                        borderRadius: 20,
                        fontSize: 12,
                        fontWeight: 500,
                        cursor: "pointer",
                        border: isSelected
                          ? "1px solid rgba(249,115,22,0.5)"
                          : `1px solid ${T.border}`,
                        background: isSelected
                          ? "rgba(249,115,22,0.12)"
                          : "transparent",
                        color: isSelected ? T.accent : T.text,
                        transition: "all 0.15s",
                        fontFamily: "'Inter', system-ui",
                      }}
                    >
                      {s}
                    </button>
                  );
                })}
              </div>
            )}

            {/* Text input for "text" type or custom answer */}
            {q.type === "text" && (
              <input
                type="text"
                value={customInputs[q.id] || ""}
                onChange={(e) => setCustom(q.id, e.target.value)}
                placeholder={q.hint || "Type your answer..."}
                style={{
                  width: "100%",
                  padding: "9px 14px",
                  background: T.inputBg,
                  border: `1px solid ${T.inputBorder}`,
                  borderRadius: 8,
                  color: T.text,
                  fontSize: 13,
                  outline: "none",
                  boxSizing: "border-box",
                  fontFamily: "'Inter', system-ui",
                }}
              />
            )}

            {/* Hint */}
            {q.hint && q.type !== "text" && (
              <p style={{ margin: "6px 0 0", fontSize: 11, color: T.textDim, fontStyle: "italic" }}>
                {q.hint}
              </p>
            )}
          </div>
        ))}
      </div>

      {/* Similar tickets reference */}
      {similar.length > 0 && (
        <div style={{
          marginTop: 16, paddingTop: 14,
          borderTop: `1px solid ${T.border}`,
        }}>
          <div style={{
            fontSize: 10, fontWeight: 600, color: T.textDim,
            textTransform: "uppercase", letterSpacing: 1,
            fontFamily: "'JetBrains Mono', monospace",
            marginBottom: 8,
          }}>
            Similar past tickets
          </div>
          {similar.map((s) => (
            <div key={s.id} style={{
              display: "flex", alignItems: "center", gap: 8,
              padding: "6px 0", fontSize: 12, color: T.textMuted,
            }}>
              <span style={{
                padding: "2px 8px", borderRadius: 4,
                background: "rgba(249,115,22,0.08)",
                color: T.accent, fontSize: 10,
                fontFamily: "'JetBrains Mono', monospace",
                fontWeight: 600,
              }}>
                #{s.id}
              </span>
              <span style={{ color: T.text, flex: 1 }}>
                {s.title?.length > 50 ? s.title.slice(0, 47) + "..." : s.title}
              </span>
              <span style={{
                fontSize: 10, color: T.textDim,
                fontFamily: "'JetBrains Mono', monospace",
              }}>
                {Math.round(s.similarity * 100)}% similar
              </span>
            </div>
          ))}
        </div>
      )}

      {/* Error */}
      {error && (
        <div style={{
          marginTop: 12, padding: "8px 12px",
          background: "rgba(239,68,68,0.08)",
          border: "1px solid rgba(239,68,68,0.2)",
          borderRadius: 8, color: T.danger, fontSize: 12,
        }}>
          {error}
        </div>
      )}

      {/* Submit button */}
      <div style={{ marginTop: 18, display: "flex", justifyContent: "flex-end" }}>
        <button
          onClick={handleSubmit}
          disabled={loading || Object.keys(answers).length === 0}
          style={{
            padding: "10px 22px",
            borderRadius: 8,
            border: "none",
            background: loading || Object.keys(answers).length === 0
              ? "rgba(249,115,22,0.3)"
              : "linear-gradient(135deg, #F97316, #EA580C)",
            color: "#fff",
            fontSize: 13,
            fontWeight: 600,
            cursor: loading || Object.keys(answers).length === 0 ? "not-allowed" : "pointer",
            display: "flex", alignItems: "center", gap: 8,
            boxShadow: "0 0 16px rgba(249,115,22,0.2)",
            fontFamily: "'Inter', system-ui",
          }}
        >
          {loading ? (
            <>
              <DeskMindSpinner size="sm" /> Re-classifying...
            </>
          ) : (
            <>
              <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                <path d="M1 7l4 4L13 3" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
              Submit &amp; Re-classify
            </>
          )}
        </button>
      </div>
    </div>
  );
}
