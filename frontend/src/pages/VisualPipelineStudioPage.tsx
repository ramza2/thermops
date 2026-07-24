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
  Database,
  History,
  Layers,
  Maximize2,
  Play,
  Save,
  ShieldCheck,
  Zap,
} from "lucide-react";
import {
  createVisualPipelineVersion,
  activateVisualPipelineSchedule,
  compileVisualPipeline,
  compileVisualPipelinePreview,
  cancelVisualPipelineRun,
  deactivateVisualPipelineSchedule,
  getComponentCatalog,
  getConnectionRules,
  getCurrentVisualPipelineScheduleActivation,
  getLatestVisualPipelineRun,
  getVisualPipeline,
  getVisualPipelineCompileResult,
  getVisualPipelineMaterializationResult,
  getVisualPipelineRun,
  listVisualPipelineVersions,
  materializeVisualPipeline,
  pauseVisualPipelineScheduleActivation,
  resumeVisualPipelineScheduleActivation,
  runVisualPipeline,
  updateVisualPipeline,
  validateVisualPipelineGraph,
} from "@/api/visualPipelines";
import { extractApiErrorMessage } from "@/api/client";
import { Button } from "@/components/Button";
import { StatusBadge } from "@/components/StatusBadge";
import { ErrorState, LoadingState } from "@/components/Pagination";
import { VpCompilePanel } from "@/components/visualPipeline/VpCompilePanel";
import { VpMaterializationPanel } from "@/components/visualPipeline/VpMaterializationPanel";
import { VpComponentPalette } from "@/components/visualPipeline/VpComponentPalette";
import { buildNodeTypes } from "@/components/visualPipeline/VpFlowNode";
import { VpGraphStatusPanel } from "@/components/visualPipeline/VpGraphStatusPanel";
import { VpNodeInspector } from "@/components/visualPipeline/VpNodeInspector";
import { VpRunPanel } from "@/components/visualPipeline/VpRunPanel";
import { VpScheduleActivationPanel } from "@/components/visualPipeline/VpScheduleActivationPanel";
import { VpValidationPanel } from "@/components/visualPipeline/VpValidationPanel";
import { VpVersionHistoryModal } from "@/components/visualPipeline/VpVersionHistoryModal";
import { useToast } from "@/hooks/useToast";
import type {
  ComponentCatalogItem,
  ConnectionRule,
  VisualPipelineCompileResponse,
  VisualPipelineDetail,
  VisualPipelineMaterializationResponse,
  VisualPipelineRunResponse,
  VisualPipelineScheduleActivationResponse,
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

const RUN_ACTIVE_STATUSES = new Set(["PENDING", "RUNNING"]);
const RUN_TERMINAL_STATUSES = new Set(["SUCCESS", "FAILED", "PARTIAL", "CANCELLED"]);
const RUN_POLL_INTERVAL_MS = 1000;
const RUN_POLL_TIMEOUT_MS = 90_000;
const RUN_POLL_TIMEOUT_MESSAGE =
  "상태 확인 시간이 초과되었습니다. 실행은 계속 진행 중일 수 있으니 새로고침하거나 실행 이력을 확인하세요.";

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
  const [compiling, setCompiling] = useState(false);
  const [compileResult, setCompileResult] = useState<VisualPipelineCompileResponse | null>(null);
  const [compileError, setCompileError] = useState<string | null>(null);
  const [compileExpanded, setCompileExpanded] = useState(true);
  const [compileLoadingLatest, setCompileLoadingLatest] = useState(false);
  const [materializing, setMaterializing] = useState(false);
  const [materializationResult, setMaterializationResult] = useState<VisualPipelineMaterializationResponse | null>(
    null,
  );
  const [materializationError, setMaterializationError] = useState<string | null>(null);
  const [materializationExpanded, setMaterializationExpanded] = useState(true);
  const [materializationLoadingLatest, setMaterializationLoadingLatest] = useState(false);
  const [running, setRunning] = useState(false);
  const [runResult, setRunResult] = useState<VisualPipelineRunResponse | null>(null);
  const [runError, setRunError] = useState<string | null>(null);
  const [runPollError, setRunPollError] = useState<string | null>(null);
  const [runExpanded, setRunExpanded] = useState(true);
  const [runLoadingLatest, setRunLoadingLatest] = useState(false);
  const [runPolling, setRunPolling] = useState(false);
  const [activationResult, setActivationResult] = useState<VisualPipelineScheduleActivationResponse | null>(
    null,
  );
  const [activationError, setActivationError] = useState<string | null>(null);
  const [activationExpanded, setActivationExpanded] = useState(true);
  const [activationLoadingLatest, setActivationLoadingLatest] = useState(false);
  const [activating, setActivating] = useState(false);
  const [deactivating, setDeactivating] = useState(false);
  const [pausing, setPausing] = useState(false);
  const [resuming, setResuming] = useState(false);
  const [cancellingRun, setCancellingRun] = useState(false);
  const runPollGenRef = useRef(0);

  const nodeTypes = useMemo(() => buildNodeTypes(), []);

  const stopRunPolling = useCallback(() => {
    runPollGenRef.current += 1;
    setRunPolling(false);
  }, []);

  const startRunPolling = useCallback(
    (runId: string) => {
      const gen = ++runPollGenRef.current;
      setRunPolling(true);
      setRunPollError(null);
      const startedAt = Date.now();

      const tick = async () => {
        if (runPollGenRef.current !== gen) return;
        if (Date.now() - startedAt > RUN_POLL_TIMEOUT_MS) {
          setRunPollError(RUN_POLL_TIMEOUT_MESSAGE);
          setRunPolling(false);
          return;
        }
        try {
          const detail = await getVisualPipelineRun(pipelineId, runId);
          if (runPollGenRef.current !== gen) return;
          setRunResult(detail);
          setRunPollError(null);
          if (RUN_TERMINAL_STATUSES.has(String(detail.run_status))) {
            setRunPolling(false);
            return;
          }
        } catch (err) {
          if (runPollGenRef.current !== gen) return;
          setRunPollError(extractApiErrorMessage(err, "실행 상태 조회에 실패했습니다."));
        }
        if (runPollGenRef.current === gen) {
          window.setTimeout(() => {
            void tick();
          }, RUN_POLL_INTERVAL_MS);
        }
      };

      void tick();
    },
    [pipelineId],
  );

  const loadLatestRunResult = useCallback(
    async (id: string) => {
      setRunLoadingLatest(true);
      setRunError(null);
      try {
        const latest = await getLatestVisualPipelineRun(id);
        setRunResult(latest);
        if (latest && RUN_ACTIVE_STATUSES.has(String(latest.run_status))) {
          startRunPolling(latest.visual_run_id);
        }
      } catch (err) {
        setRunError(extractApiErrorMessage(err, "최근 Manual Run 결과를 불러오지 못했습니다."));
      } finally {
        setRunLoadingLatest(false);
      }
    },
    [startRunPolling],
  );

  const loadLatestMaterializationResult = useCallback(async (id: string) => {
    setMaterializationLoadingLatest(true);
    setMaterializationError(null);
    try {
      const latest = await getVisualPipelineMaterializationResult(id);
      setMaterializationResult(latest);
    } catch (err) {
      setMaterializationError(extractApiErrorMessage(err, "최근 Materialization 결과를 불러오지 못했습니다."));
    } finally {
      setMaterializationLoadingLatest(false);
    }
  }, []);

  const loadLatestCompileResult = useCallback(async (id: string) => {
    setCompileLoadingLatest(true);
    setCompileError(null);
    try {
      const latest = await getVisualPipelineCompileResult(id);
      setCompileResult(latest);
    } catch (err) {
      setCompileError(extractApiErrorMessage(err, "최근 컴파일 결과를 불러오지 못했습니다."));
    } finally {
      setCompileLoadingLatest(false);
    }
  }, []);

  const loadLatestActivation = useCallback(async (id: string) => {
    setActivationLoadingLatest(true);
    setActivationError(null);
    try {
      const latest = await getCurrentVisualPipelineScheduleActivation(id);
      setActivationResult(latest);
    } catch (err) {
      setActivationError(extractApiErrorMessage(err, "최근 Schedule Activation을 불러오지 못했습니다."));
    } finally {
      setActivationLoadingLatest(false);
    }
  }, []);

  const loadPipeline = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const detail = await getVisualPipeline(pipelineId);
      setPipeline(detail);
      const { nodes: n, edges: e } = graphToFlow(detail.graph);
      const vp = detail.graph?.viewport ?? { x: 0, y: 0, zoom: 1 };
      setNodes(n);
      setEdges(e);
      setViewport(vp);
      // Baseline must match canvas round-trip (normalize), not raw API JSON.
      savedGraphRef.current = serializeGraphBody(flowToGraph(n, e, vp));
      setGraphSaveEpoch((epoch) => epoch + 1);
      setLastSavedAt(detail.updated_at ?? null);
      void loadLatestCompileResult(pipelineId);
      void loadLatestMaterializationResult(pipelineId);
      void loadLatestActivation(pipelineId);
      void loadLatestRunResult(pipelineId);
    } catch (err) {
      setError(extractApiErrorMessage(err, "Visual Pipeline을 불러오지 못했습니다."));
    } finally {
      setLoading(false);
    }
  }, [
    pipelineId,
    setNodes,
    setEdges,
    loadLatestCompileResult,
    loadLatestMaterializationResult,
    loadLatestActivation,
    loadLatestRunResult,
  ]);

  useEffect(() => {
    void loadPipeline();
  }, [loadPipeline]);

  useEffect(() => {
    return () => {
      runPollGenRef.current += 1;
    };
  }, []);

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

  const handleCompilePreview = async () => {
    if (!pipelineId) return;
    if (dirty) {
      showToast(
        "warning",
        "저장된 그래프 기준으로 미리보기합니다. 현재 미저장 변경은 반영되지 않습니다.",
      );
    }
    setCompiling(true);
    setCompileError(null);
    setCompileExpanded(true);
    try {
      const result = await compileVisualPipelinePreview(pipelineId);
      setCompileResult(result);
      if (result.compile_status === "SUCCESS") {
        showToast("success", "컴파일 미리보기가 생성되었습니다.");
      } else {
        showToast("error", "컴파일 미리보기에 실패했습니다. 이슈를 확인하세요.");
      }
    } catch (err) {
      setCompileError(extractApiErrorMessage(err, "컴파일 미리보기에 실패했습니다."));
      showToast("error", extractApiErrorMessage(err, "컴파일 미리보기에 실패했습니다."));
    } finally {
      setCompiling(false);
    }
  };

  const handleCompile = async () => {
    if (!pipelineId || dirty) return;
    setCompiling(true);
    setCompileError(null);
    setCompileExpanded(true);
    try {
      const result = await compileVisualPipeline(pipelineId);
      setCompileResult(result);
      try {
        const detail = await getVisualPipeline(pipelineId);
        setPipeline(detail);
        setLastSavedAt(detail.updated_at ?? null);
      } catch {
        // panel still shows compile result even if detail refresh fails
      }
      if (result.compile_status === "SUCCESS") {
        showToast("success", "컴파일 결과가 저장되었습니다. (실행/스케줄 활성화 아님)");
      } else {
        showToast("error", "컴파일에 실패했습니다. 이슈를 확인하세요.");
      }
    } catch (err) {
      setCompileError(extractApiErrorMessage(err, "컴파일에 실패했습니다."));
      showToast("error", extractApiErrorMessage(err, "컴파일에 실패했습니다."));
    } finally {
      setCompiling(false);
    }
  };

  const canMaterialize = useMemo(() => {
    if (dirty || compiling || materializing || running || runPolling || activating || deactivating) return false;
    if (compileResult?.compile_status !== "SUCCESS") return false;
    if (!compileResult.persisted) return false;
    if (pipeline?.current_sync_status !== "IN_SYNC") return false;
    return true;
  }, [
    dirty,
    compiling,
    materializing,
    running,
    runPolling,
    activating,
    deactivating,
    compileResult,
    pipeline?.current_sync_status,
  ]);

  const isRunActive = Boolean(
    running ||
      runPolling ||
      (runResult && RUN_ACTIVE_STATUSES.has(String(runResult.run_status))),
  );

  const canRun = useMemo(() => {
    if (dirty || compiling || materializing || running || runPolling || activating || deactivating) return false;
    if (compileResult?.compile_status !== "SUCCESS") return false;
    if (!compileResult.persisted) return false;
    if (pipeline?.current_sync_status !== "IN_SYNC") return false;
    if (materializationResult?.materialization_status !== "SUCCESS") return false;
    if (runResult && RUN_ACTIVE_STATUSES.has(String(runResult.run_status))) return false;
    return true;
  }, [
    dirty,
    compiling,
    materializing,
    running,
    runPolling,
    activating,
    deactivating,
    compileResult,
    pipeline?.current_sync_status,
    materializationResult,
    runResult,
  ]);

  const hasMaterializedSchedule = Boolean(
    materializationResult?.objects &&
      typeof materializationResult.objects === "object" &&
      (materializationResult.objects as Record<string, unknown>).schedule_id,
  );

  const canActivate = useMemo(() => {
    if (
      dirty ||
      compiling ||
      materializing ||
      running ||
      runPolling ||
      activating ||
      deactivating ||
      pausing ||
      resuming
    ) {
      return false;
    }
    if (compileResult?.compile_status !== "SUCCESS" || !compileResult.persisted) return false;
    if (pipeline?.current_sync_status !== "IN_SYNC") return false;
    if (materializationResult?.materialization_status !== "SUCCESS") return false;
    if (!hasMaterializedSchedule) return false;
    if (activationResult?.activation_status === "ACTIVE") return false;
    if (activationResult?.activation_status === "PAUSED") return false;
    return true;
  }, [
    dirty,
    compiling,
    materializing,
    running,
    runPolling,
    activating,
    deactivating,
    pausing,
    resuming,
    compileResult,
    pipeline?.current_sync_status,
    materializationResult,
    hasMaterializedSchedule,
    activationResult,
  ]);

  const activateDisabledReason = useMemo(() => {
    if (canActivate) {
      return "스케줄 활성화를 수행합니다. due 시 PENDING scheduled run이 생성될 수 있습니다.";
    }
    if (dirty) return "미저장 변경사항이 있습니다. 저장 후 Compile → R10 설정 반영을 완료하세요.";
    if (compiling || materializing || running || activating || deactivating || pausing || resuming) {
      return "다른 작업이 진행 중입니다.";
    }
    if (activationResult?.activation_status === "ACTIVE") return "이미 활성화된 스케줄이 있습니다.";
    if (activationResult?.activation_status === "PAUSED") return "일시중지된 스케줄이 있습니다. Resume 또는 Deactivate하세요.";
    if (compileResult?.compile_status !== "SUCCESS" || !compileResult?.persisted) {
      return "persisted SUCCESS Compile이 필요합니다.";
    }
    if (pipeline?.current_sync_status !== "IN_SYNC") return "컴파일 동기화 상태(IN_SYNC)가 필요합니다.";
    if (materializationResult?.materialization_status !== "SUCCESS") {
      return "SUCCESS Materialization(R10 설정 반영)이 필요합니다.";
    }
    if (!hasMaterializedSchedule) return "Materialized CRON schedule이 없습니다.";
    return "Schedule Activation 조건을 충족하지 않습니다.";
  }, [
    canActivate,
    dirty,
    compiling,
    materializing,
    running,
    activating,
    deactivating,
    pausing,
    resuming,
    activationResult,
    compileResult,
    pipeline?.current_sync_status,
    materializationResult,
    hasMaterializedSchedule,
  ]);

  const runDisabledReason = useMemo(() => {
    if (canRun) {
      return "Manual Run을 실행합니다. 실제 REST 호출과 대상 테이블 적재가 발생할 수 있습니다. 스케줄은 활성화하지 않습니다.";
    }
    if (dirty) return "미저장 변경사항이 있습니다. 저장 후 Compile → R10 설정 반영을 완료하세요.";
    if (compiling || materializing || running) return "다른 작업이 진행 중입니다.";
    if (isRunActive) return "이미 실행 중인 Manual Run이 있습니다.";
    if (compileResult?.compile_status !== "SUCCESS" || !compileResult?.persisted) {
      return "persisted SUCCESS Compile이 필요합니다.";
    }
    if (pipeline?.current_sync_status !== "IN_SYNC") return "컴파일 동기화 상태(IN_SYNC)가 필요합니다.";
    if (materializationResult?.materialization_status !== "SUCCESS") {
      return "SUCCESS Materialization(R10 설정 반영)이 필요합니다.";
    }
    return "Manual Run 조건을 충족하지 않습니다.";
  }, [
    canRun,
    dirty,
    compiling,
    materializing,
    running,
    isRunActive,
    compileResult,
    pipeline?.current_sync_status,
    materializationResult,
  ]);

  const handleMaterialize = async () => {
    if (!pipelineId || !canMaterialize) return;
    const confirmed = window.confirm(
      "R10 설정 row를 생성/갱신합니다. 외부 API 호출, 적재 실행, 스케줄 활성화는 수행하지 않습니다.",
    );
    if (!confirmed) return;

    setMaterializing(true);
    setMaterializationError(null);
    setMaterializationExpanded(true);
    try {
      const result = await materializeVisualPipeline(pipelineId);
      setMaterializationResult(result);
      if (result.materialization_status === "SUCCESS") {
        showToast("success", "R10 설정이 반영되었습니다. (실행/스케줄 활성화 아님)");
      } else {
        showToast("error", "R10 설정 반영에 실패했습니다. 이슈를 확인하세요.");
      }
    } catch (err) {
      setMaterializationError(extractApiErrorMessage(err, "R10 설정 반영에 실패했습니다."));
      showToast("error", extractApiErrorMessage(err, "R10 설정 반영에 실패했습니다."));
    } finally {
      setMaterializing(false);
    }
  };

  const handleRunNow = async () => {
    if (!pipelineId || !canRun) return;
    const confirmed = window.confirm(
      "Manual Run을 실행합니다. 이 작업은 실제 REST API 호출과 대상 테이블 적재/갱신을 수행할 수 있습니다. 스케줄 활성화는 하지 않습니다. 계속 진행하시겠습니까?",
    );
    if (!confirmed) return;

    stopRunPolling();
    setRunning(true);
    setRunError(null);
    setRunPollError(null);
    setRunExpanded(true);
    try {
      const accepted = await runVisualPipeline(pipelineId, { mode: "MANUAL" });
      setRunResult(accepted);
      showToast("success", "Manual Run이 접수되었습니다. 상태를 확인합니다.");
      if (RUN_TERMINAL_STATUSES.has(String(accepted.run_status))) {
        setRunPolling(false);
      } else {
        startRunPolling(accepted.visual_run_id);
      }
    } catch (err) {
      const detail = extractApiErrorMessage(err, "Manual Run 요청에 실패했습니다.");
      if (detail === "RUN_CONCURRENT_RUN_EXISTS") {
        setRunError("이미 실행 중인 Run이 있습니다. 현재 실행 상태를 확인해 주세요.");
        showToast("error", "이미 실행 중인 Run이 있습니다. 현재 실행 상태를 확인해 주세요.");
        void loadLatestRunResult(pipelineId);
      } else {
        setRunError(detail);
        showToast("error", detail || "Manual Run 요청에 실패했습니다.");
      }
    } finally {
      setRunning(false);
    }
  };

  const handleActivateSchedule = async () => {
    if (!pipelineId || !canActivate) return;
    const confirmed = window.confirm(
      "스케줄 활성화를 수행합니다. 활성화 후 설정된 CRON 주기에 따라 자동 실행 Run이 생성될 수 있습니다. 실제 적재 실행은 VP run-worker가 처리합니다. 계속 진행하시겠습니까?",
    );
    if (!confirmed) return;

    setActivating(true);
    setActivationError(null);
    setActivationExpanded(true);
    try {
      const result = await activateVisualPipelineSchedule(pipelineId);
      setActivationResult(result);
      void loadLatestMaterializationResult(pipelineId);
      showToast("success", "스케줄이 활성화되었습니다. (run_load 미실행)");
    } catch (err) {
      const detail = extractApiErrorMessage(err, "스케줄 활성화에 실패했습니다.");
      setActivationError(detail);
      showToast("error", detail);
    } finally {
      setActivating(false);
    }
  };

  const handleDeactivateSchedule = async () => {
    if (!pipelineId || !activationResult?.activation_id) return;
    if (
      activationResult.activation_status !== "ACTIVE" &&
      activationResult.activation_status !== "PAUSED"
    ) {
      return;
    }
    const confirmed = window.confirm(
      "스케줄 활성화를 해제합니다. 이미 생성된 PENDING/RUNNING run은 유지됩니다. 계속하시겠습니까?",
    );
    if (!confirmed) return;

    setDeactivating(true);
    setActivationError(null);
    try {
      const result = await deactivateVisualPipelineSchedule(pipelineId, activationResult.activation_id);
      setActivationResult(result);
      void loadLatestMaterializationResult(pipelineId);
      showToast("success", "스케줄이 비활성화되었습니다.");
    } catch (err) {
      const detail = extractApiErrorMessage(err, "스케줄 비활성화에 실패했습니다.");
      setActivationError(detail);
      showToast("error", detail);
    } finally {
      setDeactivating(false);
    }
  };

  const handlePauseSchedule = async () => {
    if (!pipelineId || !activationResult?.activation_id) return;
    if (activationResult.activation_status !== "ACTIVE") return;
    const confirmed = window.confirm(
      "스케줄 자동 실행을 일시 중지합니다. 이미 생성된 Run은 취소되지 않습니다. 계속하시겠습니까?",
    );
    if (!confirmed) return;
    setPausing(true);
    setActivationError(null);
    try {
      const result = await pauseVisualPipelineScheduleActivation(
        pipelineId,
        activationResult.activation_id,
      );
      setActivationResult(result);
      void loadLatestMaterializationResult(pipelineId);
      showToast("success", "스케줄이 일시 중지되었습니다.");
    } catch (err) {
      const detail = extractApiErrorMessage(err, "스케줄 일시 중지에 실패했습니다.");
      setActivationError(detail);
      showToast("error", detail);
    } finally {
      setPausing(false);
    }
  };

  const handleResumeSchedule = async () => {
    if (!pipelineId || !activationResult?.activation_id) return;
    if (activationResult.activation_status !== "PAUSED") return;
    const confirmed = window.confirm(
      "스케줄 자동 실행을 재개합니다. 다음 실행 시각은 현재 시점 기준으로 다시 계산됩니다. 계속하시겠습니까?",
    );
    if (!confirmed) return;
    setResuming(true);
    setActivationError(null);
    try {
      const result = await resumeVisualPipelineScheduleActivation(
        pipelineId,
        activationResult.activation_id,
      );
      setActivationResult(result);
      void loadLatestMaterializationResult(pipelineId);
      showToast("success", "스케줄이 재개되었습니다.");
    } catch (err) {
      const detail = extractApiErrorMessage(err, "스케줄 재개에 실패했습니다.");
      setActivationError(detail);
      showToast("error", detail);
    } finally {
      setResuming(false);
    }
  };

  const handleCancelRun = async () => {
    if (!pipelineId || !runResult?.visual_run_id) return;
    if (runResult.run_status !== "PENDING") return;
    const confirmed = window.confirm(
      "아직 실행 대기 중인 Run을 취소합니다. 이미 실행 중인 Run은 중단할 수 없습니다. 계속하시겠습니까?",
    );
    if (!confirmed) return;
    setCancellingRun(true);
    setRunError(null);
    try {
      const result = await cancelVisualPipelineRun(pipelineId, runResult.visual_run_id);
      setRunResult(result);
      stopRunPolling();
      showToast("success", "대기 중인 Run이 취소되었습니다.");
    } catch (err) {
      const detail = extractApiErrorMessage(err, "Run 취소에 실패했습니다.");
      setRunError(detail);
      showToast("error", detail);
    } finally {
      setCancellingRun(false);
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
          <Button
            variant="secondary"
            icon={<Layers className="w-4 h-4" />}
            onClick={() => void handleCompilePreview()}
            disabled={compiling}
            title="저장된 그래프를 기준으로 실행 계획을 미리 생성합니다. DB 저장, 스케줄 활성화, 외부 API 호출은 수행하지 않습니다."
            data-testid="visual-pipeline-compile-preview-button"
          >
            {compiling ? "처리 중…" : "Compile Preview"}
          </Button>
          <Button
            variant="secondary"
            icon={<Zap className="w-4 h-4" />}
            onClick={() => void handleCompile()}
            disabled={compiling || dirty}
            title={
              dirty
                ? "미저장 변경사항은 Compile에 반영되지 않습니다. 저장 후 다시 시도하세요."
                : "저장된 그래프 기준으로 컴파일 결과를 저장합니다. 실제 적재 실행이나 스케줄 활성화는 수행하지 않습니다."
            }
            data-testid="visual-pipeline-compile-button"
          >
            Compile
          </Button>
          <Button
            variant="secondary"
            icon={<Database className="w-4 h-4" />}
            onClick={() => void handleMaterialize()}
            disabled={!canMaterialize || materializing}
            title={
              dirty
                ? "미저장 변경사항이 있습니다. 저장 후 persisted SUCCESS Compile + IN_SYNC 상태에서 실행하세요."
                : !canMaterialize
                  ? "persisted SUCCESS Compile + IN_SYNC 상태에서만 R10 설정을 반영할 수 있습니다."
                  : "R10 Operation/Write/Schedule 설정 row를 upsert합니다. 외부 API 호출, 적재 실행, 스케줄 활성화는 수행하지 않습니다."
            }
            data-testid="visual-pipeline-materialize-button"
          >
            {materializing ? "반영 중…" : "R10 설정 반영"}
          </Button>
          {canRun ? (
            <Button
              variant="secondary"
              icon={<Play className="w-3 h-3" />}
              onClick={() => void handleRunNow()}
              disabled={!canRun || running}
              title={runDisabledReason}
              data-testid="visual-pipeline-run-now-button"
            >
              {running ? "접수 중…" : "Run Now"}
            </Button>
          ) : (
            <button
              type="button"
              disabled
              title={runDisabledReason}
              className="inline-flex items-center gap-1.5 px-2.5 py-1.5 bg-slate-100 text-slate-400 text-xs font-medium rounded-md cursor-not-allowed border border-slate-200"
              data-testid="visual-pipeline-run-now-button"
            >
              <Play className="w-3 h-3" /> {isRunActive ? "실행 중…" : "Run Now"}
            </button>
          )}
          {canActivate ? (
            <Button
              variant="secondary"
              icon={<Clock className="w-3 h-3" />}
              onClick={() => void handleActivateSchedule()}
              disabled={!canActivate || activating}
              title={activateDisabledReason}
              data-testid="visual-pipeline-schedule-activation-button"
            >
              {activating ? "활성화 중…" : "스케줄 활성화"}
            </Button>
          ) : (
            <button
              type="button"
              disabled
              title={activateDisabledReason}
              className="inline-flex items-center gap-1.5 px-2.5 py-1.5 bg-slate-100 text-slate-400 text-xs font-medium rounded-md cursor-not-allowed border border-slate-200"
              data-testid="visual-pipeline-schedule-activation-button"
            >
              <Clock className="w-3 h-3" />{" "}
              {activationResult?.activation_status === "ACTIVE"
                ? "활성화됨"
                : activationResult?.activation_status === "PAUSED"
                  ? "일시중지됨"
                  : "스케줄 활성화"}
            </button>
          )}
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
      <VpCompilePanel
        result={compileResult}
        loading={compiling || compileLoadingLatest}
        error={compileError}
        dirtyHint={dirty}
        expanded={compileExpanded}
        onToggle={() => setCompileExpanded((v) => !v)}
        onSelectNode={(nodeId) => setSelectedNodeId(nodeId)}
      />
      <VpMaterializationPanel
        result={materializationResult}
        loading={materializing || materializationLoadingLatest}
        error={materializationError}
        dirtyHint={dirty}
        compileReady={canMaterialize}
        expanded={materializationExpanded}
        onToggle={() => setMaterializationExpanded((v) => !v)}
      />
      <VpScheduleActivationPanel
        result={activationResult}
        loading={activationLoadingLatest}
        activating={activating}
        deactivating={deactivating}
        pausing={pausing}
        resuming={resuming}
        error={activationError}
        canActivateHint={canActivate ? null : activateDisabledReason}
        staleActiveWarning={
          (activationResult?.activation_status === "ACTIVE" ||
            activationResult?.activation_status === "PAUSED") &&
          pipeline?.current_sync_status !== "IN_SYNC"
        }
        expanded={activationExpanded}
        onToggle={() => setActivationExpanded((v) => !v)}
        onDeactivate={() => void handleDeactivateSchedule()}
        onPause={() => void handlePauseSchedule()}
        onResume={() => void handleResumeSchedule()}
      />
      <VpRunPanel
        result={runResult}
        loading={running || runLoadingLatest}
        polling={runPolling}
        cancelling={cancellingRun}
        error={runError}
        pollError={runPollError}
        canRunHint={canRun ? null : runDisabledReason}
        expanded={runExpanded}
        onToggle={() => setRunExpanded((v) => !v)}
        onCancel={() => void handleCancelRun()}
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
