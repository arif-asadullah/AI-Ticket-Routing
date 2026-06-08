import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { useTheme } from "../theme/ThemeContext";
import { getRunbook } from "../services/api";
import DeskMindSpinner from "./DeskMindSpinner";

export default function RunbookModal({ runbookId, onClose }) {
  const { T } = useTheme();
  const [runbook, setRunbook] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError("");
    getRunbook(runbookId)
      .then((data) => {
        if (active) setRunbook(data);
      })
      .catch((err) => {
        if (active) setError(err.message);
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [runbookId]);

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
          maxWidth: 560,
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
            alignItems: "flex-start",
            gap: 12,
          }}
        >
          <div>
            <div
              style={{
                fontSize: 10,
                fontWeight: 600,
                color: T.textDim,
                textTransform: "uppercase",
                letterSpacing: 1,
                fontFamily: "'JetBrains Mono', monospace",
                marginBottom: 4,
              }}
            >
              Runbook {runbookId}
            </div>
            <h3
              style={{
                margin: 0,
                fontSize: 16,
                fontWeight: 600,
                color: T.text,
                fontFamily: "'Inter', system-ui",
              }}
            >
              {runbook?.title || "Loading…"}
            </h3>
            {runbook?.category && (
              <span
                style={{
                  display: "inline-block",
                  marginTop: 8,
                  padding: "3px 10px",
                  borderRadius: 12,
                  fontSize: 11,
                  fontWeight: 600,
                  background: "rgba(249,115,22,0.12)",
                  color: T.accent,
                }}
              >
                {runbook.category}
              </span>
            )}
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
              lineHeight: 1,
            }}
          >
            &times;
          </button>
        </div>

        {/* Body */}
        <div style={{ padding: "20px 24px" }}>
          {loading && (
            <div style={{ textAlign: "center", padding: 24 }}>
              <DeskMindSpinner size="sm" label="Loading runbook…" />
            </div>
          )}

          {!loading && error && (
            <div
              style={{
                padding: "10px 14px",
                background: "rgba(239,68,68,0.1)",
                border: "1px solid rgba(239,68,68,0.3)",
                borderRadius: 8,
                color: T.danger,
                fontSize: 13,
              }}
            >
              {error}
            </div>
          )}

          {!loading && !error && runbook && (
            <ol style={{ margin: 0, padding: 0, listStyle: "none" }}>
              {(runbook.steps || []).map((step, i) => (
                <li
                  key={i}
                  style={{
                    display: "flex",
                    gap: 12,
                    alignItems: "flex-start",
                    padding: "10px 12px",
                    marginBottom: 8,
                    background: T.card,
                    borderRadius: 8,
                    border: `1px solid ${T.border}`,
                  }}
                >
                  <span
                    style={{
                      flexShrink: 0,
                      width: 22,
                      height: 22,
                      borderRadius: "50%",
                      background: "rgba(249,115,22,0.12)",
                      color: T.accent,
                      fontSize: 11,
                      fontWeight: 700,
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      fontFamily: "'JetBrains Mono', monospace",
                    }}
                  >
                    {i + 1}
                  </span>
                  <span
                    style={{
                      fontSize: 13,
                      color: T.text,
                      lineHeight: 1.5,
                      fontFamily: "'JetBrains Mono', monospace",
                      wordBreak: "break-word",
                    }}
                  >
                    {step}
                  </span>
                </li>
              ))}
              {(!runbook.steps || runbook.steps.length === 0) && (
                <div style={{ fontSize: 13, color: T.textMuted }}>
                  This runbook has no steps recorded.
                </div>
              )}
            </ol>
          )}
        </div>
      </div>
    </div>,
    document.body
  );
}
