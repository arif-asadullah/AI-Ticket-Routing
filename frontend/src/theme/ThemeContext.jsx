import { createContext, useContext, useState, useEffect } from "react";

const DARK = {
  bg: "#0C0C0F",
  bgAlt: "#111114",
  card: "rgba(255,255,255,0.04)",
  cardHover: "rgba(255,255,255,0.07)",
  border: "rgba(255,255,255,0.08)",
  borderGlow: "rgba(249,115,22,0.3)",
  cardShadow: "none",
  text: "#F5F5F4",
  textMuted: "#78716C",
  textDim: "#44403C",
  accent: "#F97316",
  accentGlow: "rgba(249,115,22,0.15)",
  success: "#22c55e",
  warning: "#f59e0b",
  danger: "#ef4444",
  blue: "#3b82f6",
  purple: "#8b5cf6",
  // Graph-specific
  graphBg: "#f5f5f4",
  graphText: "rgba(0,0,0,0.75)",
  graphTextDim: "rgba(0,0,0,0.15)",
  graphOverlay: "rgba(255,255,255,0.97)",
  graphOverlayText: "#1a1a1a",
  graphOverlayMuted: "#888",
  graphOverlayBorder: "rgba(0,0,0,0.1)",
  graphOverlayShadow: "0 8px 32px rgba(0,0,0,0.12)",
  // Input
  inputBg: "rgba(255,255,255,0.06)",
  inputBorder: "rgba(255,255,255,0.1)",
};

const LIGHT = {
  bg: "#f8f8fa",
  bgAlt: "#ffffff",
  card: "#ffffff",
  cardHover: "#f5f5f5",
  border: "rgba(0,0,0,0.12)",
  borderGlow: "rgba(234,88,12,0.25)",
  cardShadow: "0 1px 3px rgba(0,0,0,0.08), 0 1px 2px rgba(0,0,0,0.06)",
  text: "#1a1a1a",
  textMuted: "#6b7280",
  textDim: "#9ca3af",
  accent: "#ea580c",
  accentGlow: "rgba(234,88,12,0.1)",
  success: "#16a34a",
  warning: "#d97706",
  danger: "#dc2626",
  blue: "#2563eb",
  purple: "#7c3aed",
  // Graph-specific (same — graph is always light bg)
  graphBg: "#f5f5f4",
  graphText: "rgba(0,0,0,0.75)",
  graphTextDim: "rgba(0,0,0,0.15)",
  graphOverlay: "rgba(255,255,255,0.97)",
  graphOverlayText: "#1a1a1a",
  graphOverlayMuted: "#888",
  graphOverlayBorder: "rgba(0,0,0,0.1)",
  graphOverlayShadow: "0 8px 32px rgba(0,0,0,0.12)",
  // Input
  inputBg: "rgba(0,0,0,0.03)",
  inputBorder: "rgba(0,0,0,0.12)",
};

const ThemeContext = createContext({ T: DARK, mode: "dark", toggleTheme: () => {} });

export function ThemeProvider({ children }) {
  const [mode, setMode] = useState(() => localStorage.getItem("deskmind-theme") || "light");

  useEffect(() => {
    localStorage.setItem("deskmind-theme", mode);
    document.body.style.background = mode === "dark" ? DARK.bg : LIGHT.bg;
    document.body.style.color = mode === "dark" ? DARK.text : LIGHT.text;
  }, [mode]);

  const toggleTheme = () => setMode((m) => (m === "dark" ? "light" : "dark"));
  const T = mode === "dark" ? DARK : LIGHT;

  return (
    <ThemeContext.Provider value={{ T, mode, toggleTheme }}>
      {children}
    </ThemeContext.Provider>
  );
}

export function useTheme() {
  return useContext(ThemeContext);
}
