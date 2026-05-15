import { useState, useRef, useEffect } from "react";
import { sendChat } from "../services/api";
import DeskMindSpinner from "./DeskMindSpinner";
import RichMessage from "./RichMessage";

const T = {
  bg: "#0C0C0F",
  card: "rgba(255,255,255,0.04)",
  border: "rgba(255,255,255,0.08)",
  text: "#F5F5F4",
  textMuted: "#78716C",
  textDim: "#44403C",
  accent: "#F97316",
};

export default function ChatPanel({ onClose, compact }) {
  const [messages, setMessages] = useState([
    { role: "assistant", content: "Hi! I'm Mindy, your DeskMind AI assistant. Ask me about tickets, teams, or IT issues.\n\nTry: \"status of ticket #206129\" or \"which team handles database?\"" },
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const bottomRef = useRef(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  async function handleSend(e) {
    e.preventDefault();
    if (!input.trim() || loading) return;

    const userMsg = input.trim();
    setInput("");
    setMessages((prev) => [...prev, { role: "user", content: userMsg }]);
    setLoading(true);

    try {
      const history = messages.map(({ role, content }) => ({ role, content }));
      const data = await sendChat(userMsg, history);
      setMessages((prev) => [...prev, {
        role: "assistant",
        content: data.reply,
        model: data.model,
        entities: data.entities || null,
      }]);
    } catch {
      setMessages((prev) => [...prev, { role: "assistant", content: "Error: Could not reach the AI. Is Ollama running?" }]);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div style={{
      display: "flex",
      flexDirection: "column",
      height: compact ? "100%" : "calc(100vh - 65px)",
      maxWidth: compact ? "none" : 860,
      margin: compact ? 0 : "0 auto",
      padding: compact ? 0 : "0 24px",
    }}>
      {/* Header (compact mode) */}
      {compact && (
        <div style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "12px 16px",
          borderBottom: `1px solid ${T.border}`,
          background: "rgba(255,255,255,0.02)",
        }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <div style={{
              width: 8, height: 8, borderRadius: "50%",
              background: T.accent,
              boxShadow: `0 0 8px ${T.accent}`,
            }} />
            <span style={{ fontSize: 13, fontWeight: 600, color: T.text, fontFamily: "'Inter', system-ui" }}>
              Mindy
            </span>
            <span style={{ fontSize: 10, color: T.textDim, fontFamily: "'JetBrains Mono', monospace" }}>
              grounded
            </span>
          </div>
          {onClose && (
            <button
              onClick={onClose}
              style={{ background: "none", border: "none", color: T.textMuted, cursor: "pointer", fontSize: 16, padding: 4 }}
            >
              ✕
            </button>
          )}
        </div>
      )}

      {/* Messages */}
      <div style={{
        flex: 1,
        overflowY: "auto",
        padding: compact ? "12px 14px" : "24px 0",
      }}>
        {messages.map((msg, i) => (
          <div
            key={i}
            style={{
              display: "flex",
              justifyContent: msg.role === "user" ? "flex-end" : "flex-start",
              marginBottom: 12,
            }}
          >
            <div style={{
              maxWidth: compact ? "85%" : "75%",
              padding: "10px 14px",
              borderRadius: msg.role === "user" ? "14px 14px 4px 14px" : "14px 14px 14px 4px",
              background: msg.role === "user" ? T.accent : T.card,
              border: msg.role === "user" ? "none" : `1px solid ${T.border}`,
              color: T.text,
              fontSize: 13,
              lineHeight: 1.6,
            }}>
              {msg.role === "assistant" ? (
                <RichMessage content={msg.content} entities={msg.entities} />
              ) : (
                <span style={{ whiteSpace: "pre-wrap", wordBreak: "break-word" }}>{msg.content}</span>
              )}
              {msg.model && (
                <div style={{
                  marginTop: 6,
                  fontSize: 9,
                  color: T.textDim,
                  fontFamily: "'JetBrains Mono', monospace",
                  display: "flex",
                  alignItems: "center",
                  gap: 4,
                }}>
                  <span style={{
                    width: 5, height: 5, borderRadius: "50%",
                    background: msg.model === "database" ? "#3b82f6" : T.accent,
                  }} />
                  {msg.model === "database" ? "direct lookup" : msg.model}
                </div>
              )}
            </div>
          </div>
        ))}

        {loading && (
          <div style={{ display: "flex", justifyContent: "flex-start", marginBottom: 12 }}>
            <div style={{
              padding: "12px 20px",
              borderRadius: "14px 14px 14px 4px",
              background: T.card,
              border: `1px solid ${T.border}`,
            }}>
              <DeskMindSpinner size="sm" label="Thinking..." />
            </div>
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <form onSubmit={handleSend} style={{
        display: "flex",
        gap: 8,
        padding: compact ? "10px 14px" : "16px 0 24px",
        borderTop: `1px solid ${T.border}`,
      }}>
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask about tickets, teams, status..."
          disabled={loading}
          style={{
            flex: 1,
            padding: "10px 14px",
            borderRadius: 10,
            border: `1px solid ${T.border}`,
            background: "rgba(255,255,255,0.03)",
            color: T.text,
            fontSize: 13,
            fontFamily: "'Inter', system-ui",
            outline: "none",
            transition: "border-color 0.2s",
          }}
          onFocus={(e) => e.target.style.borderColor = "rgba(249,115,22,0.3)"}
          onBlur={(e) => e.target.style.borderColor = T.border}
        />
        <button
          type="submit"
          disabled={loading || !input.trim()}
          style={{
            padding: "10px 16px",
            borderRadius: 10,
            border: "none",
            background: input.trim() && !loading ? T.accent : "rgba(249,115,22,0.3)",
            color: "#fff",
            fontSize: 13,
            fontWeight: 600,
            cursor: input.trim() && !loading ? "pointer" : "not-allowed",
            display: "flex",
            alignItems: "center",
            gap: 5,
            boxShadow: input.trim() && !loading ? "0 0 12px rgba(249,115,22,0.25)" : "none",
          }}
        >
          <svg width="14" height="14" viewBox="0 0 16 16" fill="none">
            <path d="M14 2L7.5 14L5.5 8.5L2 7L14 2Z" stroke="#fff" strokeWidth="1.5" strokeLinejoin="round" />
          </svg>
        </button>
      </form>
    </div>
  );
}
