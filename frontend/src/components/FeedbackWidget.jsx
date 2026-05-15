import { useState } from "react";
import { useTheme } from "../theme/ThemeContext";

export default function FeedbackWidget({ ticketId, onSubmit }) {
  const { T } = useTheme();
  const { containerStyle, headingStyle, textareaStyle, submitButtonStyle, thankYouStyle, checkIconStyle } = getFeedbackStyles(T);
  const [rating, setRating] = useState(null); // "helpful" | "not_helpful"
  const [comment, setComment] = useState("");
  const [submitted, setSubmitted] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit() {
    setSubmitting(true);
    try {
      await onSubmit({
        rating,
        comment: comment.trim() || null,
      });
      setSubmitted(true);
    } finally {
      setSubmitting(false);
    }
  }

  if (submitted) {
    return (
      <div style={containerStyle}>
        <div style={thankYouStyle}>
          <span style={checkIconStyle}>&#10003;</span>
          Thanks for your feedback!
        </div>
      </div>
    );
  }

  return (
    <div style={containerStyle}>
      {/* Label */}
      <label style={headingStyle}>Rate the AI's suggestion</label>

      {/* Rating Buttons */}
      <div style={{ display: "flex", gap: 10, marginBottom: rating ? 16 : 0 }}>
        {/* Helpful */}
        <button
          type="button"
          onClick={() => setRating("helpful")}
          disabled={submitted}
          style={{
            ...ratingButtonBase,
            borderColor:
              rating === "helpful"
                ? T.success
                : "rgba(34,197,94,0.25)",
            background:
              rating === "helpful"
                ? "rgba(34,197,94,0.15)"
                : "transparent",
            color:
              rating === "helpful" ? T.success : "rgba(34,197,94,0.7)",
          }}
        >
          <span style={{ fontSize: 16 }}>{"\uD83D\uDC4D"}</span>
          Helpful
        </button>

        {/* Not Helpful */}
        <button
          type="button"
          onClick={() => setRating("not_helpful")}
          disabled={submitted}
          style={{
            ...ratingButtonBase,
            borderColor:
              rating === "not_helpful"
                ? T.danger
                : "rgba(239,68,68,0.25)",
            background:
              rating === "not_helpful"
                ? "rgba(239,68,68,0.15)"
                : "transparent",
            color:
              rating === "not_helpful" ? T.danger : "rgba(239,68,68,0.7)",
          }}
        >
          <span style={{ fontSize: 16 }}>{"\uD83D\uDC4E"}</span>
          Not Helpful
        </button>
      </div>

      {/* Comment textarea — appears after selecting a rating */}
      {rating && (
        <div style={{ marginBottom: 14 }}>
          <textarea
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            placeholder="Tell us more (optional)"
            rows={3}
            style={textareaStyle}
          />

          {/* Submit button */}
          <button
            type="button"
            onClick={handleSubmit}
            disabled={submitting}
            style={{
              ...submitButtonStyle,
              opacity: submitting ? 0.6 : 1,
              cursor: submitting ? "wait" : "pointer",
            }}
          >
            {submitting ? "Submitting..." : "Submit Feedback"}
          </button>
        </div>
      )}
    </div>
  );
}

// ── Styles ──

function getFeedbackStyles(T) {
  const containerStyle = {
    background: T.card,
    border: `1px solid ${T.border}`,
    borderRadius: 12,
    padding: 20,
    backdropFilter: "blur(8px)",
  };

  const headingStyle = {
    display: "block",
    fontSize: 11,
    fontWeight: 600,
    color: T.textMuted,
    marginBottom: 12,
    letterSpacing: 1,
    textTransform: "uppercase",
    fontFamily: "'JetBrains Mono', monospace",
  };

  const textareaStyle = {
    width: "100%",
    padding: "10px 14px",
    background: "rgba(255,255,255,0.06)",
    border: "1px solid rgba(255,255,255,0.1)",
    borderRadius: 8,
    color: T.text,
    fontSize: 13,
    fontFamily: "'JetBrains Mono', monospace",
    outline: "none",
    boxSizing: "border-box",
    resize: "vertical",
    marginBottom: 10,
  };

  const submitButtonStyle = {
    padding: "7px 16px",
    background: T.accent,
    border: "none",
    borderRadius: 6,
    color: "#fff",
    fontSize: 12,
    fontWeight: 600,
    boxShadow: "0 0 14px rgba(249,115,22,0.25)",
  };

  const thankYouStyle = {
    display: "flex",
    alignItems: "center",
    gap: 10,
    fontSize: 14,
    fontWeight: 600,
    color: T.success,
    fontFamily: "'Inter', system-ui",
  };

  const checkIconStyle = {
    width: 24,
    height: 24,
    borderRadius: "50%",
    background: "rgba(34,197,94,0.15)",
    color: T.success,
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    fontSize: 13,
    fontWeight: 700,
  };

  return { containerStyle, headingStyle, textareaStyle, submitButtonStyle, thankYouStyle, checkIconStyle };
}

const ratingButtonBase = {
  display: "flex",
  alignItems: "center",
  gap: 8,
  padding: "8px 18px",
  borderRadius: 8,
  border: "1px solid",
  fontSize: 13,
  fontWeight: 600,
  cursor: "pointer",
  transition: "all 0.15s",
  background: "transparent",
};
