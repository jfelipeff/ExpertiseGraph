import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Background,
  Controls,
  MiniMap,
  ReactFlow,
  type Edge,
  type Node,
  useEdgesState,
  useNodesState,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";

const TYPE_COLORS: Record<string, string> = {
  Company: "#1f4d3a",
  Client: "#3d7a5c",
  Consultant: "#c45c26",
  Person: "#a34a1f",
  Project: "#2b6a8a",
  Technology: "#5a4a8a",
  Industry: "#6b5b2e",
  Methodology: "#1f6b5a",
  Topic: "#4a5d4e",
  Document: "#7a6a4a",
  Capability: "#3a6d7a",
  Product: "#6a3d5a",
  Initiative: "#4d6a3a",
  Deliverable: "#7a4d3a",
};

type Props = {
  data: { nodes: any[]; edges: any[] };
  onSelectNode: (id: string) => void;
  onSelectEdge: (edge: any) => void;
  onSearch: (q: string) => Promise<any[]>;
};

export function GraphExplorer({ data, onSelectNode, onSelectEdge, onSearch }: Props) {
  const [query, setQuery] = useState("");
  const [hits, setHits] = useState<any[]>([]);
  const [expanded, setExpanded] = useState<Set<string>>(new Set());

  const layouted = useMemo(() => {
    const nodes: Node[] = data.nodes.map((n, i) => {
      const angle = (i / Math.max(data.nodes.length, 1)) * Math.PI * 2;
      const radius = 180 + (i % 7) * 55;
      const type = n.type || n.document_type || "Topic";
      return {
        id: n.id,
        position: { x: Math.cos(angle) * radius + 420, y: Math.sin(angle) * radius + 300 },
        data: { label: n.label || n.name || n.id, type, raw: n },
        style: {
          background: TYPE_COLORS[type] || "#3d7a5c",
          color: "#f4efe6",
          border: "none",
          borderRadius: 2,
          fontSize: 11,
          padding: "6px 10px",
          maxWidth: 160,
        },
      };
    });
    const edges: Edge[] = data.edges.map((e) => ({
      id: e.id || `${e.source}-${e.type}-${e.target}`,
      source: e.source,
      target: e.target,
      label: e.type,
      data: e,
      style: { stroke: "#1f4d3a99" },
      labelStyle: { fontSize: 10, fill: "#0f1c18" },
    }));
    return { nodes, edges };
  }, [data]);

  const [nodes, setNodes, onNodesChange] = useNodesState(layouted.nodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(layouted.edges);

  useEffect(() => {
    setNodes(layouted.nodes);
    setEdges(layouted.edges);
  }, [layouted, setNodes, setEdges]);

  const onNodeClick = useCallback(
    (_: any, node: Node) => {
      setExpanded((prev) => new Set(prev).add(node.id));
      onSelectNode(node.id);
    },
    [onSelectNode]
  );

  const onEdgeClick = useCallback(
    (_: any, edge: Edge) => {
      onSelectEdge(edge.data || edge);
    },
    [onSelectEdge]
  );

  async function runSearch() {
    if (!query.trim()) {
      setHits([]);
      return;
    }
    const results = await onSearch(query.trim());
    setHits(results);
    const ids = new Set(results.map((r) => r.id));
    setNodes((nds) =>
      nds.map((n) => ({
        ...n,
        style: {
          ...n.style,
          outline: ids.has(n.id) ? "3px solid #c45c26" : undefined,
          opacity: ids.size && !ids.has(n.id) ? 0.35 : 1,
        },
      }))
    );
  }

  function collapseAll() {
    setExpanded(new Set());
    setNodes((nds) => nds.map((n) => ({ ...n, style: { ...n.style, outline: undefined, opacity: 1 } })));
    setHits([]);
  }

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap gap-2">
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search nodes…"
          className="min-w-[220px] flex-1 border border-moss/20 bg-white/80 px-3 py-2 text-sm outline-none ring-fern/30 focus:ring-2"
          onKeyDown={(e) => e.key === "Enter" && runSearch()}
        />
        <button onClick={runSearch} className="bg-moss px-3 py-2 text-sm font-semibold text-sand">
          Search
        </button>
        <button onClick={collapseAll} className="bg-white/80 px-3 py-2 text-sm font-semibold text-moss">
          Reset view
        </button>
      </div>
      {!!hits.length && (
        <div className="flex flex-wrap gap-2 text-xs">
          {hits.map((h) => (
            <button
              key={h.id}
              className="bg-ember/15 px-2 py-1 text-ember"
              onClick={() => onSelectNode(h.id)}
            >
              {h.label} · {h.type}
            </button>
          ))}
        </div>
      )}
      <div className="h-[520px] border border-moss/15 bg-[#f7f3ec]">
        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          onNodeClick={onNodeClick}
          onEdgeClick={onEdgeClick}
          fitView
          minZoom={0.2}
          maxZoom={2}
        >
          <Background gap={18} color="#1f4d3a22" />
          <Controls />
          <MiniMap pannable zoomable />
        </ReactFlow>
      </div>
      <p className="text-xs text-ink/50">
        Expanded selections: {expanded.size || 0}. Click nodes for metadata, edges for provenance.
      </p>
    </div>
  );
}
