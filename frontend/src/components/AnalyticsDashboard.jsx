import { useState, useEffect } from "react";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, PieChart, Pie, Cell,
  AreaChart, Area, ReferenceLine, Legend,
} from "recharts";
import { fetchStats } from "../services/api";
import DeskMindSpinner from "./DeskMindSpinner";
import { useTheme } from "../theme/ThemeContext";

const CATEGORY_COLORS = {
  Infrastructure: "#3b82f6",
  Application: "#F97316",
  Database: "#22c55e",
  Network: "#8b5cf6",
  Security: "#ef4444",
  "Access Management": "#06b6d4",
};

const STATUS_COLORS = {
  routed: "#F97316",
  in_progress: "#3b82f6",
  escalated: "#ef4444",
  resolved: "#22c55e",
};

const PRIORITY_COLORS = {
  critical: "#ef4444",
  high: "#f59e0b",
  medium: "#3b82f6",
  low: "#22c55e",
};

// ── Shared styles ──
function getCardStyle(T) {
  return {
    background: T.card,
    border: `1px solid ${T.border}`,
    borderRadius: 16,
    padding: 24,
    backdropFilter: "blur(12px)",
  };
}

function getTitleStyle(T) {
  return {
    fontFamily: "'Inter', sans-serif",
    fontSize: 15,
    fontWeight: 600,
    color: T.text,
    marginBottom: 16,
    letterSpacing: 0.2,
  };
}

const dataFont = "'JetBrains Mono', monospace";

// ── Dark tooltip ──
function DarkTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  return (
    <div style={{
      background: "rgba(12,12,15,0.95)",
      border: "1px solid rgba(255,255,255,0.1)",
      borderRadius: 10,
      padding: "10px 14px",
      color: "#F5F5F4",
      fontSize: 12,
    }}>
      <div style={{ fontWeight: 600, marginBottom: 4 }}>{label}</div>
      {payload.map((p, i) => (
        <div key={i} style={{ color: p.color || "#F5F5F4" }}>
          {p.name}: {typeof p.value === "number" && p.value < 1
            ? `${(p.value * 100).toFixed(1)}%`
            : p.value}
        </div>
      ))}
    </div>
  );
}

// ── Custom pie label renderer ──
function makeRenderPercentLabel(T) {
  return function renderPercentLabel({ cx, cy, midAngle, innerRadius, outerRadius, percent }) {
    if (percent < 0.05) return null;
    const RADIAN = Math.PI / 180;
    const radius = outerRadius + 18;
    const x = cx + radius * Math.cos(-midAngle * RADIAN);
    const y = cy + radius * Math.sin(-midAngle * RADIAN);
    return (
      <text
        x={x}
        y={y}
        fill={T.text}
        textAnchor={x > cx ? "start" : "end"}
        dominantBaseline="central"
        style={{ fontSize: 11, fontFamily: dataFont }}
      >
        {`${(percent * 100).toFixed(0)}%`}
      </text>
    );
  };
}

// ── Custom bar label for horizontal bar chart ──
function makeRenderBarLabel(T) {
  return function renderBarLabel(props) {
    const { x, y, width, height, value } = props;
    return (
      <text
        x={x + width + 8}
        y={y + height / 2}
        fill={T.text}
        textAnchor="start"
        dominantBaseline="central"
        style={{ fontSize: 11, fontFamily: dataFont }}
      >
        {value}
      </text>
    );
  };
}

// ── Center text for donut charts ──
function CenterLabel({ cx, cy, text, sub }) {
  const { T } = useTheme();
  return (
    <g>
      <text
        x={cx}
        y={cy - 6}
        textAnchor="middle"
        dominantBaseline="central"
        style={{ fontSize: 22, fontWeight: 700, fill: T.text, fontFamily: dataFont }}
      >
        {text}
      </text>
      {sub && (
        <text
          x={cx}
          y={cy + 16}
          textAnchor="middle"
          dominantBaseline="central"
          style={{ fontSize: 10, fill: T.textMuted, fontFamily: dataFont }}
        >
          {sub}
        </text>
      )}
    </g>
  );
}

// ── Chart 1: Tickets by Category (horizontal bar) ──
function CategoryBarChart({ data }) {
  const { T } = useTheme();
  const cardStyle = getCardStyle(T);
  const titleStyle = getTitleStyle(T);
  const renderBarLabel = makeRenderBarLabel(T);
  return (
    <div style={{ ...cardStyle, gridColumn: "1 / -1" }}>
      <div style={titleStyle}>Tickets by Category</div>
      <ResponsiveContainer width="100%" height={280}>
        <BarChart data={data} layout="vertical" margin={{ left: 20, right: 40, top: 5, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" horizontal={false} />
          <XAxis type="number" tick={{ fill: T.textMuted, fontSize: 11, fontFamily: dataFont }} axisLine={false} tickLine={false} />
          <YAxis
            type="category"
            dataKey="category"
            tick={{ fill: T.text, fontSize: 12, fontFamily: "'Inter', sans-serif" }}
            axisLine={false}
            tickLine={false}
            width={130}
          />
          <Tooltip content={<DarkTooltip />} cursor={{ fill: "rgba(255,255,255,0.03)" }} />
          <Bar dataKey="count" name="Tickets" radius={[0, 6, 6, 0]} label={renderBarLabel}>
            {data.map((entry, i) => (
              <Cell key={i} fill={CATEGORY_COLORS[entry.category] || T.accent} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

// ── Chart 2: Status Distribution (donut) ──
function StatusPieChart({ data, total }) {
  const { T } = useTheme();
  const cardStyle = getCardStyle(T);
  const titleStyle = getTitleStyle(T);
  const renderPercentLabel = makeRenderPercentLabel(T);
  return (
    <div style={cardStyle}>
      <div style={titleStyle}>Status Distribution</div>
      <ResponsiveContainer width="100%" height={280}>
        <PieChart>
          <Pie
            data={data}
            dataKey="count"
            nameKey="status"
            cx="50%"
            cy="50%"
            innerRadius={60}
            outerRadius={90}
            paddingAngle={3}
            label={renderPercentLabel}
            labelLine={false}
          >
            {data.map((entry, i) => (
              <Cell key={i} fill={STATUS_COLORS[entry.status] || T.textMuted} stroke="none" />
            ))}
          </Pie>
          <Tooltip content={<DarkTooltip />} />
          <Legend
            formatter={(value) => <span style={{ color: T.text, fontSize: 11, fontFamily: dataFont }}>{value}</span>}
            iconType="circle"
            iconSize={8}
          />
          {/* Center text rendered via customized label */}
          <Pie
            data={[{ value: 1 }]}
            dataKey="value"
            cx="50%"
            cy="50%"
            innerRadius={0}
            outerRadius={0}
            fill="none"
            isAnimationActive={false}
          >
            <Cell fill="none" />
          </Pie>
          {/* We use a custom active shape workaround — render center text via SVG */}
          <text
            x="50%"
            y="44%"
            textAnchor="middle"
            dominantBaseline="central"
            style={{ fontSize: 22, fontWeight: 700, fill: T.text, fontFamily: dataFont }}
          >
            {total ?? 0}
          </text>
          <text
            x="50%"
            y="52%"
            textAnchor="middle"
            dominantBaseline="central"
            style={{ fontSize: 10, fill: T.textMuted, fontFamily: dataFont }}
          >
            total
          </text>
        </PieChart>
      </ResponsiveContainer>
    </div>
  );
}

// ── Chart 3: Priority Distribution (donut) ──
function PriorityPieChart({ data }) {
  const { T } = useTheme();
  const cardStyle = getCardStyle(T);
  const titleStyle = getTitleStyle(T);
  const renderPercentLabel = makeRenderPercentLabel(T);
  const total = data.reduce((sum, d) => sum + d.count, 0);
  return (
    <div style={cardStyle}>
      <div style={titleStyle}>Priority Distribution</div>
      <ResponsiveContainer width="100%" height={280}>
        <PieChart>
          <Pie
            data={data}
            dataKey="count"
            nameKey="priority"
            cx="50%"
            cy="50%"
            innerRadius={60}
            outerRadius={90}
            paddingAngle={3}
            label={renderPercentLabel}
            labelLine={false}
          >
            {data.map((entry, i) => (
              <Cell key={i} fill={PRIORITY_COLORS[entry.priority] || T.textMuted} stroke="none" />
            ))}
          </Pie>
          <Tooltip content={<DarkTooltip />} />
          <Legend
            formatter={(value) => <span style={{ color: T.text, fontSize: 11, fontFamily: dataFont }}>{value}</span>}
            iconType="circle"
            iconSize={8}
          />
          <text
            x="50%"
            y="44%"
            textAnchor="middle"
            dominantBaseline="central"
            style={{ fontSize: 22, fontWeight: 700, fill: T.text, fontFamily: dataFont }}
          >
            {total ?? 0}
          </text>
          <text
            x="50%"
            y="52%"
            textAnchor="middle"
            dominantBaseline="central"
            style={{ fontSize: 10, fill: T.textMuted, fontFamily: dataFont }}
          >
            total
          </text>
        </PieChart>
      </ResponsiveContainer>
    </div>
  );
}

// ── Chart 4: Daily Ticket Volume (area) ──
function DailyTrendChart({ data }) {
  const { T } = useTheme();
  const cardStyle = getCardStyle(T);
  const titleStyle = getTitleStyle(T);
  return (
    <div style={{ ...cardStyle, gridColumn: "1 / -1" }}>
      <div style={titleStyle}>Daily Ticket Volume</div>
      <ResponsiveContainer width="100%" height={280}>
        <AreaChart data={data} margin={{ left: 0, right: 20, top: 5, bottom: 5 }}>
          <defs>
            <linearGradient id="areaGradient" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#F97316" stopOpacity={0.3} />
              <stop offset="100%" stopColor="#F97316" stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
          <XAxis
            dataKey="date"
            tick={{ fill: T.textMuted, fontSize: 11, fontFamily: dataFont }}
            axisLine={false}
            tickLine={false}
            tickFormatter={(d) => {
              const dt = new Date(d);
              return `${dt.getMonth() + 1}/${dt.getDate()}`;
            }}
          />
          <YAxis
            tick={{ fill: T.textMuted, fontSize: 11, fontFamily: dataFont }}
            axisLine={false}
            tickLine={false}
            allowDecimals={false}
          />
          <Tooltip content={<DarkTooltip />} />
          <Area
            type="monotone"
            dataKey="count"
            name="Tickets"
            stroke="#F97316"
            strokeWidth={2}
            fill="url(#areaGradient)"
            dot={false}
            activeDot={{ r: 4, fill: "#F97316", stroke: T.bg, strokeWidth: 2 }}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}

// ── Chart 5: Confidence by Category (vertical bar) ──
function ConfidenceBarChart({ data }) {
  const { T } = useTheme();
  const cardStyle = getCardStyle(T);
  const titleStyle = getTitleStyle(T);
  return (
    <div style={cardStyle}>
      <div style={titleStyle}>Confidence by Category</div>
      <ResponsiveContainer width="100%" height={280}>
        <BarChart data={data} margin={{ left: 0, right: 10, top: 5, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" vertical={false} />
          <XAxis
            dataKey="category"
            tick={{ fill: T.textMuted, fontSize: 10, fontFamily: "'Inter', sans-serif" }}
            axisLine={false}
            tickLine={false}
            interval={0}
            angle={-25}
            textAnchor="end"
            height={50}
          />
          <YAxis
            domain={[0, 1]}
            tick={{ fill: T.textMuted, fontSize: 11, fontFamily: dataFont }}
            axisLine={false}
            tickLine={false}
            tickFormatter={(v) => `${(v * 100).toFixed(0)}%`}
          />
          <Tooltip content={<DarkTooltip />} cursor={{ fill: "rgba(255,255,255,0.03)" }} />
          <ReferenceLine
            y={0.70}
            stroke="#ef4444"
            strokeDasharray="6 4"
            label={{
              value: "Auto-route threshold",
              position: "right",
              fill: "#ef4444",
              fontSize: 10,
              fontFamily: dataFont,
            }}
          />
          <Bar dataKey="avg_confidence" name="Confidence" radius={[4, 4, 0, 0]}>
            {data.map((entry, i) => (
              <Cell key={i} fill={CATEGORY_COLORS[entry.category] || T.accent} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

// ── Chart 6: AI Feedback (donut) ──
function FeedbackPieChart({ feedback }) {
  const { T } = useTheme();
  const cardStyle = getCardStyle(T);
  const titleStyle = getTitleStyle(T);
  const renderPercentLabel = makeRenderPercentLabel(T);
  const data = [
    { name: "Helpful", value: feedback?.helpful || 0 },
    { name: "Not Helpful", value: feedback?.not_helpful || 0 },
  ];
  const COLORS = ["#22c55e", "#ef4444"];
  const total = data[0].value + data[1].value;
  const helpfulPct = total > 0 ? Math.round((data[0].value / total) * 100) : 0;

  return (
    <div style={cardStyle}>
      <div style={titleStyle}>AI Feedback</div>
      <ResponsiveContainer width="100%" height={280}>
        <PieChart>
          <Pie
            data={data}
            dataKey="value"
            nameKey="name"
            cx="50%"
            cy="50%"
            innerRadius={60}
            outerRadius={90}
            paddingAngle={3}
            label={renderPercentLabel}
            labelLine={false}
          >
            {data.map((_, i) => (
              <Cell key={i} fill={COLORS[i]} stroke="none" />
            ))}
          </Pie>
          <Tooltip content={<DarkTooltip />} />
          <Legend
            formatter={(value) => <span style={{ color: T.text, fontSize: 11, fontFamily: dataFont }}>{value}</span>}
            iconType="circle"
            iconSize={8}
          />
          <text
            x="50%"
            y="44%"
            textAnchor="middle"
            dominantBaseline="central"
            style={{ fontSize: 22, fontWeight: 700, fill: "#22c55e", fontFamily: dataFont }}
          >
            {helpfulPct}%
          </text>
          <text
            x="50%"
            y="52%"
            textAnchor="middle"
            dominantBaseline="central"
            style={{ fontSize: 10, fill: T.textMuted, fontFamily: dataFont }}
          >
            helpful
          </text>
        </PieChart>
      </ResponsiveContainer>
    </div>
  );
}

// ── Main component ──
export default function AnalyticsDashboard({ user }) {
  const { T } = useTheme();
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    fetchStats()
      .then((data) => {
        if (!cancelled) {
          setStats(data);
          setError(null);
        }
      })
      .catch((err) => {
        if (!cancelled) setError(err.message);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => { cancelled = true; };
  }, []);

  if (loading) {
    return (
      <div style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        minHeight: 400,
        background: T.bg,
      }}>
        <DeskMindSpinner size="lg" label="Loading analytics..." />
      </div>
    );
  }

  if (error) {
    return (
      <div style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        minHeight: 400,
        background: T.bg,
        color: "#ef4444",
        fontFamily: "'Inter', sans-serif",
        fontSize: 14,
      }}>
        Failed to load analytics: {error}
      </div>
    );
  }

  if (!stats || stats.total === 0) {
    return (
      <div style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        minHeight: 400,
        background: T.bg,
        gap: 12,
      }}>
        <svg width="48" height="48" viewBox="0 0 48 48" fill="none">
          <rect x="4" y="8" width="40" height="32" rx="6" stroke={T.textMuted} strokeWidth="1.5" />
          <line x1="12" y1="20" x2="36" y2="20" stroke={T.textMuted} strokeWidth="1" strokeLinecap="round" opacity="0.4" />
          <line x1="12" y1="26" x2="28" y2="26" stroke={T.textMuted} strokeWidth="1" strokeLinecap="round" opacity="0.4" />
          <line x1="12" y1="32" x2="20" y2="32" stroke={T.textMuted} strokeWidth="1" strokeLinecap="round" opacity="0.4" />
        </svg>
        <span style={{
          fontFamily: "'Inter', sans-serif",
          fontSize: 14,
          color: T.textMuted,
        }}>
          No data yet
        </span>
        <span style={{
          fontFamily: "'Inter', sans-serif",
          fontSize: 12,
          color: T.textMuted,
          opacity: 0.6,
        }}>
          Analytics will appear once tickets are created.
        </span>
      </div>
    );
  }

  return (
    <div style={{
      background: T.bg,
      minHeight: "100vh",
      padding: "32px 24px",
    }}>
      <div style={{
        maxWidth: 1100,
        margin: "0 auto",
      }}>
        {/* Header */}
        <div style={{ marginBottom: 28 }}>
          <h1 style={{
            fontFamily: "'Inter', sans-serif",
            fontSize: 24,
            fontWeight: 700,
            color: T.text,
            margin: 0,
            letterSpacing: -0.3,
          }}>
            Analytics
          </h1>
          <p style={{
            fontFamily: "'Inter', sans-serif",
            fontSize: 13,
            color: T.textMuted,
            margin: "6px 0 0",
          }}>
            {stats.total_all != null
              ? `${stats.total_all.toLocaleString()} tickets analyzed`
              : "Overview of ticket routing performance"}
          </p>
        </div>

        {/* Chart grid */}
        <div style={{
          display: "grid",
          gridTemplateColumns: "1fr 1fr",
          gap: 24,
        }}>
          {/* 1. Tickets by Category — full width */}
          {stats.by_category?.length > 0 && (
            <CategoryBarChart data={stats.by_category} />
          )}

          {/* 2. Status Distribution — left */}
          {stats.by_status?.length > 0 && (
            <StatusPieChart data={stats.by_status} total={stats.total} />
          )}

          {/* 3. Priority Distribution — right */}
          {stats.by_priority?.length > 0 && (
            <PriorityPieChart data={stats.by_priority} />
          )}

          {/* 4. Daily Ticket Volume — full width */}
          {stats.daily_trend?.length > 0 && (
            <DailyTrendChart data={stats.daily_trend} />
          )}

          {/* 5. Confidence by Category — left */}
          {stats.confidence_by_category?.length > 0 && (
            <ConfidenceBarChart data={stats.confidence_by_category} />
          )}

          {/* 6. AI Feedback — right */}
          {stats.feedback && (
            <FeedbackPieChart feedback={stats.feedback} />
          )}
        </div>
      </div>
    </div>
  );
}
