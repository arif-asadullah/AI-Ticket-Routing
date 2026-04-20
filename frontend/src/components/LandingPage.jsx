import AnimatedBackground from "./AnimatedBackground";
import logoLandscapeDark from "../assets/logo/deskmind-logo-landscape-dark.svg";

export default function LandingPage({ onEnter, health, ticketCount }) {
  return (
    <div style={{
      minHeight: "100vh",
      background: "#0C0C0F",
      color: "#F5F5F4",
      position: "relative",
      overflow: "hidden",
    }}>
      <AnimatedBackground />

      {/* ── Hero ── */}
      <section style={{
        position: "relative",
        zIndex: 1,
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        minHeight: "100vh",
        padding: "0 24px",
        textAlign: "center",
      }}>
        <img
          src={logoLandscapeDark}
          alt="DeskMind"
          style={{
            height: 64,
            marginBottom: 32,
            filter: "drop-shadow(0 0 30px rgba(249,115,22,0.3))",
          }}
        />

        <h1 style={{
          fontFamily: "'Inter', system-ui, sans-serif",
          fontSize: "clamp(28px, 5vw, 48px)",
          fontWeight: 600,
          lineHeight: 1.2,
          maxWidth: 640,
          marginBottom: 16,
          background: "linear-gradient(135deg, #F5F5F4 0%, #A8A29E 100%)",
          WebkitBackgroundClip: "text",
          WebkitTextFillColor: "transparent",
        }}>
          AI-powered ticket routing that learns your infrastructure
        </h1>

        <p style={{
          fontSize: 16,
          color: "#78716C",
          maxWidth: 480,
          lineHeight: 1.6,
          marginBottom: 40,
        }}>
          Describe the issue. DeskMind classifies it using a knowledge graph and local LLM,
          then routes it to the right team — instantly.
        </p>

        <button
          onClick={onEnter}
          style={{
            padding: "14px 40px",
            fontSize: 15,
            fontWeight: 600,
            color: "#fff",
            background: "#F97316",
            border: "none",
            borderRadius: 12,
            cursor: "pointer",
            display: "flex",
            alignItems: "center",
            gap: 8,
            boxShadow: "0 0 30px rgba(249,115,22,0.35), 0 4px 16px rgba(0,0,0,0.3)",
            transition: "transform 0.2s, box-shadow 0.2s",
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.transform = "translateY(-2px)";
            e.currentTarget.style.boxShadow = "0 0 50px rgba(249,115,22,0.5), 0 8px 24px rgba(0,0,0,0.4)";
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.transform = "translateY(0)";
            e.currentTarget.style.boxShadow = "0 0 30px rgba(249,115,22,0.35), 0 4px 16px rgba(0,0,0,0.3)";
          }}
        >
          Raise Ticket
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
            <path d="M3 8h10M9 4l4 4-4 4" stroke="#fff" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
        </button>

        {/* Status pills */}
        <div style={{
          display: "flex",
          gap: 12,
          marginTop: 32,
          flexWrap: "wrap",
          justifyContent: "center",
        }}>
          {[
            { label: "ArangoDB", ok: health?.arango === "connected" },
            { label: "Redis", ok: health?.redis === "connected" },
            { label: "Phi-3 LLM", ok: true },
          ].map(({ label, ok }) => (
            <div key={label} style={{
              display: "flex",
              alignItems: "center",
              gap: 6,
              padding: "6px 14px",
              borderRadius: 20,
              background: "rgba(255,255,255,0.05)",
              border: "1px solid rgba(255,255,255,0.08)",
              fontSize: 12,
              color: "#78716C",
            }}>
              <span style={{
                width: 6,
                height: 6,
                borderRadius: "50%",
                background: ok ? "#22c55e" : "#ef4444",
                boxShadow: ok ? "0 0 8px rgba(34,197,94,0.6)" : "0 0 8px rgba(239,68,68,0.6)",
              }} />
              {label}
            </div>
          ))}
        </div>
      </section>

      {/* ── How It Works ── */}
      <section style={{
        position: "relative",
        zIndex: 1,
        padding: "80px 24px",
        maxWidth: 900,
        margin: "0 auto",
      }}>
        <h2 style={{
          fontFamily: "'Inter', system-ui",
          fontSize: 13,
          fontWeight: 600,
          textTransform: "uppercase",
          letterSpacing: 3,
          color: "#F97316",
          textAlign: "center",
          marginBottom: 48,
        }}>
          How it works
        </h2>

        <div style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))",
          gap: 24,
        }}>
          {[
            {
              step: "01",
              title: "Submit",
              desc: "Describe the issue in plain text — no forms, no dropdowns, just natural language.",
              icon: (
                <svg width="32" height="32" viewBox="0 0 32 32" fill="none">
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
              desc: "AI analyzes using knowledge graph traversal and local LLM inference — no data leaves your network.",
              icon: (
                <svg width="32" height="32" viewBox="0 0 32 32" fill="none">
                  <circle cx="16" cy="16" r="11" stroke="#F97316" strokeWidth="1.5" fill="none"/>
                  <circle cx="16" cy="12" r="2" fill="#F97316" opacity="0.7"/>
                  <circle cx="12" cy="20" r="2" fill="#EA580C" opacity="0.7"/>
                  <circle cx="20" cy="20" r="2" fill="#FB923C" opacity="0.7"/>
                  <line x1="16" y1="14" x2="13" y2="18" stroke="#F97316" strokeWidth="1" opacity="0.4"/>
                  <line x1="16" y1="14" x2="19" y2="18" stroke="#F97316" strokeWidth="1" opacity="0.4"/>
                  <line x1="14" y1="20" x2="18" y2="20" stroke="#F97316" strokeWidth="1" opacity="0.4"/>
                </svg>
              ),
            },
            {
              step: "03",
              title: "Route",
              desc: "Ticket is automatically sent to the right team — Infrastructure, Networking, Security, Database, or App Support.",
              icon: (
                <svg width="32" height="32" viewBox="0 0 32 32" fill="none">
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
              padding: 28,
              borderRadius: 16,
              background: "rgba(255,255,255,0.03)",
              border: "1px solid rgba(255,255,255,0.06)",
              backdropFilter: "blur(8px)",
              transition: "border-color 0.3s, background 0.3s",
            }}
              onMouseEnter={(e) => {
                e.currentTarget.style.borderColor = "rgba(249,115,22,0.25)";
                e.currentTarget.style.background = "rgba(255,255,255,0.05)";
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.borderColor = "rgba(255,255,255,0.06)";
                e.currentTarget.style.background = "rgba(255,255,255,0.03)";
              }}
            >
              <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 16 }}>
                {icon}
                <span style={{
                  fontFamily: "'JetBrains Mono', monospace",
                  fontSize: 11,
                  color: "#F97316",
                  opacity: 0.6,
                }}>
                  {step}
                </span>
              </div>
              <h3 style={{
                fontFamily: "'Inter', system-ui",
                fontSize: 18,
                fontWeight: 600,
                marginBottom: 8,
                color: "#F5F5F4",
              }}>
                {title}
              </h3>
              <p style={{ fontSize: 13, color: "#78716C", lineHeight: 1.6 }}>
                {desc}
              </p>
            </div>
          ))}
        </div>
      </section>

      {/* ── Stats Bar ── */}
      <section style={{
        position: "relative",
        zIndex: 1,
        padding: "0 24px 40px",
        maxWidth: 700,
        margin: "0 auto",
      }}>
        <div style={{
          display: "flex",
          justifyContent: "center",
          gap: 32,
          padding: "20px 32px",
          borderRadius: 16,
          background: "rgba(255,255,255,0.03)",
          border: "1px solid rgba(255,255,255,0.06)",
          flexWrap: "wrap",
        }}>
          {[
            { value: ticketCount, label: "Tickets routed" },
            { value: "5", label: "Teams" },
            { value: "3", label: "AI Services" },
          ].map(({ value, label }) => (
            <div key={label} style={{ textAlign: "center", minWidth: 100 }}>
              <div style={{
                fontFamily: "'JetBrains Mono', monospace",
                fontSize: 24,
                fontWeight: 700,
                color: "#F97316",
              }}>
                {value}
              </div>
              <div style={{ fontSize: 11, color: "#78716C", marginTop: 2 }}>
                {label}
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* ── CTA Footer ── */}
      <section style={{
        position: "relative",
        zIndex: 1,
        textAlign: "center",
        padding: "60px 24px 80px",
      }}>
        <p style={{ fontSize: 22, fontFamily: "Georgia, serif", color: "#78716C", marginBottom: 24 }}>
          Ready to route smarter?
        </p>
        <button
          onClick={onEnter}
          style={{
            padding: "12px 32px",
            fontSize: 14,
            fontWeight: 600,
            color: "#F97316",
            background: "transparent",
            border: "1px solid rgba(249,115,22,0.4)",
            borderRadius: 10,
            cursor: "pointer",
            transition: "all 0.2s",
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.background = "rgba(249,115,22,0.1)";
            e.currentTarget.style.borderColor = "#F97316";
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.background = "transparent";
            e.currentTarget.style.borderColor = "rgba(249,115,22,0.4)";
          }}
        >
          Raise Ticket →
        </button>
      </section>
    </div>
  );
}
