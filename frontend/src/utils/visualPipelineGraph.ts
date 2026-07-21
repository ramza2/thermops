import type { Edge, Node } from "@xyflow/react";
import type { GraphTemplateId, VisualPipelineGraph, VisualPipelineGraphNode } from "@/types/visualPipeline";

export const MVP_COMPONENT_TYPES = [
  "VP_REST_API_SOURCE",
  "VP_TRANSFORM",
  "VP_UPSERT_LOAD",
  "VP_CRON_SCHEDULE",
] as const;

/** Visual node tokens (S3-1): CRON=indigo, REST=blue, TRANSFORM=amber, UPSERT=emerald */
export const NODE_STYLE: Record<
  string,
  { border: string; header: string; tint: string; accentDot: string; minimap: string }
> = {
  VP_REST_API_SOURCE: {
    border: "border-blue-400",
    header: "bg-blue-600",
    tint: "bg-blue-50/90",
    accentDot: "bg-blue-400",
    minimap: "#2563eb",
  },
  VP_TRANSFORM: {
    border: "border-amber-400",
    header: "bg-amber-500",
    tint: "bg-amber-50/90",
    accentDot: "bg-amber-400",
    minimap: "#d97706",
  },
  VP_UPSERT_LOAD: {
    border: "border-emerald-400",
    header: "bg-emerald-600",
    tint: "bg-emerald-50/90",
    accentDot: "bg-emerald-400",
    minimap: "#059669",
  },
  VP_CRON_SCHEDULE: {
    border: "border-indigo-400",
    header: "bg-indigo-600",
    tint: "bg-indigo-50/90",
    accentDot: "bg-indigo-400",
    minimap: "#4f46e5",
  },
};

export function edgeLabelStyleProps(label?: string): Pick<
  Edge,
  "label" | "labelStyle" | "labelBgStyle" | "labelBgPadding" | "labelBgBorderRadius" | "style" | "type"
> {
  return {
    type: "smoothstep",
    label,
    labelStyle: { fill: "#475569", fontSize: 10, fontWeight: 600 },
    labelBgStyle: { fill: "#ffffff", fillOpacity: 0.95 },
    labelBgPadding: [3, 6],
    labelBgBorderRadius: 4,
    style: { stroke: "#94a3b8", strokeWidth: 1.5 },
  };
}

export function emptyGraph(): VisualPipelineGraph {
  return { nodes: [], edges: [], viewport: { x: 0, y: 0, zoom: 1 } };
}

export function newNodeId(): string {
  return `node-${Math.random().toString(36).slice(2, 9)}`;
}

export function defaultNodeData(componentType: string, label?: string): Record<string, unknown> {
  return {
    label: label ?? componentType.replace(/^VP_/, "").replace(/_/g, " "),
    config: {},
  };
}

export function buildTemplateGraph(templateId: GraphTemplateId): VisualPipelineGraph {
  if (templateId === "blank") return emptyGraph();

  if (templateId === "rest-upsert") {
    return {
      nodes: [
        { id: "n-rest", type: "VP_REST_API_SOURCE", position: { x: 80, y: 120 }, data: defaultNodeData("VP_REST_API_SOURCE", "REST API Source") },
        { id: "n-xform", type: "VP_TRANSFORM", position: { x: 320, y: 120 }, data: defaultNodeData("VP_TRANSFORM", "Transform") },
        { id: "n-load", type: "VP_UPSERT_LOAD", position: { x: 560, y: 120 }, data: defaultNodeData("VP_UPSERT_LOAD", "Upsert Load") },
      ],
      edges: [
        { id: "e1", source: "n-rest", target: "n-xform", label: "raw_rows" },
        { id: "e2", source: "n-xform", target: "n-load", label: "transformed_rows" },
      ],
      viewport: { x: 0, y: 0, zoom: 1 },
    };
  }

  return {
    nodes: [
      { id: "n-cron", type: "VP_CRON_SCHEDULE", position: { x: 20, y: 120 }, data: defaultNodeData("VP_CRON_SCHEDULE", "CRON Schedule") },
      { id: "n-rest", type: "VP_REST_API_SOURCE", position: { x: 240, y: 120 }, data: defaultNodeData("VP_REST_API_SOURCE", "REST API Source") },
      { id: "n-xform", type: "VP_TRANSFORM", position: { x: 460, y: 120 }, data: defaultNodeData("VP_TRANSFORM", "Transform") },
      { id: "n-load", type: "VP_UPSERT_LOAD", position: { x: 680, y: 120 }, data: defaultNodeData("VP_UPSERT_LOAD", "Upsert Load") },
    ],
    edges: [
      { id: "e1", source: "n-cron", target: "n-rest", label: "trigger" },
      { id: "e2", source: "n-rest", target: "n-xform", label: "raw_rows" },
      { id: "e3", source: "n-xform", target: "n-load", label: "transformed_rows" },
    ],
    viewport: { x: 0, y: 0, zoom: 1 },
  };
}

export function graphToFlow(graph: VisualPipelineGraph | undefined | null): { nodes: Node[]; edges: Edge[] } {
  const g = graph ?? emptyGraph();
  const nodes: Node[] = (g.nodes ?? []).map((n) => ({
    id: n.id,
    type: n.type,
    position: n.position ?? { x: 0, y: 0 },
    data: {
      ...(n.data ?? {}),
      component_type: n.type,
      label: (n.data?.label as string) ?? n.type,
    },
  }));
  const edges: Edge[] = (g.edges ?? []).map((e, idx) => ({
    id: e.id ?? `edge-${e.source}-${e.target}-${idx}`,
    source: e.source,
    target: e.target,
    animated: false,
    ...edgeLabelStyleProps(e.label),
  }));
  return { nodes, edges };
}

export function flowToGraph(nodes: Node[], edges: Edge[], viewport: VisualPipelineGraph["viewport"]): VisualPipelineGraph {
  const graphNodes: VisualPipelineGraphNode[] = nodes.map((n) => ({
    id: n.id,
    type: String(n.type ?? n.data?.component_type ?? "VP_TRANSFORM"),
    position: { x: n.position.x, y: n.position.y },
    data: {
      label: (n.data?.label as string) ?? n.id,
      config: (n.data?.config as Record<string, unknown>) ?? {},
    },
  }));
  const graphEdges = edges.map((e, idx) => ({
    id: e.id ?? `edge-${e.source}-${e.target}-${idx}`,
    source: e.source,
    target: e.target,
    label: typeof e.label === "string" ? e.label : undefined,
  }));
  return {
    nodes: graphNodes,
    edges: graphEdges,
    viewport: viewport ?? { x: 0, y: 0, zoom: 1 },
  };
}

export function graphCounts(graph: VisualPipelineGraph | undefined | null): { nodes: number; edges: number } {
  const g = graph ?? emptyGraph();
  return { nodes: g.nodes?.length ?? 0, edges: g.edges?.length ?? 0 };
}

/** Stable JSON for dirty comparison (viewport excluded by default). */
export function serializeGraphBody(graph: VisualPipelineGraph, includeViewport = false): string {
  const payload = includeViewport
    ? graph
    : { nodes: graph.nodes, edges: graph.edges };
  return JSON.stringify(payload);
}

export function placeholderConfigJson(componentType: string): string {
  if (componentType === "VP_REST_API_SOURCE") {
    return JSON.stringify(
      { data_source_id: "미설정", endpoint_path: "미설정", http_method: "GET" },
      null,
      2,
    );
  }
  if (componentType === "VP_TRANSFORM") {
    return JSON.stringify({ transform_profile: "미설정" }, null, 2);
  }
  if (componentType === "VP_UPSERT_LOAD") {
    return JSON.stringify({ dataset_type_id: "미설정", upsert_mode: "미설정" }, null, 2);
  }
  if (componentType === "VP_CRON_SCHEDULE") {
    return JSON.stringify({ cron_expression: "미설정" }, null, 2);
  }
  return JSON.stringify({}, null, 2);
}

export function findConnectionRuleWarning(
  rules: Array<{ from_component_type: string; to_component_type: string; allowed: boolean; reason?: string }>,
  sourceType: string,
  targetType: string,
): string | null {
  const match = rules.find(
    (r) => r.from_component_type === sourceType && r.to_component_type === targetType,
  );
  if (!match) {
    return `연결 규칙에 없는 조합입니다 (${sourceType} → ${targetType}). S4에서 검증 예정.`;
  }
  if (!match.allowed) {
    return match.reason ?? `허용되지 않는 연결입니다 (${sourceType} → ${targetType}).`;
  }
  return null;
}
