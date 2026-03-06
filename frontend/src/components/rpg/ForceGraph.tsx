import { useEffect, useRef, useState, useCallback } from "react";
import type { GraphNode, GraphEdge } from "@/types";

const ENTITY_COLORS: Record<string, string> = {
  character: "#60a5fa", // blue-400
  npc: "#c084fc",      // purple-400
  location: "#fbbf24",  // amber-400
  quest: "#4ade80",     // green-400
  item: "#9ca3af",      // gray-400
};

interface SimNode {
  id: string;
  name: string;
  type: string;
  x: number;
  y: number;
  vx: number;
  vy: number;
  edgeCount: number;
}

interface Props {
  nodes: GraphNode[];
  edges: GraphEdge[];
  width: number;
  height: number;
  typeFilter?: Set<string>;
  minStrength?: number;
}

function runSimulation(nodes: SimNode[], edges: GraphEdge[], width: number, height: number) {
  const cx = width / 2;
  const cy = height / 2;
  const nodeMap = new Map(nodes.map((n) => [n.id, n]));

  for (let iter = 0; iter < 80; iter++) {
    const decay = 1 - iter / 100;

    // Repulsion between all pairs
    for (let i = 0; i < nodes.length; i++) {
      for (let j = i + 1; j < nodes.length; j++) {
        const a = nodes[i];
        const b = nodes[j];
        let dx = a.x - b.x;
        let dy = a.y - b.y;
        const dist = Math.sqrt(dx * dx + dy * dy) || 1;
        const force = (800 / (dist * dist)) * decay;
        dx = (dx / dist) * force;
        dy = (dy / dist) * force;
        a.vx += dx;
        a.vy += dy;
        b.vx -= dx;
        b.vy -= dy;
      }
    }

    // Attraction along edges
    for (const e of edges) {
      const a = nodeMap.get(e.source_id);
      const b = nodeMap.get(e.target_id);
      if (!a || !b) continue;
      let dx = b.x - a.x;
      let dy = b.y - a.y;
      const dist = Math.sqrt(dx * dx + dy * dy) || 1;
      const force = (dist - 100) * 0.02 * decay;
      dx = (dx / dist) * force;
      dy = (dy / dist) * force;
      a.vx += dx;
      a.vy += dy;
      b.vx -= dx;
      b.vy -= dy;
    }

    // Centering force
    for (const n of nodes) {
      n.vx += (cx - n.x) * 0.005 * decay;
      n.vy += (cy - n.y) * 0.005 * decay;
    }

    // Apply velocities with damping
    for (const n of nodes) {
      n.vx *= 0.6;
      n.vy *= 0.6;
      n.x += n.vx;
      n.y += n.vy;
      // Keep within bounds
      n.x = Math.max(40, Math.min(width - 40, n.x));
      n.y = Math.max(40, Math.min(height - 40, n.y));
    }
  }
}

export function ForceGraph({ nodes, edges, width, height, typeFilter, minStrength = 0 }: Props) {
  const svgRef = useRef<SVGSVGElement>(null);
  const [simNodes, setSimNodes] = useState<SimNode[]>([]);
  const [hoveredNode, setHoveredNode] = useState<string | null>(null);
  const [hoveredEdge, setHoveredEdge] = useState<number | null>(null);
  const dragRef = useRef<{ id: string; offsetX: number; offsetY: number } | null>(null);

  // Filter edges
  const filteredEdges = edges.filter((e) => {
    if (minStrength > 0 && e.strength < minStrength) return false;
    if (typeFilter && typeFilter.size > 0) {
      const srcMatch = typeFilter.has(e.source_type);
      const tgtMatch = typeFilter.has(e.target_type);
      if (!srcMatch && !tgtMatch) return false;
    }
    return true;
  });

  // Filter nodes: keep nodes that appear in filtered edges, or all if no filter
  const activeNodeIds = new Set<string>();
  for (const e of filteredEdges) {
    activeNodeIds.add(e.source_id);
    activeNodeIds.add(e.target_id);
  }
  const filteredNodes = nodes.filter((n) => {
    if (typeFilter && typeFilter.size > 0 && !typeFilter.has(n.type)) return false;
    if (filteredEdges.length > 0) return activeNodeIds.has(n.id);
    return true;
  });

  useEffect(() => {
    // Count edges per node
    const edgeCounts: Record<string, number> = {};
    for (const e of filteredEdges) {
      edgeCounts[e.source_id] = (edgeCounts[e.source_id] || 0) + 1;
      edgeCounts[e.target_id] = (edgeCounts[e.target_id] || 0) + 1;
    }

    const sn: SimNode[] = filteredNodes.map((n, i) => ({
      id: n.id,
      name: n.name,
      type: n.type,
      x: width / 2 + Math.cos((i / filteredNodes.length) * Math.PI * 2) * 120,
      y: height / 2 + Math.sin((i / filteredNodes.length) * Math.PI * 2) * 120,
      vx: 0,
      vy: 0,
      edgeCount: edgeCounts[n.id] || 0,
    }));

    runSimulation(sn, filteredEdges, width, height);
    setSimNodes([...sn]);
  }, [filteredNodes.length, filteredEdges.length, width, height]);

  const nodeMap = new Map(simNodes.map((n) => [n.id, n]));

  const handleMouseDown = useCallback((id: string, e: React.MouseEvent) => {
    e.preventDefault();
    const svg = svgRef.current;
    if (!svg) return;
    const pt = svg.createSVGPoint();
    pt.x = e.clientX;
    pt.y = e.clientY;
    const svgPt = pt.matrixTransform(svg.getScreenCTM()?.inverse());
    const node = nodeMap.get(id);
    if (!node) return;
    dragRef.current = { id, offsetX: node.x - svgPt.x, offsetY: node.y - svgPt.y };
  }, [nodeMap]);

  const handleMouseMove = useCallback((e: React.MouseEvent) => {
    if (!dragRef.current) return;
    const svg = svgRef.current;
    if (!svg) return;
    const pt = svg.createSVGPoint();
    pt.x = e.clientX;
    pt.y = e.clientY;
    const svgPt = pt.matrixTransform(svg.getScreenCTM()?.inverse());
    setSimNodes((prev) =>
      prev.map((n) =>
        n.id === dragRef.current!.id
          ? { ...n, x: svgPt.x + dragRef.current!.offsetX, y: svgPt.y + dragRef.current!.offsetY }
          : n
      )
    );
  }, []);

  const handleMouseUp = useCallback(() => {
    dragRef.current = null;
  }, []);

  return (
    <svg
      ref={svgRef}
      width={width}
      height={height}
      className="select-none"
      onMouseMove={handleMouseMove}
      onMouseUp={handleMouseUp}
      onMouseLeave={handleMouseUp}
    >
      {/* Edges */}
      {filteredEdges.map((e, i) => {
        const src = nodeMap.get(e.source_id);
        const tgt = nodeMap.get(e.target_id);
        if (!src || !tgt) return null;
        const opacity = 0.2 + (e.strength / 100) * 0.6;
        const isHovered = hoveredEdge === i;
        return (
          <g key={i}>
            <line
              x1={src.x}
              y1={src.y}
              x2={tgt.x}
              y2={tgt.y}
              stroke={isHovered ? "#fff" : "#6b7280"}
              strokeWidth={isHovered ? 2 : 1}
              strokeOpacity={isHovered ? 1 : opacity}
              onMouseEnter={() => setHoveredEdge(i)}
              onMouseLeave={() => setHoveredEdge(null)}
              style={{ cursor: "pointer" }}
            />
            {isHovered && (
              <text
                x={(src.x + tgt.x) / 2}
                y={(src.y + tgt.y) / 2 - 6}
                textAnchor="middle"
                fill="#fbbf24"
                fontSize={10}
                fontWeight="bold"
              >
                {e.relationship.replace(/_/g, " ")} ({e.strength})
              </text>
            )}
          </g>
        );
      })}

      {/* Nodes */}
      {simNodes.map((n) => {
        const r = 8 + Math.min(n.edgeCount * 2, 12);
        const color = ENTITY_COLORS[n.type] || "#9ca3af";
        const isHovered = hoveredNode === n.id;
        return (
          <g
            key={n.id}
            onMouseDown={(e) => handleMouseDown(n.id, e)}
            onMouseEnter={() => setHoveredNode(n.id)}
            onMouseLeave={() => setHoveredNode(null)}
            style={{ cursor: "grab" }}
          >
            <circle
              cx={n.x}
              cy={n.y}
              r={r}
              fill={color}
              fillOpacity={isHovered ? 0.9 : 0.6}
              stroke={isHovered ? "#fff" : color}
              strokeWidth={isHovered ? 2 : 1}
            />
            <text
              x={n.x}
              y={n.y + r + 12}
              textAnchor="middle"
              fill={isHovered ? "#fff" : "#d1d5db"}
              fontSize={isHovered ? 12 : 10}
              fontWeight={isHovered ? "bold" : "normal"}
            >
              {n.name}
            </text>
            {isHovered && (
              <text
                x={n.x}
                y={n.y + r + 24}
                textAnchor="middle"
                fill="#9ca3af"
                fontSize={9}
              >
                {n.type} ({n.edgeCount} connections)
              </text>
            )}
          </g>
        );
      })}
    </svg>
  );
}
