import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  Panel,
  addEdge,
  useEdgesState,
  useNodesState,
  type Connection,
  type Edge,
  type Node,
  type OnConnect,
  ReactFlowProvider,
  useReactFlow,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import {
  ChevronLeft,
  Clock,
  History,
  Maximize2,
  Play,
  Save,
  Zap,
} from "lucide-react";
import {
  createVisualPipelineVersion,
  getComponentCatalog,
  getConnectionRules,
  getVisualPipeline,
  listVisualPipelineVersions,
  updateVisualPipeline,
} from "@/api/visualPipelines";
import { extractApiErrorMessage } from "@/api/client";
import { Button } from "@/components/Button";
import { StatusBadge } from "@/components/StatusBadge";
import { ErrorState, LoadingState } from "@/components/Pagination";
import { VpComponentPalette } from "@/components/visualPipeline/VpComponentPalette";
import { buildNodeTypes } from "@/components/visualPipeline/VpFlowNode";
import { VpGraphStatusPanel } from "@/components/visualPipeline/VpGraphStatusPanel";
import { VpNodeInspector } from "@/components/visualPipeline/VpNodeInspector";
import { VpVersionHistoryModal } from "@/components/visualPipeline/VpVersionHistoryModal";
import { useToast } from "@/hooks/useToast";
import type { ComponentCatalogItem, ConnectionRule, VisualPipelineDetail, VisualPipelineVersion } from "@/types/visualPipeline";
import {
  defaultNodeData,
  findConnectionRuleWarning,
  flowToGraph,
  graphToFlow,
  newNodeId,
  serializeGraphBody,
} from "@/utils/visualPipelineGraph";

function StudioCanvasInner() {
  const { pipelineId = "" } = useParams<{ pipelineId: string }>();
  const navigate = useNavigate();
  const { showToast } = useToast();
  const { fitView } = useReactFlow();

  const [pipeline, setPipeline] = useState<VisualPipelineDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [catalogActive, setCatalogActive] = useState<ComponentCatalogItem[]>([]);
  const [catalogDisabled, setCatalogDisabled] = useState<ComponentCatalogItem[]>([]);
  const [catalogLoading, setCatalogLoading] = useState(true);
  const [catalogError, setCatalogError] = useState("");
  const [connectionRules, setConnectionRules] = useState<ConnectionRule[]>([]);
  const [nodes, setNodes, onNodesChange] = useNodesState<Node>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([]);
  const [viewport, setViewport] = useState({ x: 0, y: 0, zoom: 1 });
  const savedGraphRef = useRef("");
  const [lastSavedAt, setLastSavedAt] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [versionSaving, setVersionSaving] = useState(false);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [jsonExpanded, setJsonExpanded] = useState(false);
  const [versionsOpen, setVersionsOpen] = useState(false);
  const [versionsLoading, setVersionsLoading] = useState(false);
  const [versions, setVersions] = useState<VisualPipelineVersion[]>([]);

  const nodeTypes = useMemo(() => buildNodeTypes(), []);

  const loadPipeline = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const detail = await getVisualPipeline(pipelineId);
      setPipeline(detail);
      const { nodes: n, edges: e } = graphToFlow(detail.graph);
      setNodes(n);
      setEdges(e);
      setViewport(detail.graph?.viewport ?? { x: 0, y: 0, zoom: 1 });
      savedGraphRef.current = serializeGraphBody(detail.graph ?? { nodes: [], edges: [], viewport: { x: 0, y: 0, zoom: 1 } });
      setLastSavedAt(detail.updated_at ?? null);
    } catch (err) {
      setError(extractApiErrorMessage(err, "Visual Pipeline을 불러오지 못했습니다."));
    } finally {
      setLoading(false);
    }
  }, [pipelineId, setNodes, setEdges]);

  useEffect(() => {
    void loadPipeline();
  }, [loadPipeline]);

  useEffect(() => {
    (async () => {
      setCatalogLoading(true);
      setCatalogError("");
      try {
        const [cat, rules] = await Promise.all([getComponentCatalog(), getConnectionRules()]);
        setCatalogActive(cat.items.filter((c) => c.status === "ACTIVE"));
        setCatalogDisabled(cat.items.filter((c) => c.status === "DISABLED"));
        setConnectionRules(rules.items ?? []);
      } catch {
        setCatalogError("컴포넌트 카탈로그를 불러오지 못했습니다.");
      } finally {
        setCatalogLoading(false);
      }
    })();
  }, []);

  const currentGraph = useMemo(() => flowToGraph(nodes, edges, viewport), [nodes, edges, viewport]);

  const dirty = useMemo(() => serializeGraphBody(currentGraph) !== savedGraphRef.current, [currentGraph]);

  useEffect(() => {
    const handler = (e: BeforeUnloadEvent) => {
      if (dirty) {
        e.preventDefault();
        e.returnValue = "";
      }
    };
    window.addEventListener("beforeunload", handler);
    return () => window.removeEventListener("beforeunload", handler);
  }, [dirty]);

  const catalogMap = useMemo(() => {
    const m = new Map<string, ComponentCatalogItem>();
    for (const c of [...catalogActive, ...catalogDisabled]) m.set(c.component_type, c);
    return m;
  }, [catalogActive, catalogDisabled]);

  const selectedNode = useMemo(() => nodes.find((n) => n.id === selectedNodeId) ?? null, [nodes, selectedNodeId]);
  const selectedCatalog = selectedNode ? catalogMap.get(String(selectedNode.type)) ?? null : null;

  const onConnect: OnConnect = useCallback(
    (connection: Connection) => {
      const sourceNode = nodes.find((n) => n.id === connection.source);
      const targetNode = nodes.find((n) => n.id === connection.target);
      if (sourceNode && targetNode) {
        const warn = findConnectionRuleWarning(connectionRules, String(sourceNode.type), String(targetNode.type));
        if (warn) showToast("warning", warn);
      }
      setEdges((eds) => addEdge({ ...connection, type: "smoothstep" }, eds));
    },
    [nodes, connectionRules, setEdges, showToast],
  );

  const handleAddNode = (component: ComponentCatalogItem) => {
    const id = newNodeId();
    const offset = nodes.length * 24;
    const newNode: Node = {
      id,
      type: component.component_type,
      position: { x: 120 + offset, y: 80 + offset },
      data: {
        ...defaultNodeData(component.component_type, component.display_name),
        component_type: component.component_type,
        description: component.description,
        input_ports: component.input_ports.map((p) => p.port_id),
        output_ports: component.output_ports.map((p) => p.port_id),
      },
    };
    setNodes((nds) => [...nds, newNode]);
    setSelectedNodeId(id);
  };

  const handleLabelChange = (label: string) => {
    if (!selectedNodeId) return;
    setNodes((nds) => nds.map((n) => (n.id === selectedNodeId ? { ...n, data: { ...n.data, label } } : n)));
  };

  const handleDeleteNode = () => {
    if (!selectedNodeId) return;
    setNodes((nds) => nds.filter((n) => n.id !== selectedNodeId));
    setEdges((eds) => eds.filter((e) => e.source !== selectedNodeId && e.target !== selectedNodeId));
    setSelectedNodeId(null);
  };

  const saveGraph = async (opts?: { silent?: boolean }) => {
    if (!pipeline) return;
    const silent = opts?.silent === true;
    if (!silent) setSaving(true);
    try {
      const graph = flowToGraph(nodes, edges, viewport);
      const updated = await updateVisualPipeline(pipelineId, {
        graph,
        create_version: false,
      });
      setPipeline(updated);
      savedGraphRef.current = serializeGraphBody(graph);
      setLastSavedAt(updated.updated_at ?? new Date().toISOString());
      if (!silent) {
        showToast("success", "현재 Graph가 저장되었습니다.");
      }
    } catch (err) {
      showToast("error", extractApiErrorMessage(err, "Graph 저장에 실패했습니다."));
      throw err;
    } finally {
      if (!silent) setSaving(false);
    }
  };

  const handleSave = async () => {
    try {
      await saveGraph({ silent: false });
    } catch {
      // toast already shown in saveGraph
    }
  };

  const handleVersionSave = async () => {
    setVersionSaving(true);
    try {
      if (dirty) {
        await saveGraph({ silent: true });
      }
      await createVisualPipelineVersion(pipelineId, "manual snapshot");
      showToast("success", "현재 Graph가 version snapshot으로 저장되었습니다.");
      setVersionsOpen(true);
      setVersionsLoading(true);
      const list = await listVisualPipelineVersions(pipelineId);
      setVersions(list.items);
      setVersionsLoading(false);
    } catch (err) {
      showToast("error", extractApiErrorMessage(err, "Version 저장에 실패했습니다."));
    } finally {
      setVersionSaving(false);
    }
  };

  const openVersions = async () => {
    setVersionsOpen(true);
    setVersionsLoading(true);
    try {
      const list = await listVisualPipelineVersions(pipelineId);
      setVersions(list.items);
    } catch {
      showToast("error", "Version 목록을 불러오지 못했습니다.");
    } finally {
      setVersionsLoading(false);
    }
  };

  const goList = () => {
    if (dirty && !window.confirm("저장하지 않은 변경 사항이 있습니다. 목록으로 이동할까요?")) return;
    navigate("/visual-pipelines");
  };

  if (loading) return <LoadingState />;
  if (error) return <ErrorState message={error} onRetry={() => void loadPipeline()} />;
  if (!pipeline) return null;

  return (
    <div className="-m-6 p-6 min-h-[calc(100vh-4rem)] flex flex-col">
      <div className="bg-white border border-slate-200 rounded-lg px-3 py-2 flex flex-wrap items-center justify-between gap-2 mb-3">
        <div className="flex items-center gap-2 flex-wrap">
          <Button variant="ghost" icon={<ChevronLeft className="w-4 h-4" />} onClick={goList}>목록</Button>
          <span className="text-sm font-semibold text-slate-800 truncate max-w-[240px]">{pipeline.pipeline_name}</span>
          <StatusBadge status={pipeline.status} />
          {dirty && <span className="text-[10px] text-amber-600 font-medium">● 저장되지 않음</span>}
          {!dirty && lastSavedAt && <span className="text-[10px] text-emerald-600">✓ 저장됨</span>}
          {saving && <span className="text-[10px] text-blue-600 animate-pulse">저장 중…</span>}
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          <Button
            icon={<Save className="w-4 h-4" />}
            onClick={() => void handleSave()}
            disabled={saving || !dirty}
            title="현재 작업본 Graph를 저장합니다. version snapshot은 만들지 않습니다."
          >
            저장
          </Button>
          <Button
            variant="secondary"
            icon={<History className="w-4 h-4" />}
            onClick={() => void handleVersionSave()}
            disabled={versionSaving}
            title="현재 Graph를 명시적 version snapshot으로 남깁니다."
          >
            버전 저장
          </Button>
          <Button variant="secondary" icon={<Maximize2 className="w-4 h-4" />} onClick={() => fitView({ padding: 0.2 })}>Fit View</Button>
          <Button variant="secondary" onClick={() => void openVersions()}>이력</Button>
          <button type="button" disabled title="현재 단계에서는 Compile/Run을 지원하지 않습니다." className="inline-flex items-center gap-1 px-2 py-1.5 bg-slate-100 text-slate-400 text-xs font-medium rounded cursor-not-allowed">
            <Zap className="w-3 h-3" /> Compile
          </button>
          <button type="button" disabled title="현재 단계에서는 Compile/Run을 지원하지 않습니다." className="inline-flex items-center gap-1 px-2 py-1.5 bg-slate-100 text-slate-400 text-xs font-medium rounded cursor-not-allowed">
            <Play className="w-3 h-3" /> Run Now
          </button>
          <button type="button" disabled className="inline-flex items-center gap-1 px-2 py-1.5 bg-slate-100 text-slate-400 text-xs font-medium rounded cursor-not-allowed">
            <Clock className="w-3 h-3" /> 스케줄 활성화
          </button>
        </div>
      </div>

      <div className="flex gap-3 flex-1 min-h-[480px]">
        <VpComponentPalette active={catalogActive} disabled={catalogDisabled} loading={catalogLoading} error={catalogError} onAdd={handleAddNode} />
        <div className="flex-1 bg-white border border-slate-200 rounded-lg overflow-hidden min-h-[480px]">
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onConnect={onConnect}
            nodeTypes={nodeTypes}
            onSelectionChange={({ nodes: sel }) => setSelectedNodeId(sel[0]?.id ?? null)}
            onMoveEnd={(_, vp) => setViewport({ x: vp.x, y: vp.y, zoom: vp.zoom })}
            fitView
            deleteKeyCode={["Backspace", "Delete"]}
          >
            <Background gap={20} size={1} />
            <Controls />
            <MiniMap nodeColor={() => "#94a3b8"} zoomable pannable />
            <Panel position="top-left" className="text-[10px] text-slate-400 bg-white/80 px-2 py-1 rounded border">Canvas · React Flow</Panel>
          </ReactFlow>
        </div>
        <VpNodeInspector node={selectedNode} catalogItem={selectedCatalog} onLabelChange={handleLabelChange} onDelete={handleDeleteNode} />
      </div>

      <VpGraphStatusPanel pipeline={pipeline} graph={currentGraph} dirty={dirty} lastSavedAt={lastSavedAt} expanded={jsonExpanded} onToggle={() => setJsonExpanded((v) => !v)} />
      <VpVersionHistoryModal open={versionsOpen} loading={versionsLoading} versions={versions} onClose={() => setVersionsOpen(false)} />
    </div>
  );
}

export default function VisualPipelineStudioPage() {
  return (
    <ReactFlowProvider>
      <StudioCanvasInner />
    </ReactFlowProvider>
  );
}
