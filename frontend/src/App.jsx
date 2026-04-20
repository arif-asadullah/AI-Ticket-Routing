import { useState } from "react";
import DeskMindSplash from "./components/DeskMindSplash";
import DeskMindSpinner from "./components/DeskMindSpinner";

import logo from "./assets/logo/deskmind-logo.svg";
import logoDark from "./assets/logo/deskmind-logo-dark.svg";
import icon from "./assets/logo/deskmind-icon.svg";

export default function App() {
  const [splashDone, setSplashDone] = useState(false);
  const [isClassifying, setIsClassifying] = useState(false);
  const [result, setResult] = useState(null);

  const handleSubmit = async () => {
    setIsClassifying(true);
    setResult(null);

    await new Promise((r) => setTimeout(r, 3000));

    setResult({
      category: "Database",
      confidence: 0.93,
      resolution: "Check PostgreSQL max_connections setting on prod-db-01",
    });
    setIsClassifying(false);
  };

  return (
    <>
      {!splashDone && <DeskMindSplash onFinished={() => setSplashDone(true)} />}

      {splashDone && (
        <div style={{ minHeight: "100vh", background: "#FAFAF9" }}>

          <header style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            padding: "16px 32px",
            borderBottom: "1px solid #E7E5E4",
            background: "#fff"
          }}>
            <img src={logo} alt="DeskMind" style={{ height: 80 }} />

            <nav style={{ display: "flex", gap: 24, fontSize: 14, color: "#78716C" }}>
              <a href="#tickets" style={{ color: "#1C1917", fontWeight: 500 }}>Tickets</a>
              <a href="#dashboard" style={{ color: "#78716C" }}>Dashboard</a>
              <a href="#evaluation" style={{ color: "#78716C" }}>Evaluation</a>
            </nav>
          </header>

          <main style={{ maxWidth: 640, margin: "48px auto", padding: "0 24px" }}>
            <h1 style={{
              fontFamily: "Georgia, serif",
              fontSize: 28,
              fontWeight: 400,
              color: "#1C1917",
              marginBottom: 8
            }}>
              Submit a ticket
            </h1>
            <p style={{ color: "#78716C", fontSize: 14, marginBottom: 32 }}>
              Enter the ticket description and DeskMind will classify and route it.
            </p>

            <textarea
              placeholder="Describe the IT issue... (e.g., PostgreSQL not accepting connections on prod-db-01)"
              style={{
                width: "100%",
                minHeight: 120,
                padding: 16,
                borderRadius: 12,
                border: "1px solid #D6D3D1",
                fontSize: 14,
                fontFamily: "system-ui, sans-serif",
                resize: "vertical",
                outline: "none",
                boxSizing: "border-box"
              }}
            />

            <button
              onClick={handleSubmit}
              disabled={isClassifying}
              style={{
                marginTop: 16,
                padding: "12px 32px",
                background: isClassifying ? "#FED7AA" : "#F97316",
                color: "#fff",
                border: "none",
                borderRadius: 8,
                fontSize: 14,
                fontWeight: 500,
                cursor: isClassifying ? "wait" : "pointer",
                display: "flex",
                alignItems: "center",
                gap: 8
              }}
            >
              {isClassifying ? (
                <>
                  <DeskMindSpinner size="sm" />
                  Classifying...
                </>
              ) : (
                "Classify & Route"
              )}
            </button>

            {isClassifying && !result && (
              <div style={{
                marginTop: 48,
                textAlign: "center",
                padding: 48,
                background: "#fff",
                borderRadius: 16,
                border: "1px solid #E7E5E4"
              }}>
                <DeskMindSpinner size="lg" label="Analyzing ticket..." />
                <p style={{ marginTop: 16, color: "#78716C", fontSize: 14 }}>
                  Running classification and searching knowledge graph
                </p>
              </div>
            )}

            {result && (
              <div style={{
                marginTop: 32,
                padding: 24,
                background: "#fff",
                borderRadius: 16,
                border: "1px solid #E7E5E4"
              }}>
                <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 16 }}>
                  <img src={icon} alt="" style={{ width: 32, height: 32, borderRadius: 8 }} />
                  <div>
                    <h3 style={{ margin: 0, fontSize: 16, fontWeight: 500, color: "#1C1917" }}>Classification result</h3>
                    <p style={{ margin: 0, fontSize: 12, color: "#A8A29E" }}>via Phi-3 + ArangoDB GraphRAG</p>
                  </div>
                </div>

                <div style={{ display: "flex", gap: 16, marginBottom: 16 }}>
                  <div style={{
                    padding: "8px 16px",
                    background: "#FFF7ED",
                    borderRadius: 8,
                    fontSize: 14,
                    color: "#C2410C",
                    fontWeight: 500
                  }}>
                    {result.category}
                  </div>
                  <div style={{
                    padding: "8px 16px",
                    background: result.confidence > 0.8 ? "#F0FDF4" : "#FEF3C7",
                    borderRadius: 8,
                    fontSize: 14,
                    color: result.confidence > 0.8 ? "#166534" : "#92400E",
                    fontWeight: 500
                  }}>
                    {Math.round(result.confidence * 100)}% confidence
                  </div>
                </div>

                <div style={{
                  padding: 16,
                  background: "#FAFAF9",
                  borderRadius: 8,
                  fontSize: 14,
                  color: "#44403C",
                  lineHeight: 1.6
                }}>
                  <strong style={{ color: "#1C1917" }}>Suggested resolution:</strong>
                  <br />{result.resolution}
                </div>
              </div>
            )}
          </main>
        </div>
      )}
    </>
  );
}
