import { useState, useEffect, useRef, useCallback } from "react";
import ForceGraph2D from "react-force-graph-2d";
import { fetchGraph } from "../services/api";
import DeskMindSpinner from "./DeskMindSpinner";
import { useTheme } from "../theme/ThemeContext";

const NODE_COLORS = {
  team: "#3b82f6",
  engineer: "#22c55e",
  server: "#F97316",
  service: "#8b5cf6",
  ticket: "#f59e0b",
  error_code: "#ef4444",
  network_device: "#06b6d4",
};

const NODE_LABELS = {
  team: "Teams",
  engineer: "Engineers",
  server: "Servers",
  service: "Services",
  ticket: "Tickets",
  error_code: "Error Codes",
  network_device: "Network Devices",
};

const NODE_SIZES = {
  team: 12,
  engineer: 8,
  server: 9,
  service: 8,
  ticket: 7,
  error_code: 6,
  network_device: 7,
};

const EDGE_COLORS = {
  hosts: "#F97316",
  managed_by: "#3b82f6",
  depends_on: "#8b5cf6",
  member_of: "#22c55e",
  affects: "#f59e0b",
  assigned_to: "#3b82f6",
  resolved_with: "#22c55e",
  triggered_by: "#ef4444",
};

const CATEGORIES = ["All", "Infrastructure", "Application", "Database", "Network", "Security", "Access Management"];

export default function GraphVisualization({ user }) {
  const { T } = useTheme();
  const [graphData, setGraphData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [category, setCategory] = useState("All");
  const [hoveredNode, setHoveredNode] = useState(null);
  const [selectedNode, setSelectedNode] = useState(null);
  const [dimensions, setDimensions] = useState({ width: 800, height: 600 });
  const [isFullscreen, setIsFullscreen] = useState(false);
  // Node type filter: all visible by default
  const [visibleTypes, setVisibleTypes] = useState(new Set(Object.keys(NODE_COLORS)));
  const containerRef = useRef(null);
  const graphRef = useRef(null);
  const graphWrapRef = useRef(null);

  // Resize
  useEffect(() => {
    function updateSize() {
      if (isFullscreen) {
        setDimensions({ width: window.innerWidth, height: window.innerHeight });
      } else if (containerRef.current) {
        setDimensions({
          width: containerRef.current.offsetWidth,
          height: window.innerHeight - 180,
        });
      }
    }
    updateSize();
    window.addEventListener("resize", updateSize);
    return () => window.removeEventListener("resize", updateSize);
  }, [isFullscreen]);

  // Zoom controls
  function handleZoomIn() {
    if (graphRef.current) {
      const currentZoom = graphRef.current.zoom();
      graphRef.current.zoom(currentZoom * 1.4, 300);
    }
  }
  function handleZoomOut() {
    if (graphRef.current) {
      const currentZoom = graphRef.current.zoom();
      graphRef.current.zoom(currentZoom / 1.4, 300);
    }
  }
  function handleZoomFit() {
    if (graphRef.current) {
      graphRef.current.zoomToFit(400, 40);
    }
  }
  function toggleFullscreen() {
    setIsFullscreen((v) => !v);
  }

  // Fetch
  useEffect(() => {
    setLoading(true);
    setSelectedNode(null);
    const cat = category === "All" ? null : category;
    fetchGraph(cat)
      .then(setGraphData)
      .catch(() => setGraphData({ nodes: [], edges: [] }))
      .finally(() => setLoading(false));
  }, [category]);

  // Toggle node type visibility
  function toggleType(type) {
    setVisibleTypes((prev) => {
      const next = new Set(prev);
      if (next.has(type)) next.delete(type);
      else next.add(type);
      return next;
    });
  }

  // Show only one type + its connections
  function isolateType(type) {
    if (visibleTypes.size === 1 && visibleTypes.has(type)) {
      // Already isolated — show all
      setVisibleTypes(new Set(Object.keys(NODE_COLORS)));
    } else {
      // Find connected types
      const connectedTypes = new Set([type]);
      if (graphData) {
        const typeNodes = new Set(graphData.nodes.filter((n) => n.type === type).map((n) => n.id));
        for (const e of graphData.edges) {
          const src = e.source?.id || e.source;
          const tgt = e.target?.id || e.target;
          if (typeNodes.has(src)) {
            const targetNode = graphData.nodes.find((n) => n.id === tgt);
            if (targetNode) connectedTypes.add(targetNode.type);
          }
          if (typeNodes.has(tgt)) {
            const sourceNode = graphData.nodes.find((n) => n.id === src);
            if (sourceNode) connectedTypes.add(sourceNode.type);
          }
        }
      }
      setVisibleTypes(connectedTypes);
    }
  }

  // Filter data by visible types
  const filteredData = graphData ? {
    nodes: graphData.nodes.filter((n) => visibleTypes.has(n.type)),
    links: graphData.edges
      .map((e) => ({ source: e.source, target: e.target, type: e.type }))
      .filter((e) => {
        const srcId = e.source?.id || e.source;
        const tgtId = e.target?.id || e.target;
        const srcNode = graphData.nodes.find((n) => n.id === srcId);
        const tgtNode = graphData.nodes.find((n) => n.id === tgtId);
        return srcNode && tgtNode && visibleTypes.has(srcNode.type) && visibleTypes.has(tgtNode.type);
      }),
  } : { nodes: [], links: [] };

  // Node paint
  const paintNode = useCallback((node, ctx, globalScale) => {
    const size = NODE_SIZES[node.type] || 6;
    const color = NODE_COLORS[node.type] || "#888";
    const isHovered = hoveredNode?.id === node.id;
    const isSelected = selectedNode?.id === node.id;
    const isConnected = hoveredNode && (
      filteredData.links.some((e) =>
        ((e.source?.id || e.source) === hoveredNode.id && (e.target?.id || e.target) === node.id) ||
        ((e.target?.id || e.target) === hoveredNode.id && (e.source?.id || e.source) === node.id)
      )
    );
    const dimmed = hoveredNode && !isHovered && !isConnected;

    // Outer glow
    if (isHovered || isSelected) {
      ctx.beginPath();
      ctx.arc(node.x, node.y, size + 8, 0, 2 * Math.PI);
      ctx.fillStyle = `${color}40`;
      ctx.fill();
    }

    // Drop shadow
    ctx.shadowColor = dimmed ? "transparent" : `${color}60`;
    ctx.shadowBlur = dimmed ? 0 : 8;

    // Node
    ctx.beginPath();
    ctx.arc(node.x, node.y, size, 0, 2 * Math.PI);
    ctx.fillStyle = dimmed ? `${color}25` : color;
    ctx.fill();

    // Reset shadow
    ctx.shadowBlur = 0;

    // Border
    if (isHovered || isSelected) {
      ctx.strokeStyle = "#fff";
      ctx.lineWidth = 2.5;
      ctx.stroke();
      ctx.strokeStyle = `${color}90`;
      ctx.lineWidth = 1;
      ctx.stroke();
    } else {
      ctx.strokeStyle = dimmed ? `${color}20` : `${color}50`;
      ctx.lineWidth = 1;
      ctx.stroke();
    }

    // Label
    const showLabel = globalScale > 0.8 || isHovered || isSelected;
    if (showLabel) {
      const fontSize = Math.max(11 / globalScale, 3.5);
      ctx.font = `${isHovered || isSelected ? "bold " : ""}${fontSize}px Inter, sans-serif`;
      ctx.fillStyle = dimmed ? "rgba(0,0,0,0.15)" : "rgba(0,0,0,0.75)";
      ctx.textAlign = "center";
      ctx.fillText(node.label || "", node.x, node.y + size + fontSize + 2);
    }
  }, [hoveredNode, selectedNode, filteredData.links]);

  // Link paint
  const paintLink = useCallback((link, ctx) => {
    const sourceId = link.source?.id || link.source;
    const targetId = link.target?.id || link.target;
    const isConnectedToHover = hoveredNode && (sourceId === hoveredNode.id || targetId === hoveredNode.id);
    const dimmed = hoveredNode && !isConnectedToHover;

    ctx.beginPath();
    ctx.moveTo(link.source.x, link.source.y);
    ctx.lineTo(link.target.x, link.target.y);

    const baseColor = EDGE_COLORS[link.type] || "#666";
    if (dimmed) {
      ctx.strokeStyle = "rgba(0,0,0,0.08)";
      ctx.lineWidth = 0.5;
    } else if (isConnectedToHover) {
      ctx.strokeStyle = baseColor;
      ctx.lineWidth = 2.5;
      ctx.shadowColor = baseColor;
      ctx.shadowBlur = 8;
    } else {
      ctx.strokeStyle = `${baseColor}90`;
      ctx.lineWidth = 1.5;
    }
    ctx.stroke();
    ctx.shadowBlur = 0;

    // Edge label on hover
    if (isConnectedToHover) {
      const mx = (link.source.x + link.target.x) / 2;
      const my = (link.source.y + link.target.y) / 2;
      ctx.font = "9px JetBrains Mono, monospace";
      ctx.fillStyle = "rgba(0,0,0,0.7)";
      ctx.textAlign = "center";
      ctx.fillText(link.type.replace("_", " "), mx, my - 4);
    }
  }, [hoveredNode]);

  return (
    <div ref={containerRef} style={{ padding: "24px 24px 0", maxWidth: 1200, margin: "0 auto" }}>
      {/* Header */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 16, flexWrap: "wrap", gap: 12 }}>
        <div>
          <h1 style={{ fontSize: 24, fontWeight: 700, color: T.text, margin: 0, fontFamily: "'Inter', system-ui" }}>
            Knowledge Graph
          </h1>
          <p style={{ color: T.textMuted, fontSize: 13, marginTop: 4 }}>
            {graphData ? `${filteredData.nodes.length} nodes, ${filteredData.links.length} edges` : "Loading..."}
            {" — click a node for details, hover to highlight connections"}
          </p>
        </div>

        {/* Category filter */}
        <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
          {CATEGORIES.map((cat) => (
            <button
              key={cat}
              onClick={() => setCategory(cat)}
              style={{
                padding: "6px 14px",
                fontSize: 11,
                fontWeight: category === cat ? 600 : 400,
                border: `1px solid ${category === cat ? T.accent : T.border}`,
                borderRadius: 8,
                cursor: "pointer",
                background: category === cat ? "rgba(249,115,22,0.15)" : "transparent",
                color: category === cat ? T.accent : T.textMuted,
                fontFamily: "'Inter', system-ui",
              }}
            >
              {cat}
            </button>
          ))}
        </div>
      </div>

      {/* Node type filter — click to toggle, double-click to isolate */}
      <div style={{
        display: "flex",
        gap: 8,
        marginBottom: 16,
        padding: "10px 16px",
        background: T.card,
        borderRadius: 10,
        border: `1px solid ${T.border}`,
        flexWrap: "wrap",
        alignItems: "center",
      }}>
        <span style={{ fontSize: 10, color: T.textDim, fontFamily: "'JetBrains Mono', monospace", textTransform: "uppercase", letterSpacing: 1, marginRight: 8 }}>
          Filter:
        </span>
        {Object.entries(NODE_COLORS).map(([type, color]) => {
          const active = visibleTypes.has(type);
          const count = graphData?.nodes?.filter((n) => n.type === type).length || 0;
          return (
            <button
              key={type}
              onClick={() => toggleType(type)}
              onDoubleClick={() => isolateType(type)}
              title={`Click: toggle | Double-click: show only ${NODE_LABELS[type]} + connections`}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 6,
                padding: "5px 12px",
                borderRadius: 8,
                border: `1px solid ${active ? color + "60" : T.border}`,
                background: active ? color + "15" : "transparent",
                cursor: "pointer",
                opacity: active ? 1 : 0.4,
                transition: "all 0.15s",
              }}
            >
              <div style={{
                width: 8, height: 8, borderRadius: "50%",
                background: color,
                boxShadow: active ? `0 0 6px ${color}60` : "none",
              }} />
              <span style={{
                fontSize: 11, color: active ? T.text : T.textDim,
                fontFamily: "'Inter', system-ui", fontWeight: 500,
              }}>
                {NODE_LABELS[type]} ({count})
              </span>
            </button>
          );
        })}
        <button
          onClick={() => setVisibleTypes(new Set(Object.keys(NODE_COLORS)))}
          style={{
            marginLeft: "auto",
            padding: "5px 12px",
            borderRadius: 8,
            border: `1px solid ${T.border}`,
            background: "transparent",
            color: T.textMuted,
            fontSize: 11,
            cursor: "pointer",
            fontFamily: "'Inter', system-ui",
          }}
        >
          Show All
        </button>
      </div>

      {/* Graph */}
      <div ref={graphWrapRef} style={{
        background: "#f5f5f4",
        borderRadius: isFullscreen ? 0 : 16,
        border: isFullscreen ? "none" : `1px solid ${T.border}`,
        overflow: "hidden",
        position: isFullscreen ? "fixed" : "relative",
        inset: isFullscreen ? 0 : "auto",
        zIndex: isFullscreen ? 500 : "auto",
      }}>
        {/* Zoom + Fullscreen controls */}
        <div style={{
          position: "absolute", top: 12, left: 12, zIndex: 20,
          display: "flex", flexDirection: "column", gap: 4,
        }}>
          {[
            { label: "+", action: handleZoomIn, title: "Zoom in" },
            { label: "-", action: handleZoomOut, title: "Zoom out" },
            { label: "Fit", action: handleZoomFit, title: "Zoom to fit all nodes" },
            { label: isFullscreen ? "Exit" : "Full", action: toggleFullscreen, title: isFullscreen ? "Exit fullscreen" : "Fullscreen" },
          ].map((btn) => (
            <button
              key={btn.label}
              onClick={btn.action}
              title={btn.title}
              style={{
                width: 40, height: 32,
                background: "rgba(255,255,255,0.95)",
                border: "1px solid rgba(0,0,0,0.12)",
                borderRadius: 8,
                color: "#222",
                boxShadow: "0 2px 6px rgba(0,0,0,0.1)",
                fontSize: btn.label.length > 1 ? 10 : 16,
                fontWeight: 600,
                cursor: "pointer",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                backdropFilter: "blur(4px)",
                fontFamily: btn.label.length > 1 ? "'Inter', system-ui" : "inherit",
              }}
              onMouseEnter={(e) => e.currentTarget.style.borderColor = T.accent}
              onMouseLeave={(e) => e.currentTarget.style.borderColor = T.border}
            >
              {btn.label}
            </button>
          ))}
        </div>
        {loading ? (
          <div style={{ display: "flex", justifyContent: "center", alignItems: "center", height: dimensions.height }}>
            <DeskMindSpinner size="lg" label="Loading graph..." />
          </div>
        ) : (
          <ForceGraph2D
            ref={graphRef}
            graphData={filteredData}
            width={isFullscreen ? dimensions.width : dimensions.width - 48}
            height={dimensions.height}
            backgroundColor="#f5f5f4"
            nodeCanvasObject={paintNode}
            nodePointerAreaPaint={(node, color, ctx) => {
              const size = NODE_SIZES[node.type] || 6;
              ctx.beginPath();
              ctx.arc(node.x, node.y, size + 5, 0, 2 * Math.PI);
              ctx.fillStyle = color;
              ctx.fill();
            }}
            linkCanvasObject={paintLink}
            onNodeHover={setHoveredNode}
            onNodeClick={(node) => setSelectedNode(node === selectedNode ? null : node)}
            cooldownTicks={100}
            d3AlphaDecay={0.025}
            d3VelocityDecay={0.4}
            enableNodeDrag={false}
            onEngineStop={() => {
              // Freeze all node positions after layout stabilizes
              filteredData.nodes.forEach((n) => { n.fx = n.x; n.fy = n.y; });
            }}
            enableZoomInteraction={true}
            enablePanInteraction={true}
          />
        )}

        {/* Edge type legend (bottom-left) */}
        <div style={{
          position: "absolute", bottom: 12, left: 12,
          background: "rgba(255,255,255,0.95)", borderRadius: 10,
          border: "1px solid rgba(0,0,0,0.1)", padding: "8px 12px",
          backdropFilter: "blur(4px)",
          boxShadow: "0 2px 8px rgba(0,0,0,0.08)",
        }}>
          <div style={{ fontSize: 9, color: T.textDim, fontFamily: "'JetBrains Mono', monospace", textTransform: "uppercase", letterSpacing: 1, marginBottom: 6 }}>
            Edge Types
          </div>
          <div style={{ display: "flex", flexWrap: "wrap", gap: "4px 12px" }}>
            {Object.entries(EDGE_COLORS).map(([type, color]) => (
              <div key={type} style={{ display: "flex", alignItems: "center", gap: 4 }}>
                <div style={{ width: 16, height: 2, background: color, borderRadius: 1 }} />
                <span style={{ fontSize: 10, color: T.textMuted, fontFamily: "'JetBrains Mono', monospace" }}>
                  {type.replace("_", " ")}
                </span>
              </div>
            ))}
          </div>
        </div>

        {/* Selected node detail panel */}
        {selectedNode && (
          <div style={{
            position: "absolute",
            top: 16,
            right: 16,
            width: 280,
            background: T.graphOverlay,
            border: `1px solid ${T.graphOverlayBorder}`,
            borderRadius: 12,
            padding: 16,
            backdropFilter: "blur(8px)",
            boxShadow: T.graphOverlayShadow,
            zIndex: 10,
          }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                <div style={{
                  width: 12, height: 12, borderRadius: "50%",
                  background: NODE_COLORS[selectedNode.type],
                  boxShadow: `0 0 8px ${NODE_COLORS[selectedNode.type]}60`,
                }} />
                <span style={{
                  fontSize: 10, fontWeight: 600, color: NODE_COLORS[selectedNode.type],
                  textTransform: "uppercase", letterSpacing: 1,
                  fontFamily: "'JetBrains Mono', monospace",
                }}>
                  {NODE_LABELS[selectedNode.type] || selectedNode.type}
                </span>
              </div>
              <button
                onClick={() => setSelectedNode(null)}
                style={{ background: "none", border: "none", color: T.textMuted, cursor: "pointer", fontSize: 14 }}
              >
                ✕
              </button>
            </div>

            <div style={{ fontSize: 14, fontWeight: 600, color: T.graphOverlayText, marginBottom: 12 }}>
              {selectedNode.label}
            </div>

            {selectedNode.data && Object.entries(selectedNode.data).map(([key, val]) => {
              if (!val || key === "key") return null;
              const display = Array.isArray(val) ? val.join(", ") : String(val);
              if (!display) return null;
              return (
                <div key={key} style={{ marginBottom: 8 }}>
                  <div style={{
                    fontSize: 9, fontWeight: 600, color: T.graphOverlayMuted,
                    textTransform: "uppercase", letterSpacing: 1,
                    fontFamily: "'JetBrains Mono', monospace",
                    marginBottom: 2,
                  }}>
                    {key.replace(/_/g, " ")}
                  </div>
                  <div style={{ fontSize: 12, color: T.graphOverlayText, wordBreak: "break-word" }}>
                    {display}
                  </div>
                </div>
              );
            })}

            {/* Connected nodes */}
            {(() => {
              const connections = filteredData.links.filter((e) => {
                const s = e.source?.id || e.source;
                const t = e.target?.id || e.target;
                return s === selectedNode.id || t === selectedNode.id;
              });
              if (connections.length === 0) return null;
              return (
                <div style={{ marginTop: 8, paddingTop: 8, borderTop: `1px solid ${T.graphOverlayBorder}` }}>
                  <div style={{ fontSize: 9, fontWeight: 600, color: T.graphOverlayMuted, textTransform: "uppercase", letterSpacing: 1, fontFamily: "'JetBrains Mono', monospace", marginBottom: 6 }}>
                    Connections ({connections.length})
                  </div>
                  {connections.slice(0, 8).map((e, i) => {
                    const s = e.source?.id || e.source;
                    const t = e.target?.id || e.target;
                    const otherId = s === selectedNode.id ? t : s;
                    const otherNode = filteredData.nodes.find((n) => n.id === otherId);
                    return (
                      <div key={i} style={{
                        display: "flex", alignItems: "center", gap: 6,
                        fontSize: 11, color: T.graphOverlayMuted, marginBottom: 3,
                      }}>
                        <div style={{ width: 6, height: 6, borderRadius: "50%", background: NODE_COLORS[otherNode?.type] || T.graphOverlayMuted }} />
                        <span style={{ color: T.graphOverlayText, fontSize: 11 }}>{otherNode?.label || otherId}</span>
                        <span style={{ fontSize: 9, color: T.graphOverlayMuted, fontFamily: "'JetBrains Mono', monospace" }}>
                          {e.type?.replace("_", " ")}
                        </span>
                      </div>
                    );
                  })}
                  {connections.length > 8 && (
                    <div style={{ fontSize: 10, color: T.graphOverlayMuted, marginTop: 4 }}>+{connections.length - 8} more</div>
                  )}
                </div>
              );
            })()}
          </div>
        )}
      </div>
    </div>
  );
}
