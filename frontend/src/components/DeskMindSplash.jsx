import { useEffect } from "react";

const DeskMindSplash = ({ onFinished, duration = 3200 }) => {
  useEffect(() => {
    const timer = setTimeout(() => {
      if (onFinished) onFinished();
    }, duration);
    return () => clearTimeout(timer);
  }, [duration, onFinished]);

  return (
    <>
      <style>{`
        @keyframes dotPulse {
          0% { transform: scale(0); opacity: 0 }
          60% { transform: scale(1.2); opacity: 1 }
          100% { transform: scale(1); opacity: 1 }
        }
        @keyframes lineGrow {
          0% { stroke-dashoffset: 40; opacity: 0 }
          30% { opacity: 1 }
          100% { stroke-dashoffset: 0; opacity: 1 }
        }
        @keyframes branchGrow {
          0% { stroke-dashoffset: 50; opacity: 0 }
          30% { opacity: 1 }
          100% { stroke-dashoffset: 0; opacity: 1 }
        }
        @keyframes endDot {
          0% { transform: scale(0); opacity: 0 }
          70% { transform: scale(1.3) }
          100% { transform: scale(1); opacity: 1 }
        }
        @keyframes textReveal {
          0% { opacity: 0; transform: translateY(12px) }
          100% { opacity: 1; transform: translateY(0) }
        }
        @keyframes tagReveal {
          0% { opacity: 0; letter-spacing: 12px }
          100% { opacity: 1; letter-spacing: 3px }
        }
        @keyframes splashOut {
          0% { opacity: 1; transform: scale(1) }
          100% { opacity: 0; transform: scale(0.95) }
        }
        .dm-splash {
          position: fixed; inset: 0; z-index: 9999;
          display: flex; align-items: center; justify-content: center; flex-direction: column;
          background: #0C0C0F;
          animation: splashOut 0.5s ease-in 2.7s forwards;
        }
        .dm-splash .top { transform-origin: center; transform: scale(0); animation: dotPulse 0.5s cubic-bezier(0.34,1.56,0.64,1) 0.1s forwards }
        .dm-splash .stem { stroke-dasharray: 40; stroke-dashoffset: 40; opacity: 0; animation: lineGrow 0.5s ease-out 0.4s forwards }
        .dm-splash .bl { stroke-dasharray: 50; stroke-dashoffset: 50; opacity: 0; animation: branchGrow 0.5s ease-out 0.8s forwards }
        .dm-splash .bc { stroke-dasharray: 40; stroke-dashoffset: 40; opacity: 0; animation: branchGrow 0.4s ease-out 0.9s forwards }
        .dm-splash .br { stroke-dasharray: 50; stroke-dashoffset: 50; opacity: 0; animation: branchGrow 0.5s ease-out 1.0s forwards }
        .dm-splash .el { transform-origin: center; transform: scale(0); opacity: 0; animation: endDot 0.4s cubic-bezier(0.34,1.56,0.64,1) 1.2s forwards }
        .dm-splash .ec { transform-origin: center; transform: scale(0); opacity: 0; animation: endDot 0.4s cubic-bezier(0.34,1.56,0.64,1) 1.35s forwards }
        .dm-splash .er { transform-origin: center; transform: scale(0); opacity: 0; animation: endDot 0.4s cubic-bezier(0.34,1.56,0.64,1) 1.5s forwards }
        .dm-splash .wordmark { opacity: 0; animation: textReveal 0.6s ease-out 1.7s forwards }
        .dm-splash .tagline { opacity: 0; animation: tagReveal 0.8s ease-out 2.0s forwards }
      `}</style>

      <div className="dm-splash">
        <svg width="240" height="180" viewBox="0 0 240 180">
          <circle className="top" cx="120" cy="30" r="12" fill="#F97316" />
          <line className="stem" x1="120" y1="42" x2="120" y2="76" stroke="#F97316" strokeWidth="3" strokeLinecap="round" />
          <path className="bl" d="M120 76 Q120 100 88 116" fill="none" stroke="#EA580C" strokeWidth="2.5" strokeLinecap="round" />
          <path className="bc" d="M120 76 Q120 96 120 116" fill="none" stroke="#F97316" strokeWidth="2.5" strokeLinecap="round" />
          <path className="br" d="M120 76 Q120 100 152 116" fill="none" stroke="#FB923C" strokeWidth="2.5" strokeLinecap="round" />
          <circle className="el" cx="88" cy="122" r="8" fill="#EA580C" />
          <circle className="ec" cx="120" cy="122" r="8" fill="#F97316" />
          <circle className="er" cx="152" cy="122" r="8" fill="#FB923C" />
          <text className="wordmark" x="120" y="162" textAnchor="middle" fontFamily="Georgia, 'Times New Roman', serif" fontSize="28" fontWeight="400" fill="#F5F5F4" letterSpacing="1">DeskMind</text>
        </svg>
        <p className="tagline" style={{ marginTop: 4, fontFamily: "system-ui, sans-serif", fontSize: 11, color: "#A8A29E", letterSpacing: 3 }}>
          CLASSIFY · ROUTE · RESOLVE
        </p>
      </div>
    </>
  );
};

export default DeskMindSplash;
