const sizes = {
  sm: 0.5,
  md: 0.75,
  lg: 1,
};

const DeskMindSpinner = ({ size = "md", label = "" }) => {
  const scale = sizes[size] || sizes.md;
  const svgSize = Math.round(80 * scale);

  return (
    <div style={{ display: "inline-flex", flexDirection: "column", alignItems: "center", gap: 8 }}>
      <style>{`
        @keyframes dmPulseTop { 0%,100% { opacity:.4; transform:scale(.8) } 50% { opacity:1; transform:scale(1) } }
        @keyframes dmFlowStem { 0% { stroke-dashoffset:24; opacity:.3 } 50% { stroke-dashoffset:0; opacity:1 } 100% { stroke-dashoffset:-24; opacity:.3 } }
        @keyframes dmFlowBranch { 0% { stroke-dashoffset:30; opacity:.2 } 50% { stroke-dashoffset:0; opacity:1 } 100% { stroke-dashoffset:-30; opacity:.2 } }
        @keyframes dmPulseEnd1 { 0%,20% { opacity:.2; transform:scale(.7) } 50%,70% { opacity:1; transform:scale(1.1) } 100% { opacity:.2; transform:scale(.7) } }
        @keyframes dmPulseEnd2 { 0%,25% { opacity:.2; transform:scale(.7) } 55%,75% { opacity:1; transform:scale(1.1) } 100% { opacity:.2; transform:scale(.7) } }
        @keyframes dmPulseEnd3 { 0%,30% { opacity:.2; transform:scale(.7) } 60%,80% { opacity:1; transform:scale(1.1) } 100% { opacity:.2; transform:scale(.7) } }
        .dms-top { transform-origin:center; animation: dmPulseTop 1.6s ease-in-out infinite }
        .dms-stem { stroke-dasharray:12 12; animation: dmFlowStem 1.6s ease-in-out infinite }
        .dms-bl { stroke-dasharray:15 15; animation: dmFlowBranch 1.6s ease-in-out infinite .15s }
        .dms-bc { stroke-dasharray:12 12; animation: dmFlowBranch 1.6s ease-in-out infinite .2s }
        .dms-br { stroke-dasharray:15 15; animation: dmFlowBranch 1.6s ease-in-out infinite .25s }
        .dms-el { transform-origin:center; animation: dmPulseEnd1 1.6s ease-in-out infinite }
        .dms-ec { transform-origin:center; animation: dmPulseEnd2 1.6s ease-in-out infinite }
        .dms-er { transform-origin:center; animation: dmPulseEnd3 1.6s ease-in-out infinite }
      `}</style>

      <svg width={svgSize} height={svgSize} viewBox="0 0 80 80">
        <circle className="dms-top" cx="40" cy="12" r="6" fill="#F97316" />
        <line className="dms-stem" x1="40" y1="18" x2="40" y2="38" stroke="#F97316" strokeWidth="2.5" strokeLinecap="round" />
        <path className="dms-bl" d="M40 38 Q40 52 24 60" fill="none" stroke="#EA580C" strokeWidth="2" strokeLinecap="round" />
        <path className="dms-bc" d="M40 38 Q40 50 40 60" fill="none" stroke="#F97316" strokeWidth="2" strokeLinecap="round" />
        <path className="dms-br" d="M40 38 Q40 52 56 60" fill="none" stroke="#FB923C" strokeWidth="2" strokeLinecap="round" />
        <circle className="dms-el" cx="24" cy="64" r="5" fill="#EA580C" />
        <circle className="dms-ec" cx="40" cy="64" r="5" fill="#F97316" />
        <circle className="dms-er" cx="56" cy="64" r="5" fill="#FB923C" />
      </svg>

      {label && (
        <span style={{
          fontFamily: "system-ui, sans-serif",
          fontSize: size === "sm" ? 10 : size === "md" ? 12 : 14,
          color: "#A8A29E",
          letterSpacing: 1
        }}>
          {label}
        </span>
      )}
    </div>
  );
};

export default DeskMindSpinner;
