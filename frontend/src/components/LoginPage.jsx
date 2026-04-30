import { useState, useRef, useEffect } from "react";
import LoginBackground from "./LoginBackground";
import logoIcon from "../assets/logo/deskmind-icon.svg";
import logoLandscapeDark from "../assets/logo/deskmind-logo-landscape-dark.svg";
import DeskMindSpinner from "./DeskMindSpinner";

export default function LoginPage({ onLogin }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await onLogin(email, password);
    } catch (err) {
      setError(err.message || "Login failed");
    } finally {
      setLoading(false);
    }
  };

  // Mouse tracking for logo tilt — on the outer wrapper so it always works
  const [mousePos, setMousePos] = useState({ x: 0, y: 0 });

  return (
    <div
      onMouseMove={(e) => setMousePos({ x: e.clientX, y: e.clientY })}
      style={{
        minHeight: "100vh",
        color: "#F5F5F4",
        position: "relative",
        display: "flex",
      }}
    >
      <LoginBackground />

      {/* ── Left Side: Login Form — deep navy panel ── */}
      <div style={{
        position: "relative",
        zIndex: 2,
        width: "42%",
        minWidth: 380,
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        padding: "40px 48px",
        background: "linear-gradient(160deg, #0a0f1a 0%, #0d1117 40%, #101820 100%)",
        borderRight: "1px solid rgba(249,115,22,0.2)",
        boxShadow: "4px 0 40px rgba(0,0,0,0.6)",
      }}>
        <div style={{ width: "100%", maxWidth: 360 }}>
          {/* Welcome text */}
          <h2 style={{
            fontFamily: "'Inter', system-ui, sans-serif",
            fontSize: 24,
            fontWeight: 600,
            marginBottom: 6,
          }}>
            Welcome back
          </h2>
          <p style={{
            color: "#78716C",
            fontSize: 14,
            marginBottom: 32,
          }}>
            Sign in to access your dashboard
          </p>

          {/* Error */}
          {error && (
            <div style={{
              background: "rgba(239,68,68,0.1)",
              border: "1px solid rgba(239,68,68,0.3)",
              borderRadius: 8,
              padding: "10px 14px",
              marginBottom: 20,
              color: "#EF4444",
              fontSize: 13,
              textAlign: "center",
            }}>
              {error}
            </div>
          )}

          {/* Form */}
          <form onSubmit={handleSubmit}>
            <label style={labelStyle}>Email</label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@company.com"
              required
              style={inputStyle}
              onFocus={(e) => e.target.style.borderColor = "#F97316"}
              onBlur={(e) => e.target.style.borderColor = "rgba(255,255,255,0.1)"}
            />

            <label style={{ ...labelStyle, marginTop: 18 }}>Password</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Enter your password"
              required
              style={inputStyle}
              onFocus={(e) => e.target.style.borderColor = "#F97316"}
              onBlur={(e) => e.target.style.borderColor = "rgba(255,255,255,0.1)"}
            />

            <button
              type="submit"
              disabled={loading}
              style={{
                width: "100%",
                padding: "12px 0",
                marginTop: 28,
                background: loading ? "rgba(249,115,22,0.5)" : "linear-gradient(135deg, #F97316, #EA580C)",
                border: "none",
                borderRadius: 8,
                color: "#fff",
                fontSize: 15,
                fontWeight: 600,
                cursor: loading ? "wait" : "pointer",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                gap: 10,
                boxShadow: "0 0 20px rgba(249,115,22,0.3)",
              }}
            >
              {loading ? (
                <>
                  <DeskMindSpinner size="sm" />
                  Signing in...
                </>
              ) : (
                "Sign In"
              )}
            </button>
          </form>

          {/* Footer */}
          <p style={{
            textAlign: "center",
            color: "#44403C",
            fontSize: 11,
            marginTop: 40,
            letterSpacing: 2,
          }}>
            CLASSIFY &middot; ROUTE &middot; RESOLVE
          </p>
        </div>
      </div>

      {/* ── Center Logo Badge — Interactive ── */}
      <CenterLogoBadge mousePos={mousePos} />

      {/* ── Right Side: Product Showcase ── */}
      <div style={{
        position: "relative",
        zIndex: 2,
        flex: 1,
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        padding: "60px 48px",
        overflow: "auto",
      }}>
        {/* Logo */}
        <img
          src={logoLandscapeDark}
          alt="DeskMind"
          style={{
            height: 52,
            marginBottom: 32,
            filter: "drop-shadow(0 0 24px rgba(249,115,22,0.3))",
          }}
        />

        {/* Hero */}
        <h1 style={{
          fontFamily: "'Inter', system-ui, sans-serif",
          fontSize: "clamp(24px, 3vw, 40px)",
          fontWeight: 600,
          lineHeight: 1.2,
          maxWidth: 520,
          marginBottom: 16,
          textAlign: "center",
          background: "linear-gradient(135deg, #F5F5F4 0%, #A8A29E 100%)",
          WebkitBackgroundClip: "text",
          WebkitTextFillColor: "transparent",
        }}>
          AI-powered ticket routing that learns your infrastructure
        </h1>

        <p style={{
          fontSize: 15,
          color: "#78716C",
          maxWidth: 440,
          lineHeight: 1.6,
          marginBottom: 48,
          textAlign: "center",
        }}>
          Describe the issue. DeskMind classifies it using a knowledge graph and local LLM,
          then routes it to the right team — instantly.
        </p>

        {/* How It Works — 3 cards */}
        <div style={{
          display: "grid",
          gridTemplateColumns: "repeat(3, 1fr)",
          gap: 20,
          maxWidth: 640,
          width: "100%",
          marginBottom: 40,
        }}>
          {[
            {
              step: "01",
              title: "Submit",
              desc: "Describe the issue in plain text — natural language.",
              icon: (
                <svg width="28" height="28" viewBox="0 0 32 32" fill="none">
                  <rect x="4" y="6" width="24" height="20" rx="3" stroke="#F97316" strokeWidth="1.5" fill="none"/>
                  <line x1="10" y1="13" x2="22" y2="13" stroke="#F97316" strokeWidth="1.5" strokeLinecap="round" opacity="0.5"/>
                  <line x1="10" y1="17" x2="18" y2="17" stroke="#F97316" strokeWidth="1.5" strokeLinecap="round" opacity="0.5"/>
                  <line x1="10" y1="21" x2="20" y2="21" stroke="#F97316" strokeWidth="1.5" strokeLinecap="round" opacity="0.5"/>
                </svg>
              ),
            },
            {
              step: "02",
              title: "Classify",
              desc: "4-classifier ensemble with knowledge graph traversal.",
              icon: (
                <svg width="28" height="28" viewBox="0 0 32 32" fill="none">
                  <circle cx="16" cy="16" r="11" stroke="#F97316" strokeWidth="1.5" fill="none"/>
                  <circle cx="16" cy="12" r="2" fill="#F97316" opacity="0.7"/>
                  <circle cx="12" cy="20" r="2" fill="#EA580C" opacity="0.7"/>
                  <circle cx="20" cy="20" r="2" fill="#FB923C" opacity="0.7"/>
                  <line x1="16" y1="14" x2="13" y2="18" stroke="#F97316" strokeWidth="1" opacity="0.4"/>
                  <line x1="16" y1="14" x2="19" y2="18" stroke="#F97316" strokeWidth="1" opacity="0.4"/>
                </svg>
              ),
            },
            {
              step: "03",
              title: "Route",
              desc: "Auto-routed to the right team across 6 domains.",
              icon: (
                <svg width="28" height="28" viewBox="0 0 32 32" fill="none">
                  <circle cx="16" cy="8" r="3" fill="#F97316"/>
                  <line x1="16" y1="11" x2="16" y2="16" stroke="#F97316" strokeWidth="1.5" strokeLinecap="round"/>
                  <path d="M16 16 Q16 22 10 26" stroke="#EA580C" strokeWidth="1.5" strokeLinecap="round" fill="none"/>
                  <path d="M16 16 Q16 21 16 26" stroke="#F97316" strokeWidth="1.5" strokeLinecap="round" fill="none"/>
                  <path d="M16 16 Q16 22 22 26" stroke="#FB923C" strokeWidth="1.5" strokeLinecap="round" fill="none"/>
                  <circle cx="10" cy="27" r="2" fill="#EA580C"/>
                  <circle cx="16" cy="27" r="2" fill="#F97316"/>
                  <circle cx="22" cy="27" r="2" fill="#FB923C"/>
                </svg>
              ),
            },
          ].map(({ step, title, desc, icon }) => (
            <div key={step} style={{
              padding: 22,
              borderRadius: 14,
              background: "rgba(255,255,255,0.03)",
              border: "1px solid rgba(255,255,255,0.06)",
              backdropFilter: "blur(8px)",
              transition: "border-color 0.3s",
            }}
              onMouseEnter={(e) => e.currentTarget.style.borderColor = "rgba(249,115,22,0.25)"}
              onMouseLeave={(e) => e.currentTarget.style.borderColor = "rgba(255,255,255,0.06)"}
            >
              <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 12 }}>
                {icon}
                <span style={{
                  fontFamily: "'JetBrains Mono', monospace",
                  fontSize: 10,
                  color: "#F97316",
                  opacity: 0.6,
                }}>
                  {step}
                </span>
              </div>
              <h3 style={{
                fontFamily: "'Inter', system-ui",
                fontSize: 16,
                fontWeight: 600,
                marginBottom: 6,
                color: "#F5F5F4",
              }}>
                {title}
              </h3>
              <p style={{ fontSize: 12, color: "#78716C", lineHeight: 1.5 }}>
                {desc}
              </p>
            </div>
          ))}
        </div>

        {/* Status pills */}
        <div style={{
          display: "flex",
          gap: 12,
          flexWrap: "wrap",
          justifyContent: "center",
        }}>
          {["ArangoDB", "Redis", "Qwen 2.5 LLM", "MiniLM Embeddings"].map((label) => (
            <div key={label} style={{
              display: "flex",
              alignItems: "center",
              gap: 6,
              padding: "5px 12px",
              borderRadius: 20,
              background: "rgba(255,255,255,0.04)",
              border: "1px solid rgba(255,255,255,0.06)",
              fontSize: 11,
              color: "#78716C",
            }}>
              <span style={{
                width: 5,
                height: 5,
                borderRadius: "50%",
                background: "#22c55e",
                boxShadow: "0 0 6px rgba(34,197,94,0.5)",
              }} />
              {label}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// ── Interactive Center Logo ──

function CenterLogoBadge({ mousePos }) {
  const ref = useRef(null);

  // Compute tilt and glow from mouse position
  let rotateX = 0, rotateY = 0, scale = 1, glow = 0.15, borderAlpha = 0.35;

  if (ref.current && mousePos.x > 0) {
    const rect = ref.current.getBoundingClientRect();
    const cx = rect.left + rect.width / 2;
    const cy = rect.top + rect.height / 2;
    const dx = mousePos.x - cx;
    const dy = mousePos.y - cy;
    const dist = Math.sqrt(dx * dx + dy * dy);
    const falloff = Math.max(0, 1 - dist / 500);

    rotateX = (dy / 300) * 20 * falloff;
    rotateY = -(dx / 300) * 20 * falloff;
    scale = 1 + falloff * 0.15;
    glow = 0.15 + falloff * 0.45;
    borderAlpha = 0.35 + falloff * 0.5;
  }

  return (
    <>
      <style>{`
        @keyframes logoPulse {
          0%, 100% { transform: scale(1); opacity: 1; }
          50% { transform: scale(1.2); opacity: 0.3; }
        }
      `}</style>
      <div
        ref={ref}
        style={{
          position: "absolute",
          left: "calc(42% - 38px)",
          top: "50%",
          marginTop: -38,
          zIndex: 10,
          width: 76,
          height: 76,
          borderRadius: "50%",
          background: "radial-gradient(circle at 40% 35%, #1a1a2e, #0C0C0F)",
          border: `2px solid rgba(249,115,22,${borderAlpha})`,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          cursor: "pointer",
          transform: `perspective(800px) rotateX(${rotateX}deg) rotateY(${rotateY}deg) scale(${scale})`,
          transition: "box-shadow 0.2s",
          boxShadow: `0 0 ${20 + glow * 60}px rgba(249,115,22,${glow}), 0 0 80px rgba(0,0,0,0.4)`,
        }}
      >
        {/* Pulse rings */}
        <div style={{
          position: "absolute", inset: -8, borderRadius: "50%",
          border: `1px solid rgba(249,115,22,${0.1 + glow * 0.2})`,
          animation: "logoPulse 3s ease-in-out infinite", pointerEvents: "none",
        }} />
        <div style={{
          position: "absolute", inset: -18, borderRadius: "50%",
          border: `1px solid rgba(249,115,22,${0.05 + glow * 0.1})`,
          animation: "logoPulse 3s ease-in-out infinite 1s", pointerEvents: "none",
        }} />

        {/* Logo icon */}
        <img
          src={logoIcon}
          alt="DeskMind"
          style={{
            height: 38,
            filter: `drop-shadow(0 0 ${6 + glow * 20}px rgba(249,115,22,${0.3 + glow}))`,
          }}
        />
      </div>
    </>
  );
}

const labelStyle = {
  display: "block",
  fontSize: 13,
  color: "#A8A29E",
  marginBottom: 6,
  fontWeight: 500,
};

const inputStyle = {
  width: "100%",
  padding: "11px 14px",
  background: "rgba(255,255,255,0.06)",
  border: "1px solid rgba(255,255,255,0.1)",
  borderRadius: 8,
  color: "#F5F5F4",
  fontSize: 14,
  outline: "none",
  boxSizing: "border-box",
  transition: "border-color 0.2s",
};
