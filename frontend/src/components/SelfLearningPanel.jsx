import { useState, useEffect, useCallback } from "react";
import {
  fetchCorrectionStats,
  fetchRepeatedIssues,
  recomputeCentroids,
  detectRepeatedIssues,
} from "../services/api";
import { useTheme } from "../theme/ThemeContext";

const ACCENT = "#F97316";
const dataFont = "'JetBrains Mono', monospace";
const uiFont = "'Inter', sans-serif";

const CLASSIFIER_LABELS = {
  llm: "LLM",
  centroid: "Centroid",
  knn: "KNN",
  keyword: "Keyword",
};

/**
 * Self-Learning panel — surfaces the correction-feedback loop that's otherwise
 * API-only: how many corrections the system has learned from, which classifiers
 * are wrong most often, the most common misclassifications it has been taught to
 * fix, and recurring-issue clusters. Admins can trigger a centroid recompute or
 * a repeated-issue scan.
 */
export default function SelfLearningPanel({ user }) {
  const { T } = useTheme();
  const [stats, setStats] = useState(null);
  const [repeated, setRepeated] = useState([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(null); // 'recompute' | 'detect' | null
  const [msg, setMsg] = useState(null);

  const isAdmin = user?.role === "admin";

  const load = useCallback(() => {
    setLoading(true);
    Promise.all([
      fetchCorrectionStats().catch(() => null),
      fetchRepeatedIssues().catch(() => []),
    ])
      .then(([s, r]) => {
        setStats(s);
        setRepeated(Array.isArray(r) ? r : []);
      })
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => { load(); }, [load]);

  async function runAction(kind) {
    setBusy(kind);
    setMsg(null);
    try {
      if (kind === "recompute") {
        await recomputeCentroids();
        setMsg("Centroids recomputed from the latest corrections.");
      } else {
        const res = await detectRepeatedIssues();
        const n = res?.clusters_found ?? res?.clusters?.length ?? "0";
        setMsg(`Repeated-issue scan complete — ${n} cluster(s) found.`);
      }
      load();
    } catch (err) {
      setMsg(`Failed: ${err.message}`);
    } finally {
      setBusy(null);
    }
  }

  const cardStyle = {
    background: T.card,
    border: `1px solid ${T.border}`,
    borderRadius: 16,
    padding: 24,
    backdropFilter: "blur(12px)",
    gridColumn: "1 / -1", // full width in the dashboard grid
  };

  const total = stats?.total_corrections ?? 0;
  const trusted = stats?.trusted_corrections ?? 0;
  const overrideRate = stats?.override_rate ?? 0;
  const classifierErrors = stats?.classifier_errors ?? [];
  const misclass = stats?.common_misclassifications ?? [];
  const maxErr = Math.max(1, ...classifierErrors.map((c) => c.wrong_count || 0));

  return (
    <div style={cardStyle}>
      {/* Header */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 4, flexWrap: "wrap", gap: 12 }}>
        <div>
          <h3 style={{ fontFamily: uiFont, fontSize: 15, fontWeight: 600, color: T.text, margin: 0, letterSpacing: 0.2 }}>
            🧠 Self-Learning
          </h3>
          <p style={{ fontFamily: uiFont, fontSize: 12, color: T.textMuted, margin: "4px 0 0" }}>
            How the system improves from human corrections & feedback
          </p>
        </div>
        {isAdmin && (
          <div style={{ display: "flex", gap: 8 }}>
            <button onClick={() => runAction("recompute")} disabled={busy} style={btnStyle(T, busy === "recompute")}>
              {busy === "recompute" ? "Recomputing…" : "Recompute centroids"}
            </button>
            <button onClick={() => runAction("detect")} disabled={busy} style={btnStyle(T, busy === "detect")}>
              {busy === "detect" ? "Scanning…" : "Detect repeated issues"}
            </button>
          </div>
        )}
      </div>

      {msg && (
        <div style={{ fontFamily: uiFont, fontSize: 12, color: ACCENT, margin: "8px 0 0" }}>{msg}</div>
      )}

      {loading ? (
        <div style={{ fontFamily: uiFont, fontSize: 13, color: T.textMuted, padding: "24px 0" }}>Loading…</div>
      ) : total === 0 ? (
        <div style={{ fontFamily: uiFont, fontSize: 13, color: T.textMuted, padding: "20px 0" }}>
          No corrections recorded yet. As engineers override classifications, the system learns —
          near-identical future tickets are routed the corrected way automatically.
        </div>
      ) : (
        <>
          {/* Stat tiles */}
          <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 12, margin: "18px 0" }}>
            <Tile T={T} label="Corrections learned" value={total} />
            <Tile T={T} label="Trusted" value={trusted} />
            <Tile T={T} label="Override rate" value={`${(overrideRate * 100).toFixed(1)}%`} />
            <Tile T={T} label="Recurring clusters" value={repeated.length} />
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 24 }}>
            {/* Classifier error rates */}
            <div>
              <div style={subTitle(T)}>Which model is corrected most</div>
              {classifierErrors.length === 0 ? (
                <Empty T={T} />
              ) : (
                classifierErrors.map((c) => (
                  <div key={c.classifier} style={{ marginBottom: 10 }}>
                    <div style={{ display: "flex", justifyContent: "space-between", fontFamily: uiFont, fontSize: 12, color: T.text, marginBottom: 4 }}>
                      <span>{CLASSIFIER_LABELS[c.classifier] || c.classifier}</span>
                      <span style={{ fontFamily: dataFont, color: T.textMuted }}>{c.wrong_count}</span>
                    </div>
                    <div style={{ height: 6, background: T.border, borderRadius: 4, overflow: "hidden" }}>
                      <div style={{ width: `${((c.wrong_count || 0) / maxErr) * 100}%`, height: "100%", background: ACCENT, borderRadius: 4 }} />
                    </div>
                  </div>
                ))
              )}
            </div>

            {/* Top misclassifications */}
            <div>
              <div style={subTitle(T)}>Most common corrections</div>
              {misclass.length === 0 ? (
                <Empty T={T} />
              ) : (
                misclass.slice(0, 6).map((m, i) => (
                  <div key={i} style={{ display: "flex", alignItems: "center", justifyContent: "space-between", fontFamily: uiFont, fontSize: 12, color: T.text, padding: "5px 0" }}>
                    <span style={{ display: "flex", alignItems: "center", gap: 6 }}>
                      <span style={{ color: T.textMuted }}>{m.from}</span>
                      <span style={{ color: ACCENT }}>→</span>
                      <span>{m.to}</span>
                    </span>
                    <span style={{ fontFamily: dataFont, color: T.textMuted }}>×{m.count}</span>
                  </div>
                ))
              )}
            </div>
          </div>

          {/* Recurring issue clusters */}
          {repeated.length > 0 && (
            <div style={{ marginTop: 20 }}>
              <div style={subTitle(T)}>Recurring issues detected</div>
              {repeated.slice(0, 5).map((c, i) => (
                <div key={i} style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "8px 12px", background: T.bg, border: `1px solid ${T.border}`, borderRadius: 8, marginBottom: 8 }}>
                  <span style={{ fontFamily: uiFont, fontSize: 12, color: T.text }}>
                    {c.representative_title || c.category || "Cluster"}
                  </span>
                  <span style={{ display: "flex", gap: 8, alignItems: "center" }}>
                    {c.category && <Pill T={T} text={c.category} />}
                    <span style={{ fontFamily: dataFont, fontSize: 11, color: ACCENT }}>seen {c.count}×</span>
                  </span>
                </div>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}

function Tile({ T, label, value }) {
  return (
    <div style={{ background: T.bg, border: `1px solid ${T.border}`, borderRadius: 12, padding: "14px 16px" }}>
      <div style={{ fontFamily: dataFont, fontSize: 22, fontWeight: 700, color: T.text }}>{value}</div>
      <div style={{ fontFamily: uiFont, fontSize: 11, color: T.textMuted, marginTop: 2 }}>{label}</div>
    </div>
  );
}

function Pill({ T, text }) {
  return (
    <span style={{ fontFamily: uiFont, fontSize: 10, color: T.textMuted, background: T.border, borderRadius: 6, padding: "2px 7px" }}>{text}</span>
  );
}

function Empty({ T }) {
  return <div style={{ fontFamily: uiFont, fontSize: 12, color: T.textMuted, opacity: 0.7, padding: "6px 0" }}>—</div>;
}

function subTitle(T) {
  return { fontFamily: uiFont, fontSize: 12, fontWeight: 600, color: T.textMuted, textTransform: "uppercase", letterSpacing: 0.4, marginBottom: 12 };
}

function btnStyle(T, active) {
  return {
    fontFamily: uiFont,
    fontSize: 12,
    fontWeight: 500,
    color: active ? "#fff" : T.text,
    background: active ? ACCENT : T.bg,
    border: `1px solid ${active ? ACCENT : T.border}`,
    borderRadius: 8,
    padding: "7px 12px",
    cursor: active ? "default" : "pointer",
  };
}
