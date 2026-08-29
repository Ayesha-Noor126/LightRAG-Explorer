import { useCallback, useEffect, useRef, useState } from "react";
import { getGraphData, getGraphStats } from "../api/client";

// ─── Constants ────────────────────────────────────────────────────────────────

const W = 900;
const H = 620;

// Entity-type → colour mapping (mirrors what Neo4j browser uses by default)
const TYPE_COLORS = {
  artifact:     "#6366f1", // indigo
  concept:      "#10b981", // emerald
  organization: "#f59e0b", // amber
  person:       "#ec4899", // pink
  method:       "#3b82f6", // blue
  location:     "#8b5cf6", // violet
  event:        "#ef4444", // red
  technology:   "#06b6d4", // cyan
};
const DEFAULT_COLOR = "#94a3b8"; // slate-400

function typeColor(type) {
  if (!type) return DEFAULT_COLOR;
  return TYPE_COLORS[type.toLowerCase()] ?? DEFAULT_COLOR;
}

// ─── Tiny force-directed simulator (no external library) ─────────────────────
// Runs only when data changes; returns stable {x,y} per node.

function runForce(nodes, edges, iterations = 200) {
  const positions = {};
  const rng = (seed) => {
    // deterministic pseudo-random so layout is stable across re-renders
    let s = seed;
    return () => { s = (s * 1664525 + 1013904223) & 0xffffffff; return s / 0x100000000 + 0.5; };
  };

  nodes.forEach((n, i) => {
    const rand = rng(i * 997);
    positions[n.id] = {
      x: W / 2 + (rand() - 0.5) * 400,
      y: H / 2 + (rand() - 0.5) * 400,
      vx: 0,
      vy: 0,
    };
  });

  const edgeMap = edges.map((e) => ({
    s: e.source,
    t: e.target,
  }));

  const REPEL   = 2200;
  const ATTRACT = 0.04;
  const IDEAL   = 110;
  const DAMP    = 0.85;
  const CENTER  = 0.012;

  for (let iter = 0; iter < iterations; iter++) {
    // repulsion between every pair
    for (let i = 0; i < nodes.length; i++) {
      for (let j = i + 1; j < nodes.length; j++) {
        const a = positions[nodes[i].id];
        const b = positions[nodes[j].id];
        const dx = a.x - b.x;
        const dy = a.y - b.y;
        const dist = Math.sqrt(dx * dx + dy * dy) || 1;
        const force = REPEL / (dist * dist);
        const fx = (dx / dist) * force;
        const fy = (dy / dist) * force;
        a.vx += fx; a.vy += fy;
        b.vx -= fx; b.vy -= fy;
      }
    }

    // spring attraction along edges
    edgeMap.forEach(({ s, t }) => {
      const a = positions[s];
      const b = positions[t];
      if (!a || !b) return;
      const dx = b.x - a.x;
      const dy = b.y - a.y;
      const dist = Math.sqrt(dx * dx + dy * dy) || 1;
      const displacement = dist - IDEAL;
      const force = ATTRACT * displacement;
      const fx = (dx / dist) * force;
      const fy = (dy / dist) * force;
      a.vx += fx; a.vy += fy;
      b.vx -= fx; b.vy -= fy;
    });

    // pull toward centre
    nodes.forEach((n) => {
      const p = positions[n.id];
      p.vx += (W / 2 - p.x) * CENTER;
      p.vy += (H / 2 - p.y) * CENTER;
    });

    // integrate + damp
    nodes.forEach((n) => {
      const p = positions[n.id];
      p.vx *= DAMP; p.vy *= DAMP;
      p.x += p.vx;  p.y += p.vy;
      // clamp to canvas with margin
      p.x = Math.max(40, Math.min(W - 40, p.x));
      p.y = Math.max(40, Math.min(H - 40, p.y));
    });
  }

  return positions;
}

// ─── Sub-components ───────────────────────────────────────────────────────────

function StatPill({ label, value, color = "slate" }) {
  const colors = {
    slate:  "bg-slate-100 text-slate-700",
    indigo: "bg-indigo-50 text-indigo-700",
    emerald:"bg-emerald-50 text-emerald-700",
    amber:  "bg-amber-50 text-amber-700",
  };
  return (
    <div className={`flex flex-col rounded-lg px-4 py-2.5 ${colors[color]}`}>
      <span className="text-[10px] font-semibold uppercase tracking-wider opacity-60">{label}</span>
      <span className="text-xl font-bold">{value ?? "—"}</span>
    </div>
  );
}

function Legend({ types }) {
  if (!types.length) return null;
  return (
    <div className="flex flex-wrap gap-2">
      {types.map((t) => (
        <span key={t} className="flex items-center gap-1.5 rounded-full border border-slate-200 bg-white px-2.5 py-1 text-xs text-slate-600 shadow-sm">
          <span className="inline-block h-2.5 w-2.5 rounded-full" style={{ background: typeColor(t) }} />
          {t}
        </span>
      ))}
    </div>
  );
}

function NodeDetail({ node, connectedEdges, allNodes }) {
  if (!node) return (
    <p className="text-sm text-slate-400 italic">Click any node to inspect it.</p>
  );

  const posMap = Object.fromEntries((allNodes || []).map((n) => [n.id, n.label]));

  return (
    <div className="space-y-3 text-sm">
      {/* Header */}
      <div className="flex items-start gap-2">
        <span
          className="mt-0.5 h-3 w-3 shrink-0 rounded-full"
          style={{ background: typeColor(node.entity_type) }}
        />
        <p className="font-semibold text-slate-900 leading-tight">{node.label}</p>
      </div>

      {node.entity_type && (
        <span className="inline-block rounded-full bg-slate-100 px-2.5 py-0.5 text-xs font-medium text-slate-600">
          {node.entity_type}
        </span>
      )}

      {node.description && (
        <p className="rounded-md bg-slate-50 p-2.5 text-xs text-slate-700 leading-relaxed border border-slate-100">
          {node.description}
        </p>
      )}

      <div className="flex gap-3">
        <span className="rounded bg-indigo-50 px-2 py-0.5 text-xs text-indigo-700">
          Degree: <strong>{node.degree}</strong>
        </span>
      </div>

      {/* Connected relationships */}
      {connectedEdges.length > 0 && (
        <div>
          <p className="mb-1.5 text-[10px] font-semibold uppercase tracking-wider text-slate-400">
            Relationships ({connectedEdges.length})
          </p>
          <ul className="space-y-1.5 max-h-52 overflow-y-auto pr-1">
            {connectedEdges.map((e, i) => {
              const isOut = e.source === node.id;
              const other = isOut ? e.target : e.source;
              const otherLabel = posMap[other] ?? other;
              return (
                <li key={i} className="rounded border border-slate-100 bg-slate-50 px-2.5 py-1.5 text-xs">
                  <div className="flex items-center gap-1.5 text-slate-600">
                    <span className={`font-medium ${isOut ? "text-indigo-600" : "text-emerald-600"}`}>
                      {isOut ? "→" : "←"}
                    </span>
                    <span className="font-medium text-slate-800 truncate">{otherLabel}</span>
                  </div>
                  {e.description && (
                    <p className="mt-0.5 text-slate-500 leading-relaxed">{e.description}</p>
                  )}
                </li>
              );
            })}
          </ul>
        </div>
      )}
    </div>
  );
}

// ─── Main component ───────────────────────────────────────────────────────────

export default function GraphView() {
  const [stats, setStats]         = useState(null);
  const [graph, setGraph]         = useState(null);
  const [positioned, setPositioned] = useState([]);
  const [posById, setPosById]     = useState({});
  const [error, setError]         = useState(null);
  const [loading, setLoading]     = useState(true);
  const [selected, setSelected]   = useState(null);
  const [hovered, setHovered]     = useState(null);
  const [search, setSearch]       = useState("");
  const [nodeLimit, setNodeLimit] = useState(150);

  // zoom / pan state
  const [transform, setTransform] = useState({ x: 0, y: 0, scale: 1 });
  const isPanning = useRef(false);
  const panStart  = useRef({ x: 0, y: 0, tx: 0, ty: 0 });
  const svgRef    = useRef(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    setSelected(null);
    try {
      const [statsRes, graphRes] = await Promise.all([
        getGraphStats(),
        getGraphData(nodeLimit),
      ]);
      setStats(statsRes);
      setGraph(graphRes);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [nodeLimit]);

  useEffect(() => { load(); }, [load]);

  // Run force layout whenever graph data changes
  useEffect(() => {
    if (!graph?.nodes?.length) return;
    const positions = runForce(graph.nodes, graph.edges, 250);
    const pos = graph.nodes.map((n) => ({ ...n, ...positions[n.id] }));
    setPositioned(pos);
    setPosById(Object.fromEntries(pos.map((n) => [n.id, n])));
  }, [graph]);

  // ── pan/zoom handlers ──
  const handleWheel = (e) => {
    e.preventDefault();
    const delta = e.deltaY > 0 ? 0.9 : 1.1;
    setTransform((t) => ({
      ...t,
      scale: Math.max(0.2, Math.min(4, t.scale * delta)),
    }));
  };

  const handleMouseDown = (e) => {
    if (e.button !== 0) return;
    isPanning.current = true;
    panStart.current = { x: e.clientX, y: e.clientY, tx: transform.x, ty: transform.y };
  };

  const handleMouseMove = (e) => {
    if (!isPanning.current) return;
    setTransform((t) => ({
      ...t,
      x: panStart.current.tx + (e.clientX - panStart.current.x),
      y: panStart.current.ty + (e.clientY - panStart.current.y),
    }));
  };

  const stopPan = () => { isPanning.current = false; };

  const resetView = () => setTransform({ x: 0, y: 0, scale: 1 });

  // ── derived data ──
  const searchLower = search.toLowerCase();
  const matchIds = new Set(
    search
      ? positioned.filter((n) =>
          n.label.toLowerCase().includes(searchLower) ||
          (n.entity_type || "").toLowerCase().includes(searchLower)
        ).map((n) => n.id)
      : []
  );

  const maxDegree = Math.max(1, ...positioned.map((n) => n.degree));
  const entityTypes = [...new Set(positioned.map((n) => n.entity_type).filter(Boolean))].sort();

  const connectedEdges = selected
    ? (graph?.edges ?? []).filter(
        (e) => e.source === selected.id || e.target === selected.id
      )
    : [];

  // ── render states ──
  if (loading) return (
    <div className="flex h-64 items-center justify-center">
      <div className="flex flex-col items-center gap-3 text-slate-400">
        <svg className="h-8 w-8 animate-spin" viewBox="0 0 24 24" fill="none">
          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z"/>
        </svg>
        <span className="text-sm">Loading graph…</span>
      </div>
    </div>
  );

  if (error) return (
    <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
      {error}
      <button onClick={load} className="ml-3 rounded border border-red-300 px-2 py-0.5 text-xs hover:bg-red-100">Retry</button>
    </div>
  );

  if (!stats?.reachable) return (
    <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
      Neo4j is not reachable. Make sure the Neo4j container is running and{" "}
      <code className="rounded bg-amber-100 px-1">NEO4J_URI</code> is correct.
      <button onClick={load} className="ml-3 rounded border border-amber-300 px-2 py-0.5 text-xs hover:bg-amber-100">Retry</button>
    </div>
  );

  return (
    <div className="space-y-4">

      {/* ── Stats bar ── */}
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-slate-200 bg-white px-5 py-3 shadow-sm">
        <div className="flex flex-wrap gap-3">
          <StatPill label="Entities" value={stats.node_count} color="indigo" />
          <StatPill label="Relationships" value={stats.edge_count} color="emerald" />
          <StatPill label="Density" value={stats.density} color="amber" />
          <StatPill label="Avg Degree" value={stats.avg_degree} color="slate" />
        </div>
        <div className="flex items-center gap-2">
          <select
            value={nodeLimit}
            onChange={(e) => setNodeLimit(Number(e.target.value))}
            className="rounded-md border border-slate-200 px-2.5 py-1.5 text-xs text-slate-600 focus:outline-none focus:ring-2 focus:ring-indigo-300"
          >
            {[50, 100, 150, 250, 500].map((v) => (
              <option key={v} value={v}>Show top {v} nodes</option>
            ))}
          </select>
          <button
            onClick={load}
            className="rounded-md border border-slate-200 px-3 py-1.5 text-xs font-medium text-slate-600 hover:bg-slate-50 transition"
          >
            ↺ Refresh
          </button>
        </div>
      </div>

      {/* ── Legend ── */}
      {entityTypes.length > 0 && (
        <div className="rounded-xl border border-slate-100 bg-white px-4 py-2.5 shadow-sm">
          <p className="mb-2 text-[10px] font-semibold uppercase tracking-wider text-slate-400">Entity Types</p>
          <Legend types={entityTypes} />
        </div>
      )}

      {/* ── Truncation notice ── */}
      {graph?.truncated && (
        <p className="rounded-lg border border-blue-100 bg-blue-50 px-3 py-2 text-xs text-blue-700">
          Showing the top <strong>{graph.nodes.length}</strong> highest-degree nodes.
          The full graph has <strong>{stats.node_count}</strong> entities.
          Increase the limit above to see more.
        </p>
      )}

      {graph?.nodes.length === 0 ? (
        <p className="rounded-xl border border-slate-200 bg-white p-8 text-center text-sm text-slate-400 italic">
          No graph data yet — upload documents and let LightRAG finish entity extraction.
        </p>
      ) : (
        <div className="grid gap-4 lg:grid-cols-[1fr_300px]">

          {/* ── SVG canvas ── */}
          <div className="overflow-hidden rounded-xl border border-slate-200 bg-slate-900 shadow-sm">

            {/* toolbar */}
            <div className="flex items-center justify-between gap-2 border-b border-slate-700 px-3 py-2">
              <input
                type="text"
                placeholder="Search nodes…"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="w-48 rounded-md border border-slate-600 bg-slate-800 px-2.5 py-1 text-xs text-slate-200 placeholder:text-slate-500 focus:outline-none focus:ring-1 focus:ring-indigo-400"
              />
              <div className="flex items-center gap-1.5">
                <button onClick={() => setTransform((t) => ({ ...t, scale: Math.min(4, t.scale * 1.2) }))}
                  className="rounded border border-slate-600 px-2 py-0.5 text-xs text-slate-300 hover:bg-slate-700">+</button>
                <button onClick={() => setTransform((t) => ({ ...t, scale: Math.max(0.2, t.scale * 0.8) }))}
                  className="rounded border border-slate-600 px-2 py-0.5 text-xs text-slate-300 hover:bg-slate-700">−</button>
                <button onClick={resetView}
                  className="rounded border border-slate-600 px-2 py-0.5 text-xs text-slate-300 hover:bg-slate-700">Reset</button>
              </div>
            </div>

            <svg
              ref={svgRef}
              viewBox={`0 0 ${W} ${H}`}
              className="h-auto w-full cursor-grab select-none active:cursor-grabbing"
              onWheel={handleWheel}
              onMouseDown={handleMouseDown}
              onMouseMove={handleMouseMove}
              onMouseUp={stopPan}
              onMouseLeave={stopPan}
            >
              {/* arrow marker definition */}
              <defs>
                <marker id="arrow" markerWidth="8" markerHeight="8" refX="7" refY="3" orient="auto">
                  <path d="M0,0 L0,6 L8,3 z" fill="#475569" />
                </marker>
                <marker id="arrow-highlight" markerWidth="8" markerHeight="8" refX="7" refY="3" orient="auto">
                  <path d="M0,0 L0,6 L8,3 z" fill="#818cf8" />
                </marker>
              </defs>

              <g transform={`translate(${transform.x},${transform.y}) scale(${transform.scale})`}>

                {/* Edges */}
                {graph.edges.map((edge, i) => {
                  const s = posById[edge.source];
                  const t = posById[edge.target];
                  if (!s || !t) return null;
                  const isConnected =
                    selected &&
                    (edge.source === selected.id || edge.target === selected.id);
                  const isHoveredEdge =
                    hovered &&
                    (edge.source === hovered || edge.target === hovered);
                  const opacity = selected
                    ? isConnected ? 1 : 0.08
                    : isHoveredEdge ? 0.9 : 0.35;

                  // shorten line so it ends at circle perimeter
                  const rS = 5 + (s.degree / maxDegree) * 14;
                  const rT = 5 + (t.degree / maxDegree) * 14;
                  const dx = t.x - s.x, dy = t.y - s.y;
                  const len = Math.sqrt(dx * dx + dy * dy) || 1;
                  const x1 = s.x + (dx / len) * rS;
                  const y1 = s.y + (dy / len) * rS;
                  const x2 = t.x - (dx / len) * (rT + 8);
                  const y2 = t.y - (dy / len) * (rT + 8);

                  return (
                    <line
                      key={i}
                      x1={x1} y1={y1} x2={x2} y2={y2}
                      stroke={isConnected ? "#818cf8" : "#475569"}
                      strokeWidth={isConnected ? 1.8 : 1}
                      strokeOpacity={opacity}
                      markerEnd={isConnected ? "url(#arrow-highlight)" : "url(#arrow)"}
                    />
                  );
                })}

                {/* Nodes */}
                {positioned.map((node) => {
                  const r = 5 + (node.degree / maxDegree) * 14;
                  const isSelected = selected?.id === node.id;
                  const isHov = hovered === node.id;
                  const isDimmed =
                    (selected && !isSelected &&
                      !connectedEdges.some(
                        (e) => e.source === node.id || e.target === node.id
                      )) ||
                    (search && !matchIds.has(node.id));
                  const color = typeColor(node.entity_type);
                  const showLabel = isSelected || isHov || node.degree > maxDegree * 0.25 || matchIds.has(node.id);

                  return (
                    <g
                      key={node.id}
                      onClick={(e) => { e.stopPropagation(); setSelected(isSelected ? null : node); }}
                      onMouseEnter={() => setHovered(node.id)}
                      onMouseLeave={() => setHovered(null)}
                      className="cursor-pointer"
                      opacity={isDimmed ? 0.18 : 1}
                    >
                      {/* outer glow ring when selected */}
                      {isSelected && (
                        <circle cx={node.x} cy={node.y} r={r + 6}
                          fill="none" stroke="#818cf8" strokeWidth={2} opacity={0.6} />
                      )}
                      <circle
                        cx={node.x} cy={node.y} r={r}
                        fill={color}
                        stroke={isSelected ? "#ffffff" : isHov ? "#e2e8f0" : "rgba(255,255,255,0.25)"}
                        strokeWidth={isSelected ? 2.5 : 1.5}
                      />
                      {/* degree badge for high-degree nodes */}
                      {node.degree > 3 && (
                        <text x={node.x} y={node.y + 4} textAnchor="middle"
                          fontSize={r > 12 ? 9 : 7} fill="rgba(255,255,255,0.9)" fontWeight="600">
                          {node.degree}
                        </text>
                      )}
                      {showLabel && (
                        <text
                          x={node.x} y={node.y - r - 5}
                          textAnchor="middle"
                          fontSize={10}
                          fill={isSelected ? "#c7d2fe" : "#cbd5e1"}
                          fontWeight={isSelected ? "600" : "400"}
                        >
                          {node.label.length > 18 ? node.label.slice(0, 18) + "…" : node.label}
                        </text>
                      )}
                    </g>
                  );
                })}
              </g>

              {/* deselect on canvas click */}
              <rect x={0} y={0} width={W} height={H} fill="transparent"
                onClick={() => setSelected(null)} style={{ pointerEvents: "none" }} />
            </svg>

            <p className="border-t border-slate-700 px-3 py-1.5 text-[10px] text-slate-500">
              Scroll to zoom · Drag to pan · Click a node to inspect
            </p>
          </div>

          {/* ── Detail panel ── */}
          <div className="flex flex-col gap-4">
            <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
              <h3 className="mb-3 text-[10px] font-semibold uppercase tracking-wider text-slate-400">
                Node Details
              </h3>
              <NodeDetail
                node={selected}
                connectedEdges={connectedEdges}
                allNodes={positioned}
              />
            </div>

            {/* top-10 hub nodes */}
            <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
              <h3 className="mb-2 text-[10px] font-semibold uppercase tracking-wider text-slate-400">
                Top Hubs
              </h3>
              <ul className="space-y-1.5">
                {[...positioned]
                  .sort((a, b) => b.degree - a.degree)
                  .slice(0, 10)
                  .map((n) => (
                    <li
                      key={n.id}
                      onClick={() => setSelected(selected?.id === n.id ? null : n)}
                      className="flex cursor-pointer items-center justify-between rounded-md px-2.5 py-1.5 text-xs hover:bg-slate-50 transition"
                    >
                      <div className="flex items-center gap-2 min-w-0">
                        <span className="h-2 w-2 shrink-0 rounded-full"
                          style={{ background: typeColor(n.entity_type) }} />
                        <span className="truncate text-slate-700 font-medium">{n.label}</span>
                      </div>
                      <span className="ml-2 shrink-0 rounded-full bg-slate-100 px-2 py-0.5 text-slate-500">
                        {n.degree}
                      </span>
                    </li>
                  ))}
              </ul>
            </div>
          </div>

        </div>
      )}
    </div>
  );
}
