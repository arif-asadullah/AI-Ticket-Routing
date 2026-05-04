import { useState, useRef, useEffect } from "react";
import { sendChat } from "../services/api";
import DeskMindSpinner from "./DeskMindSpinner";

const T = {
  bg: "#0C0C0F",
  card: "rgba(255,255,255,0.04)",
  border: "rgba(255,255,255,0.08)",
  text: "#F5F5F4",
  textMuted: "#78716C",
  textDim: "#44403C",
  accent: "#F97316",
};

export default function ChatPanel() {
  const [messages, setMessages] = useState([
    { role: "assistant", content: "Hi! I'm DeskMind AI powered by Qwen 2.5:3B. Ask me anything about IT issues, or paste a ticket description and I'll classify it." },
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
      setMessages((prev) => [...prev, { role: "assistant", content: data.reply, model: data.model }]);
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
      height: "calc(100vh - 65px)",
      maxWidth: 860,
      margin: "0 auto",
      padding: "0 24px",
    }}>
      {/* Messages */}
      <div style={{
        flex: 1,
        overflowY: "auto",
        padding: "24px 0",
      }}>
        {messages.map((msg, i) => (
          <div
            key={i}
            style={{
              display: "flex",
              justifyContent: msg.role === "user" ? "flex-end" : "flex-start",
              marginBottom: 16,
            }}
          >
            <div style={{
              maxWidth: "75%",
              padding: "12px 16px",
              borderRadius: msg.role === "user" ? "16px 16px 4px 16px" : "16px 16px 16px 4px",
              background: msg.role === "user" ? T.accent : T.card,
              border: msg.role === "user" ? "none" : `1px solid ${T.border}`,
              color: T.text,
              fontSize: 14,
              lineHeight: 1.6,
              whiteSpace: "pre-wrap",
              wordBreak: "break-word",
            }}>
              {msg.content}
              {msg.model && (
                <div style={{
                  marginTop: 8,
                  fontSize: 10,
                  color: T.textDim,
                  fontFamily: "'JetBrains Mono', monospace",
                }}>
                  {msg.model}
                </div>
              )}
            </div>
          </div>
        ))}

        {loading && (
          <div style={{ display: "flex", justifyContent: "flex-start", marginBottom: 16 }}>
            <div style={{
              padding: "16px 24px",
              borderRadius: "16px 16px 16px 4px",
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
        gap: 12,
        padding: "16px 0 24px",
        borderTop: `1px solid ${T.border}`,
      }}>
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Type a message... (e.g., 'Classify: NGINX 502 errors after deployment')"
          disabled={loading}
          style={{
            flex: 1,
            padding: "12px 16px",
            borderRadius: 12,
            border: `1px solid ${T.border}`,
            background: "rgba(255,255,255,0.03)",
            color: T.text,
            fontSize: 14,
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
            padding: "12px 20px",
            borderRadius: 12,
            border: "none",
            background: input.trim() && !loading ? T.accent : "rgba(249,115,22,0.3)",
            color: "#fff",
            fontSize: 14,
            fontWeight: 600,
            cursor: input.trim() && !loading ? "pointer" : "not-allowed",
            display: "flex",
            alignItems: "center",
            gap: 6,
            boxShadow: input.trim() && !loading ? "0 0 15px rgba(249,115,22,0.25)" : "none",
            transition: "all 0.2s",
          }}
        >
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
            <path d="M14 2L7.5 14L5.5 8.5L2 7L14 2Z" stroke="#fff" strokeWidth="1.5" strokeLinejoin="round" />
          </svg>
          Send
        </button>
      </form>
    </div>
  );
}
