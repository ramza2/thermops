import type { Connection, Edge, Node } from "@xyflow/react";
import type {
  GraphTemplateId,
  VisualPipelineGraph,
  VisualPipelineGraphEdge,
  VisualPipelineGraphNode,
} from "@/types/visualPipeline";

export const MVP_COMPONENT_TYPES = [
  "VP_REST_API_SOURCE",
  "VP_TRANSFORM",
  "VP_UPSERT_LOAD",
  "VP_CRON_SCHEDULE",
] as const;

/** Catalog canonical ports + data types (S1 MVP). */
export const DEFAULT_PORTS: Record<string, { input: string[]; output: string[] }> = {
  VP_REST_API_SOURCE: { input: ["trigger"], output: ["raw_rows"] },
  VP_TRANSFORM: { input: ["input_rows"], output: ["transformed_rows"] },
  VP_UPSERT_LOAD: { input: ["input_rows"], output: ["load_result"] },
  VP_CRON_SCHEDULE: { input: [], output: ["schedule_config"] },
};

export const PORT_DATA_TYPES: Record<string, Record<string, string>> = {
  VP_REST_API_SOURCE: { trigger: "SCHEDULE_TRIGGER", raw_rows: "RAW_ROWS" },
  VP_TRANSFORM: { input_rows: "RAW_ROWS", transformed_rows: "TRANSFORMED_ROWS" },
  VP_UPSERT_LOAD: { input_rows: "TRANSFORMED_ROWS", load_result: "LOAD_RESULT" },
  VP_CRON_SCHEDULE: { schedule_config: "SCHEDULE_CONFIG" },
};

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

export function makePortHandleId(direction: "input" | "output", portName: string): string {
  return `${direction}:${portName}`;
}

export function parsePortHandleId(handleId?: string | null): {
  direction?: "input" | "output";
  portName?: string;
  raw?: string;
  malformed?: boolean;
  legacyBare?: boolean;
} {
  if (!handleId || !String(handleId).trim()) return {};
  const raw = String(handleId).trim();
  const idx = raw.indexOf(":");
  if (idx >= 0) {
    const dir = raw.slice(0, idx);
    const portName = raw.slice(idx + 1);
    if ((dir === "input" || dir === "output") && portName) {
      return { direction: dir, portName, raw };
    }
    return { malformed: true, raw };
  }
  return { portName: raw, raw, legacyBare: true };
}

export function normalizeEdgeLabel(sourcePort?: string, targetPort?: string): string | undefined {
  if (sourcePort && targetPort) return `${sourcePort} → ${targetPort}`;
  return sourcePort || targetPort || undefined;
}

export function getNodeComponentType(node: Node | { type?: string; data?: Record<string, unknown> }): string {
  return String(node.type ?? node.data?.component_type ?? "").trim().toUpperCase();
}

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
  const ports = DEFAULT_PORTS[componentType] ?? { input: [], output: [] };
  return {
    label: label ?? componentType.replace(/^VP_/, "").replace(/_/g, " "),
    config: {},
    component_type: componentType,
    input_ports: ports.input,
    output_ports: ports.output,
  };
}

function templateEdge(
  id: string,
  source: string,
  target: string,
  sourcePort: string,
  targetPort: string,
  dataType: string,
): VisualPipelineGraphEdge {
  return {
    id,
    source,
    target,
    sourceHandle: makePortHandleId("output", sourcePort),
    targetHandle: makePortHandleId("input", targetPort),
    label: normalizeEdgeLabel(sourcePort, targetPort),
    data: { source_port: sourcePort, target_port: targetPort, data_type: dataType },
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
        templateEdge("e1", "n-rest", "n-xform", "raw_rows", "input_rows", "RAW_ROWS"),
        templateEdge("e2", "n-xform", "n-load", "transformed_rows", "input_rows", "TRANSFORMED_ROWS"),
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
      templateEdge("e1", "n-cron", "n-rest", "schedule_config", "trigger", "SCHEDULE_CONFIG"),
      templateEdge("e2", "n-rest", "n-xform", "raw_rows", "input_rows", "RAW_ROWS"),
      templateEdge("e3", "n-xform", "n-load", "transformed_rows", "input_rows", "TRANSFORMED_ROWS"),
    ],
    viewport: { x: 0, y: 0, zoom: 1 },
  };
}

export function graphToFlow(graph: VisualPipelineGraph | undefined | null): { nodes: Node[]; edges: Edge[] } {
  const g = graph ?? emptyGraph();
  const nodes: Node[] = (g.nodes ?? []).map((n) => {
    const ctype = String(n.type ?? "").toUpperCase();
    const ports = DEFAULT_PORTS[ctype] ?? { input: [], output: [] };
    const data = n.data ?? {};
    return {
      id: n.id,
      type: n.type,
      position: n.position ?? { x: 0, y: 0 },
      data: {
        ...data,
        component_type: ctype,
        label: (data.label as string) ?? n.type,
        input_ports: (data.input_ports as string[]) ?? ports.input,
        output_ports: (data.output_ports as string[]) ?? ports.output,
      },
    };
  });
  const edges: Edge[] = (g.edges ?? []).map((e, idx) => ({
    id: e.id ?? `edge-${e.source}-${e.target}-${idx}`,
    source: e.source,
    target: e.target,
    sourceHandle: e.sourceHandle,
    targetHandle: e.targetHandle,
    data: e.data ?? {},
    animated: false,
    ...edgeLabelStyleProps(e.label),
  }));
  return { nodes, edges };
}

export function flowToGraph(nodes: Node[], edges: Edge[], viewport: VisualPipelineGraph["viewport"]): VisualPipelineGraph {
  const graphNodes: VisualPipelineGraphNode[] = nodes.map((n) => {
    const ctype = getNodeComponentType(n);
    return {
      id: n.id,
      type: ctype || "VP_TRANSFORM",
      position: { x: n.position.x, y: n.position.y },
      data: {
        label: (n.data?.label as string) ?? n.id,
        config: (n.data?.config as Record<string, unknown>) ?? {},
        component_type: ctype,
        description: n.data?.description,
        input_ports: n.data?.input_ports,
        output_ports: n.data?.output_ports,
      },
    };
  });
  const graphEdges: VisualPipelineGraphEdge[] = edges.map((e, idx) => {
    const data = (e.data ?? {}) as VisualPipelineGraphEdge["data"];
    const edge: VisualPipelineGraphEdge = {
      id: e.id ?? `edge-${e.source}-${e.target}-${idx}`,
      source: e.source,
      target: e.target,
      label: typeof e.label === "string" ? e.label : undefined,
    };
    if (e.sourceHandle) edge.sourceHandle = String(e.sourceHandle);
    if (e.targetHandle) edge.targetHandle = String(e.targetHandle);
    if (data && Object.keys(data).length > 0) edge.data = { ...data };
    return edge;
  });
  return {
    nodes: graphNodes,
    edges: graphEdges,
    viewport: viewport ?? { x: 0, y: 0, zoom: 1 },
  };
}

export function enrichEdgeWithPortMetadata(
  connection: Connection,
  nodes: Node[],
): Connection &
  ReturnType<typeof edgeLabelStyleProps> & {
    data?: {
      source_port?: string;
      target_port?: string;
      data_type?: string;
    };
  } {
  const sourceNode = nodes.find((n) => n.id === connection.source);
  const targetNode = nodes.find((n) => n.id === connection.target);
  const sourceType = sourceNode ? getNodeComponentType(sourceNode) : "";
  const targetType = targetNode ? getNodeComponentType(targetNode) : "";

  const srcParsed = parsePortHandleId(connection.sourceHandle);
  const tgtParsed = parsePortHandleId(connection.targetHandle);

  let sourcePort = srcParsed.portName;
  let targetPort = tgtParsed.portName;

  // If RF sent bare ids (legacy), keep as port names and upgrade handle ids
  const sourceHandle =
    srcParsed.direction === "output" && sourcePort
      ? makePortHandleId("output", sourcePort)
      : srcParsed.legacyBare && sourcePort
        ? makePortHandleId("output", sourcePort)
        : connection.sourceHandle ?? null;
  const targetHandle =
    tgtParsed.direction === "input" && targetPort
      ? makePortHandleId("input", targetPort)
      : tgtParsed.legacyBare && targetPort
        ? makePortHandleId("input", targetPort)
        : connection.targetHandle ?? null;

  if (!sourcePort && sourceHandle) sourcePort = parsePortHandleId(sourceHandle).portName;
  if (!targetPort && targetHandle) targetPort = parsePortHandleId(targetHandle).portName;

  const dataType =
    (sourceType && sourcePort && PORT_DATA_TYPES[sourceType]?.[sourcePort]) ||
    (targetType && targetPort && PORT_DATA_TYPES[targetType]?.[targetPort]) ||
    undefined;

  const label = normalizeEdgeLabel(sourcePort, targetPort);
  return {
    source: connection.source!,
    target: connection.target!,
    sourceHandle,
    targetHandle,
    ...edgeLabelStyleProps(label),
    data: {
      source_port: sourcePort,
      target_port: targetPort,
      data_type: dataType,
    },
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
  rules: Array<{
    from_component_type: string;
    to_component_type: string;
    from_port_id?: string;
    to_port_id?: string;
    allowed: boolean;
    reason?: string;
  }>,
  sourceType: string,
  targetType: string,
  sourcePort?: string,
  targetPort?: string,
): string | null {
  const portMatches = rules.filter(
    (r) =>
      r.from_component_type === sourceType &&
      r.to_component_type === targetType &&
      (!sourcePort || !r.from_port_id || r.from_port_id === sourcePort) &&
      (!targetPort || !r.to_port_id || r.to_port_id === targetPort),
  );
  const match =
    portMatches.find((r) => r.from_port_id === sourcePort && r.to_port_id === targetPort) ??
    portMatches[0] ??
    rules.find((r) => r.from_component_type === sourceType && r.to_component_type === targetType);

  if (!match) {
    return `연결 규칙에 없는 조합입니다 (${sourceType} → ${targetType}).`;
  }
  if (!match.allowed) {
    return match.reason ?? `허용되지 않는 연결입니다 (${sourceType} → ${targetType}).`;
  }
  return null;
}
