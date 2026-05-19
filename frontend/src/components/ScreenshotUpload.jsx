import { useRef } from "react";
import { useTheme } from "../theme/ThemeContext";
import DeskMindSpinner from "./DeskMindSpinner";

export default function ScreenshotUpload({ attachments, onUpload, onRemove, error }) {
  const { T } = useTheme();
  const inputRef = useRef(null);

  function handleFiles(files) {
    const validFiles = Array.from(files).filter(
      (f) => f.type.startsWith("image/") && f.size <= 5 * 1024 * 1024
    );
    if (validFiles.length > 0) onUpload(validFiles);
  }

  return (
    <div style={{ marginBottom: 16 }}>
      <label
        style={{
          display: "block", fontSize: 12, fontWeight: 500,
          color: T.textMuted, marginBottom: 8,
        }}
      >
        Screenshots (optional)
      </label>

      {/* Drop zone */}
      <div
        onClick={() => inputRef.current?.click()}
        onDragOver={(e) => { e.preventDefault(); e.currentTarget.style.borderColor = T.accent; }}
        onDragLeave={(e) => { e.currentTarget.style.borderColor = T.border; }}
        onDrop={(e) => { e.preventDefault(); e.currentTarget.style.borderColor = T.border; handleFiles(e.dataTransfer.files); }}
        style={{
          border: `2px dashed ${T.border}`,
          borderRadius: 12,
          padding: attachments.length > 0 ? "12px" : "24px 16px",
          textAlign: "center",
          cursor: "pointer",
          transition: "border-color 0.2s",
          background: T.card,
        }}
      >
        <input
          ref={inputRef}
          type="file"
          accept="image/*"
          multiple
          onChange={(e) => handleFiles(e.target.files)}
          style={{ display: "none" }}
        />

        {attachments.length === 0 ? (
          <div>
            <svg width="28" height="28" viewBox="0 0 28 28" fill="none" style={{ marginBottom: 6, opacity: 0.4 }}>
              <rect x="3" y="5" width="22" height="18" rx="3" stroke={T.textMuted} strokeWidth="1.5" />
              <circle cx="10" cy="13" r="2.5" stroke={T.textMuted} strokeWidth="1.2" />
              <path d="M3 19l5-4 4 3 6-5 7 6" stroke={T.textMuted} strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
            <p style={{ margin: 0, fontSize: 12, color: T.textDim }}>
              Drop screenshots here or click to upload
            </p>
            <p style={{ margin: "4px 0 0", fontSize: 10, color: T.textDim, opacity: 0.6 }}>
              PNG, JPG, GIF, WEBP (max 5MB each)
            </p>
          </div>
        ) : (
          /* Thumbnail grid */
          <div style={{ display: "flex", gap: 10, flexWrap: "wrap", justifyContent: "flex-start" }}>
            {attachments.map((att, i) => (
              <div key={i} style={{ position: "relative" }}>
                <div style={{
                  width: 80, height: 80, borderRadius: 8, overflow: "hidden",
                  border: `1px solid ${T.border}`,
                  position: "relative",
                }}>
                  <img
                    src={att.preview}
                    alt=""
                    style={{ width: "100%", height: "100%", objectFit: "cover" }}
                  />
                  {att.uploading && (
                    <div style={{
                      position: "absolute", inset: 0,
                      background: "rgba(0,0,0,0.5)",
                      display: "flex", alignItems: "center", justifyContent: "center",
                    }}>
                      <DeskMindSpinner size="sm" />
                    </div>
                  )}
                  {!att.uploading && att.ocr_result && (
                    <div style={{
                      position: "absolute", bottom: 0, left: 0, right: 0,
                      background: "rgba(34,197,94,0.9)",
                      padding: "2px 4px",
                      fontSize: 8, fontWeight: 700, color: "#fff",
                      textAlign: "center", textTransform: "uppercase",
                      letterSpacing: 0.5,
                    }}>
                      {att.ocr_result.screenshot_type_label || "Analyzed"}
                    </div>
                  )}
                </div>
                {/* Remove button */}
                <button
                  onClick={(e) => { e.stopPropagation(); onRemove(i); }}
                  style={{
                    position: "absolute", top: -6, right: -6,
                    width: 18, height: 18, borderRadius: "50%",
                    background: T.danger, color: "#fff", border: "none",
                    fontSize: 10, cursor: "pointer",
                    display: "flex", alignItems: "center", justifyContent: "center",
                    lineHeight: 1,
                  }}
                >
                  &times;
                </button>
              </div>
            ))}
            {/* Add more button */}
            {attachments.length < 5 && (
              <div style={{
                width: 80, height: 80, borderRadius: 8,
                border: `2px dashed ${T.border}`,
                display: "flex", alignItems: "center", justifyContent: "center",
                fontSize: 24, color: T.textDim, cursor: "pointer",
              }}>
                +
              </div>
            )}
          </div>
        )}
      </div>

      {/* OCR preview for completed uploads */}
      {attachments.filter((a) => !a.uploading && a.ocr_result?.raw_text).map((att, i) => (
        <div key={i} style={{
          marginTop: 8, padding: "10px 14px",
          background: "rgba(34,197,94,0.04)",
          border: "1px solid rgba(34,197,94,0.15)",
          borderRadius: 8, fontSize: 12,
        }}>
          <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 6 }}>
            <span style={{
              padding: "2px 8px", borderRadius: 4, fontSize: 9, fontWeight: 700,
              background: "rgba(34,197,94,0.12)", color: T.success,
              textTransform: "uppercase", letterSpacing: 0.5,
              fontFamily: "'JetBrains Mono', monospace",
            }}>
              {att.ocr_result.screenshot_type_label}
            </span>
            <span style={{ color: T.textDim, fontSize: 10 }}>
              {Math.round(att.ocr_result.confidence * 100)}% OCR confidence
            </span>
          </div>
          <div style={{
            color: T.text, fontSize: 11, lineHeight: 1.5,
            maxHeight: 60, overflow: "hidden",
            fontFamily: "'JetBrains Mono', monospace",
          }}>
            {att.ocr_result.raw_text.slice(0, 200)}{att.ocr_result.raw_text.length > 200 ? "..." : ""}
          </div>
          {/* Entity chips */}
          {(att.ocr_result.entities.servers.length > 0 || att.ocr_result.entities.error_codes.length > 0) && (
            <div style={{ display: "flex", gap: 4, flexWrap: "wrap", marginTop: 6 }}>
              {att.ocr_result.entities.servers.map((s) => (
                <span key={s} style={{
                  padding: "2px 8px", borderRadius: 10, fontSize: 10, fontWeight: 600,
                  background: "rgba(59,130,246,0.1)", color: "#3b82f6",
                }}>
                  {s}
                </span>
              ))}
              {att.ocr_result.entities.services.map((s) => (
                <span key={s} style={{
                  padding: "2px 8px", borderRadius: 10, fontSize: 10, fontWeight: 600,
                  background: "rgba(249,115,22,0.1)", color: T.accent,
                }}>
                  {s}
                </span>
              ))}
              {att.ocr_result.entities.error_codes.map((e, j) => (
                <span key={j} style={{
                  padding: "2px 8px", borderRadius: 10, fontSize: 10, fontWeight: 600,
                  background: "rgba(239,68,68,0.1)", color: T.danger,
                }}>
                  {e}
                </span>
              ))}
            </div>
          )}
        </div>
      ))}

      {/* Error */}
      {error && (
        <div style={{
          marginTop: 6, fontSize: 11, color: T.danger,
          padding: "4px 8px", background: "rgba(239,68,68,0.06)", borderRadius: 6,
        }}>
          {error}
        </div>
      )}
    </div>
  );
}
