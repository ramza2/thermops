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
  ShieldCheck,
  Zap,
} from "lucide-react";
import {
  createVisualPipelineVersion,
  getComponentCatalog,
  getConnectionRules,
  getVisualPipeline,
  listVisualPipelineVersions,
  updateVisualPipeline,
  validateVisualPipelineGraph,
} from "@/api/visualPipelines";
import { extractApiErrorMessage } from "@/api/client";
import { Button } from "@/components/Button";
import { StatusBadge } from "@/components/StatusBadge";
import { ErrorState, LoadingState } from "@/components/Pagination";
import { VpComponentPalette } from "@/components/visualPipeline/VpComponentPalette";
import { buildNodeTypes } from "@/components/visualPipeline/VpFlowNode";
import { VpGraphStatusPanel } from "@/components/visualPipeline/VpGraphStatusPanel";
import { VpNodeInspector } from "@/components/visualPipeline/VpNodeInspector";
import { VpValidationPanel } from "@/components/visualPipeline/VpValidationPanel";
import { VpVersionHistoryModal } from "@/components/visualPipeline/VpVersionHistoryModal";
import { useToast } from "@/hooks/useToast";
import type {
  ComponentCatalogItem,
  ConnectionRule,
  VisualPipelineDetail,
  VisualPipelineValidationResponse,
  VisualPipelineVersion,
} from "@/types/visualPipeline";
import {
  defaultNodeData,
  enrichEdgeWithPortMetadata,
  findConnectionRuleWarning,
  flowToGraph,
  graphToFlow,
  newNodeId,
  NODE_STYLE,
  parsePortHandleId,
  serializeGraphBody,
} from "@/utils/visualPipelineGraph";
import { applyConfigValidationCache, applyNodeConfigPatch, fieldWarningsFromConfigIssues } from "@/utils/visualPipelineNodeConfig";

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
  const [graphSaveEpoch, setGraphSaveEpoch] = useState(0);
  const [lastSavedAt, setLastSavedAt] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [versionSaving, setVersionSaving] = useState(false);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [jsonExpanded, setJsonExpanded] = useState(false);
  const [versionsOpen, setVersionsOpen] = useState(false);
  const [versionsLoading, setVersionsLoading] = useState(false);
  const [versions, setVersions] = useState<VisualPipelineVersion[]>([]);
  const [validating, setValidating] = useState(false);
  const [validationResult, setValidationResult] = useState<VisualPipelineValidationResponse | null>(null);
  const [validationExpanded, setValidationExpanded] = useState(true);

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
      setGraphSaveEpoch((e) => e + 1);
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

  const dirty = useMemo(
    () => serializeGraphBody(currentGraph) !== savedGraphRef.current,
    [currentGraph, graphSaveEpoch],
  );

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
  const selectedConfigStatus = useMemo(() => {
    if (!selectedNode) return "NOT_VALIDATED";
    const raw = (selectedNode.data as { config?: { validation?: { status?: string } } } | undefined)?.config
      ?.validation?.status;
    if (raw === "VALID") return "OK";
    if (raw === "INVALID") return "ERROR";
    return raw ?? "NOT_VALIDATED";
  }, [selectedNode]);
  const fieldWarnings = useMemo(() => {
    if (!validationResult || selectedConfigStatus === "NOT_VALIDATED" || selectedConfigStatus === "STALE") {
      return {};
    }
    return fieldWarningsFromConfigIssues(validationResult.issues ?? [], selectedNodeId);
  }, [validationResult, selectedNodeId, selectedConfigStatus]);

  const onConnect: OnConnect = useCallback(
    (connection: Connection) => {
      const sourceNode = nodes.find((n) => n.id === connection.source);
      const targetNode = nodes.find((n) => n.id === connection.target);
      const enriched = enrichEdgeWithPortMetadata(connection, nodes);
      const sourcePort = parsePortHandleId(enriched.sourceHandle).portName;
      const targetPort = parsePortHandleId(enriched.targetHandle).portName;
      if (sourceNode && targetNode) {
        const warn = findConnectionRuleWarning(
          connectionRules,
          String(sourceNode.type),
          String(targetNode.type),
          sourcePort,
          targetPort,
        );
        if (warn) showToast("warning", warn);
      }
      setEdges((eds) => addEdge(enriched, eds));
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

  const handleNodeConfigChange = (patch: Record<string, unknown>) => {
    if (!selectedNodeId) return;
    setNodes((nds) => nds.map((n) => (n.id === selectedNodeId ? applyNodeConfigPatch(n, patch) : n)));
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
      setGraphSaveEpoch((e) => e + 1);
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

  const handleValidate = async () => {
    setValidating(true);
    try {
      const graph = flowToGraph(nodes, edges, viewport);
      const result = await validateVisualPipelineGraph({
        graph,
        pipeline_id: pipelineId,
        validation_level: "BASIC",
      });
      setValidationResult(result);
      setValidationExpanded(true);
      setNodes((nds) => applyConfigValidationCache(nds, result.issues ?? []));
      if (result.severity === "ERROR") {
        showToast("error", "Graph 검증 오류가 있습니다.");
      } else if (result.severity === "WARNING") {
        showToast("warning", "Graph 검증 경고가 있습니다.");
      } else {
        showToast("success", "Graph 검증을 통과했습니다.");
      }
    } catch (err) {
      showToast("error", extractApiErrorMessage(err, "Graph 검증에 실패했습니다."));
    } finally {
      setValidating(false);
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
    <div
      className="-m-6 p-4 md:p-5 min-h-[calc(100vh-4rem)] flex flex-col bg-slate-100/60"
      data-testid="visual-pipeline-studio-page"
    >
      <div
        className="bg-white border border-slate-200 rounded-lg shadow-sm px-3 py-2.5 flex flex-wrap items-center justify-between gap-2 mb-3"
        data-testid="visual-pipeline-toolbar"
      >
        <div className="flex items-center gap-2 flex-wrap min-w-0">
          <Button variant="ghost" icon={<ChevronLeft className="w-4 h-4" />} onClick={goList}>목록</Button>
          <span className="w-px h-4 bg-slate-200 shrink-0" aria-hidden />
          <span
            className="text-sm font-semibold text-slate-800 truncate max-w-[260px]"
            data-testid="visual-pipeline-name"
          >
            {pipeline.pipeline_name}
          </span>
          <StatusBadge status={pipeline.status} />
          <span className="inline-flex items-center text-[9px] font-bold uppercase tracking-wide bg-violet-50 text-violet-700 border border-violet-200 rounded px-1.5 py-0.5">
            PoC
          </span>
          {dirty && (
            <span className="text-[10px] text-amber-700 font-medium bg-amber-50 border border-amber-100 rounded-full px-2 py-0.5">
              ● 저장되지 않음
            </span>
          )}
          {!dirty && lastSavedAt && (
            <span className="text-[10px] text-emerald-700 font-medium bg-emerald-50 border border-emerald-100 rounded-full px-2 py-0.5">
              ✓ 저장됨
            </span>
          )}
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
          <Button variant="secondary" icon={<Maximize2 className="w-4 h-4" />} onClick={() => fitView({ padding: 0.2 })}>
            Fit View
          </Button>
          <Button variant="secondary" onClick={() => void openVersions()}>이력</Button>
          <Button
            variant="secondary"
            icon={<ShieldCheck className="w-4 h-4" />}
            onClick={() => void handleValidate()}
            disabled={validating}
            title="현재 Canvas Graph를 BASIC 수준으로 검증합니다. 저장을 차단하지 않습니다."
            data-testid="visual-pipeline-validate-button"
          >
            {validating ? "검증 중…" : "Graph 검증"}
          </Button>
          <span className="w-px h-4 bg-slate-200 shrink-0 mx-0.5" aria-hidden />
          <button
            type="button"
            disabled
            title="현재 단계에서는 Compile/Run을 지원하지 않습니다."
            className="inline-flex items-center gap-1.5 px-2.5 py-1.5 bg-slate-100 text-slate-400 text-xs font-medium rounded-md cursor-not-allowed border border-slate-200"
          >
            <Zap className="w-3 h-3" /> Compile
            <span className="text-[9px] bg-slate-300 text-slate-600 px-1 rounded font-bold">Soon</span>
          </button>
          <button
            type="button"
            disabled
            title="현재 단계에서는 Compile/Run을 지원하지 않습니다."
            className="inline-flex items-center gap-1.5 px-2.5 py-1.5 bg-slate-100 text-slate-400 text-xs font-medium rounded-md cursor-not-allowed border border-slate-200"
          >
            <Play className="w-3 h-3" /> Run Now
            <span className="text-[9px] bg-slate-300 text-slate-600 px-1 rounded font-bold">Soon</span>
          </button>
          <button
            type="button"
            disabled
            title="현재 단계에서는 스케줄 활성화를 지원하지 않습니다."
            className="inline-flex items-center gap-1.5 px-2.5 py-1.5 bg-slate-100 text-slate-400 text-xs font-medium rounded-md cursor-not-allowed border border-slate-200"
          >
            <Clock className="w-3 h-3" /> 스케줄 활성화
            <span className="text-[9px] bg-slate-300 text-slate-600 px-1 rounded font-bold">Soon</span>
          </button>
        </div>
      </div>

      <div className="flex gap-3 flex-1 min-h-[620px]">
        <VpComponentPalette
          active={catalogActive}
          disabled={catalogDisabled}
          loading={catalogLoading}
          error={catalogError}
          onAdd={handleAddNode}
        />
        <div
          className="flex-1 bg-white border border-slate-200 rounded-lg shadow-sm overflow-hidden min-h-[620px] relative"
          data-testid="visual-pipeline-canvas"
        >
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
            className="bg-slate-50"
            style={{
              backgroundImage: "radial-gradient(circle, #e2e8f0 1px, transparent 1px)",
              backgroundSize: "20px 20px",
            }}
          >
            <Background gap={20} size={1} color="#cbd5e1" />
            <Controls className="!shadow-sm !border-slate-200 !rounded-md overflow-hidden" />
            <MiniMap
              nodeColor={(n) => NODE_STYLE[String(n.type)]?.minimap ?? "#94a3b8"}
              maskColor="rgba(148,163,184,0.15)"
              zoomable
              pannable
              className="!shadow-sm !border-slate-200 !rounded-md"
            />
            <Panel position="top-left" className="m-2">
              <div className="flex items-center gap-3 bg-white/95 border border-slate-200 rounded-md shadow-sm px-2.5 py-1.5 text-[10px] text-slate-500">
                <span className="font-bold uppercase tracking-wider text-slate-600">Canvas</span>
                <span className="font-mono">zoom {Math.round(viewport.zoom * 100)}%</span>
                <span className="w-px h-3 bg-slate-200" />
                <span className="inline-flex items-center gap-1">
                  <span className="w-2 h-2 rounded-full bg-blue-500" /> 선택
                </span>
                <span className="inline-flex items-center gap-1">
                  <span className="w-2 h-2 rounded-full bg-slate-300" /> 일반
                </span>
              </div>
            </Panel>
            {nodes.length === 0 && (
              <Panel position="top-center" className="m-8 pointer-events-none">
                <div className="bg-white/95 border border-dashed border-slate-300 rounded-lg shadow-sm px-6 py-5 text-center max-w-sm">
                  <p className="text-sm font-medium text-slate-700">왼쪽 팔레트에서 노드를 추가해 주세요.</p>
                  <p className="text-xs text-slate-500 mt-1.5 leading-relaxed">
                    REST API Source부터 추가한 뒤 Transform · Upsert Load를 연결하면 기본 적재 흐름을 구성할 수 있습니다.
                  </p>
                </div>
              </Panel>
            )}
          </ReactFlow>
        </div>
        <VpNodeInspector
          node={selectedNode}
          catalogItem={selectedCatalog}
          fieldWarnings={fieldWarnings}
          onLabelChange={handleLabelChange}
          onConfigChange={handleNodeConfigChange}
          onDelete={handleDeleteNode}
        />
      </div>

      <VpGraphStatusPanel
        pipeline={pipeline}
        graph={currentGraph}
        dirty={dirty}
        lastSavedAt={lastSavedAt}
        expanded={jsonExpanded}
        onToggle={() => setJsonExpanded((v) => !v)}
      />
      <VpValidationPanel
        result={validationResult}
        loading={validating}
        expanded={validationExpanded}
        onToggle={() => setValidationExpanded((v) => !v)}
        onSelectNode={(nodeId) => setSelectedNodeId(nodeId)}
      />
      <VpVersionHistoryModal
        open={versionsOpen}
        loading={versionsLoading}
        versions={versions}
        onClose={() => setVersionsOpen(false)}
      />
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
