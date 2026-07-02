import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { Eye, Plus, Save, CheckCircle, Sparkles, Archive } from "lucide-react";
import {
  activatePipelineDefinition,
  archivePipelineDefinition,
  createPipelineDefinition,
  getPipelineDefinition,
  getPipelineDefinitions,
  getPipelineNodeOptions,
  getPipelineRuntimePreview,
  getPipelineTemplates,
  updatePipelineDefinition,
  validatePipelineDefinition,
} from "@/api/pipelineBuilder";
import { PipelineFlowChart } from "@/components/PipelineFlowChart";
import { Button } from "@/components/Button";
import { DataTable } from "@/components/DataTable";
import { Modal } from "@/components/Modal";
import { ErrorState, LoadingState } from "@/components/Pagination";
import { SelectInput, TextInput } from "@/components/SearchPanel";
import { useToast } from "@/hooks/useToast";
import { PageHeader } from "@/layouts/MainLayout";
import type {
  PipelineDefinition,
  PipelineNodeOptions,
  PipelineTemplate,
  PipelineValidationResult,
} from "@/types/pipelineBuilder";
import { R8_PIPELINE_NOTE } from "@/types/pipelineBuilder";
import {
  nodeTypeLabel,
  pipelineStatusClass,
  pipelineStatusLabel,
  pipelineTypeLabel,
} from "@/utils/pipelineBuilderFormat";

const FIELD_LABELS: Record<string, string> = {
  data_source_id: "데이터소스",
  mapping_id: "데이터 매핑",
  dataset_type_id: "표준 데이터셋",
  feature_set_id: "Feature Set",
  algorithm: "알고리즘",
  config_id: "학습 설정",
  model_name: "모델",
  registry_stage: "Registry 단계",
  site_ids: "지사",
  predict_start_date: "예측 시작일",
  predict_end_date: "예측 종료일",
  metric: "지표",
  threshold: "임계값",
  quality_rule_set: "품질 규칙",
  fail_on_error: "오류 시 중단",
  drift_threshold: "Drift 임계값",
  baseline_period: "기준 기간",
  recent_period: "최근 기간",
};

export default function PipelineBuilderPage() {
  const { pipelineId } = useParams<{ pipelineId?: string }>();
  if (pipelineId) {
    return <PipelineBuilderDetail pipelineId={pipelineId} />;
  }
  return <PipelineBuilderList />;
}

function PipelineBuilderList() {
  const navigate = useNavigate();
  const { showToast } = useToast();
  const [items, setItems] = useState<PipelineDefinition[]>([]);
  const [templates, setTemplates] = useState<PipelineTemplate[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [createOpen, setCreateOpen] = useState(false);
  const [createForm, setCreateForm] = useState({ template_id: "", pipeline_name: "", description: "" });
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [defs, tpls] = await Promise.all([
        getPipelineDefinitions({ active_only: true }),
        getPipelineTemplates({ active_only: true, status: "ACTIVE" }),
      ]);
      setItems(defs.items);
      setTemplates(tpls.items);
    } catch {
      setError("Pipeline 목록을 불러오지 못했습니다.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const templateOptions = useMemo(
    () => templates.map((t) => ({ value: t.template_id, label: `${t.template_name} (${t.template_code})` })),
    [templates],
  );

  const handleCreate = async () => {
    if (!createForm.template_id || !createForm.pipeline_name.trim()) {
      showToast("warning", "템플릿과 Pipeline 이름을 입력하세요.");
      return;
    }
    setSaving(true);
    try {
      const created = await createPipelineDefinition({
        template_id: createForm.template_id,
        pipeline_name: createForm.pipeline_name.trim(),
        description: createForm.description || undefined,
      });
      showToast("success", "Pipeline Definition이 생성되었습니다.");
      setCreateOpen(false);
      navigate(`/pipeline-builder/${created.pipeline_id}`);
    } catch {
      showToast("error", "생성에 실패했습니다.");
    } finally {
      setSaving(false);
    }
  };

  if (loading && !items.length) return <LoadingState />;
  if (error && !items.length) return <ErrorState message={error} onRetry={() => void load()} />;

  return (
    <div>
      <PageHeader
        title="Pipeline Builder"
        description="Pipeline Template Flow Chart와 노드별 실행 파라미터를 관리합니다."
        actions={
          <Button icon={<Plus className="w-4 h-4" />} onClick={() => setCreateOpen(true)}>
            새 Pipeline 만들기
          </Button>
        }
      />
      <div className="mb-4 text-xs text-slate-600 bg-amber-50 border border-amber-200 rounded-lg p-3 space-y-1">
        <p>{R8_PIPELINE_NOTE}</p>
        <p>
          실행 이력·수동 DAG 실행은 <Link to="/ops/pipeline-runs" className="text-blue-600 hover:underline">파이프라인 실행 이력</Link>
          에서 계속 사용할 수 있습니다.
        </p>
      </div>
      <DataTable
        columns={[
          { key: "pipeline_name", header: "Pipeline 이름" },
          { key: "template_name", header: "Template" },
          { key: "pipeline_type", header: "유형", render: (r) => pipelineTypeLabel(String(r.pipeline_type)) },
          {
            key: "status",
            header: "상태",
            render: (r) => (
              <span className={`text-[10px] px-1.5 py-0.5 rounded border ${pipelineStatusClass(String(r.status))}`}>
                {pipelineStatusLabel(String(r.status))}
              </span>
            ),
          },
          { key: "airflow_dag_id", header: "Airflow DAG" },
          { key: "last_validated_at", header: "마지막 검증", render: (r) => String(r.last_validated_at || "-").slice(0, 19) },
          {
            key: "actions",
            header: "",
            render: (r) => (
              <Button
                variant="ghost"
                icon={<Eye className="w-3 h-3" />}
                onClick={() => navigate(`/pipeline-builder/${String(r.pipeline_id)}`)}
              >
                열기
              </Button>
            ),
          },
        ]}
        data={items as unknown as Record<string, unknown>[]}
      />
      <Modal
        open={createOpen}
        title="새 Pipeline 만들기"
        onClose={() => setCreateOpen(false)}
        footer={
          <>
            <Button variant="secondary" onClick={() => setCreateOpen(false)}>취소</Button>
            <Button onClick={() => void handleCreate()} disabled={saving}>{saving ? "생성 중..." : "생성"}</Button>
          </>
        }
      >
        <div className="space-y-3 text-sm">
          <div>
            <label className="block text-xs text-slate-500 mb-1">Template</label>
            <SelectInput
              value={createForm.template_id}
              onChange={(v) => setCreateForm({ ...createForm, template_id: v })}
              options={[{ value: "", label: "선택" }, ...templateOptions]}
            />
          </div>
          <div>
            <label className="block text-xs text-slate-500 mb-1">Pipeline 이름</label>
            <TextInput
              value={createForm.pipeline_name}
              onChange={(v) => setCreateForm({ ...createForm, pipeline_name: v })}
              placeholder="일일 열수요 예측 운영 파이프라인"
            />
          </div>
          <div>
            <label className="block text-xs text-slate-500 mb-1">설명</label>
            <TextInput value={createForm.description} onChange={(v) => setCreateForm({ ...createForm, description: v })} />
          </div>
        </div>
      </Modal>
    </div>
  );
}

function PipelineBuilderDetail({ pipelineId }: { pipelineId: string }) {
  const navigate = useNavigate();
  const { showToast } = useToast();
  const [pipeline, setPipeline] = useState<PipelineDefinition | null>(null);
  const [loading, setLoading] = useState(true);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [nodeConfig, setNodeConfig] = useState<Record<string, Record<string, unknown>>>({});
  const [nodeOptions, setNodeOptions] = useState<PipelineNodeOptions | null>(null);
  const [validation, setValidation] = useState<PipelineValidationResult | null>(null);
  const [runtimePreview, setRuntimePreview] = useState<Record<string, unknown> | null>(null);
  const [saving, setSaving] = useState(false);
  const [validating, setValidating] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const item = await getPipelineDefinition(pipelineId);
      setPipeline(item);
      setNodeConfig(item.node_config || {});
      setValidation(item.validation_result || null);
      const first = item.flow?.nodes?.[0]?.node_id;
      setSelectedNodeId((prev) => prev || first || null);
    } catch {
      showToast("error", "Pipeline을 불러오지 못했습니다.");
    } finally {
      setLoading(false);
    }
  }, [pipelineId, showToast]);

  useEffect(() => {
    void load();
  }, [load]);

  const selectedNode = useMemo(
    () => pipeline?.flow?.nodes?.find((n) => n.node_id === selectedNodeId),
    [pipeline, selectedNodeId],
  );

  useEffect(() => {
    if (!selectedNode) {
      setNodeOptions(null);
      return;
    }
    void getPipelineNodeOptions({
      component_type: selectedNode.component_type,
      template_id: pipeline?.template_id,
      pipeline_id: pipelineId,
    }).then(setNodeOptions).catch(() => setNodeOptions(null));
  }, [selectedNode, pipeline?.template_id, pipelineId]);

  const updateNodeField = (nodeId: string, field: string, value: string) => {
    setNodeConfig((prev) => ({
      ...prev,
      [nodeId]: { ...(prev[nodeId] || {}), [field]: value },
    }));
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      const updated = await updatePipelineDefinition(pipelineId, { node_config: nodeConfig });
      setPipeline(updated);
      setNodeConfig(updated.node_config || {});
      showToast("success", "저장되었습니다.");
    } catch {
      showToast("error", "저장에 실패했습니다.");
    } finally {
      setSaving(false);
    }
  };

  const handleValidate = async () => {
    setValidating(true);
    try {
      await updatePipelineDefinition(pipelineId, { node_config: nodeConfig });
      const res = await validatePipelineDefinition(pipelineId);
      setValidation(res);
      await load();
      if (res.valid) {
        showToast("success", "검증에 성공했습니다.");
      } else {
        showToast("warning", `검증 오류 ${res.errors.length}건`);
      }
    } catch {
      showToast("error", "검증에 실패했습니다.");
    } finally {
      setValidating(false);
    }
  };

  const handleActivate = async () => {
    try {
      await activatePipelineDefinition(pipelineId);
      showToast("success", "ACTIVE로 전환되었습니다.");
      void load();
    } catch (err: unknown) {
      showToast("error", err instanceof Error ? err.message : "활성화에 실패했습니다.");
    }
  };

  const handleArchive = async () => {
    try {
      await archivePipelineDefinition(pipelineId);
      showToast("success", "보관 처리되었습니다.");
      navigate("/pipeline-builder");
    } catch {
      showToast("error", "보관에 실패했습니다.");
    }
  };

  const handleRuntimePreview = async () => {
    try {
      const res = await getPipelineRuntimePreview(pipelineId);
      setRuntimePreview(res.runtime_params);
      showToast("success", "Runtime Preview를 갱신했습니다.");
    } catch {
      showToast("error", "Runtime Preview에 실패했습니다.");
    }
  };

  if (loading && !pipeline) return <LoadingState />;
  if (!pipeline) return <ErrorState message="Pipeline을 찾을 수 없습니다." onRetry={() => void load()} />;

  const flowWithConfig = pipeline.flow
    ? {
        ...pipeline.flow,
        nodes: pipeline.flow.nodes.map((n) => ({
          ...n,
          config: nodeConfig[n.node_id] || n.config,
        })),
      }
    : undefined;

  return (
    <div>
      <PageHeader
        title={pipeline.pipeline_name}
        description={`${pipeline.template_name || pipeline.template_id} · ${pipelineTypeLabel(pipeline.pipeline_type)}`}
        actions={
          <div className="flex flex-wrap gap-2">
            <Button variant="secondary" onClick={() => navigate("/pipeline-builder")}>목록</Button>
            <Button icon={<Save className="w-4 h-4" />} onClick={() => void handleSave()} disabled={saving}>저장</Button>
            <Button variant="secondary" icon={<CheckCircle className="w-4 h-4" />} onClick={() => void handleValidate()} disabled={validating}>
              검증
            </Button>
            <Button variant="secondary" onClick={() => void handleRuntimePreview()}>Runtime Preview</Button>
            <Button icon={<Sparkles className="w-4 h-4" />} onClick={() => void handleActivate()}>활성화</Button>
            <Button variant="ghost" icon={<Archive className="w-4 h-4" />} onClick={() => void handleArchive()}>보관</Button>
          </div>
        }
      />
      <div className="mb-3 flex flex-wrap gap-2 text-xs">
        <span className={`px-2 py-0.5 rounded border ${pipelineStatusClass(pipeline.status)}`}>
          {pipelineStatusLabel(pipeline.status)}
        </span>
        <span className="text-slate-500">Airflow: {pipeline.airflow_dag_id || "-"}</span>
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-[1fr_320px] gap-4">
        <div className="border rounded-lg p-4 bg-white min-h-[200px]">
          <PipelineFlowChart
            flow={flowWithConfig}
            selectedNodeId={selectedNodeId}
            onSelectNode={setSelectedNodeId}
          />
        </div>
        <div className="border rounded-lg p-4 bg-white">
          <h3 className="text-sm font-semibold text-slate-800 mb-2">노드 설정</h3>
          {!selectedNode && <p className="text-xs text-slate-400">Flow Chart에서 노드를 선택하세요.</p>}
          {selectedNode && (
            <div className="space-y-3 text-sm">
              <div className="text-xs text-slate-500">
                {selectedNode.label} · {nodeTypeLabel(selectedNode.component_type)}
                {selectedNode.required ? " (필수)" : " (선택)"}
              </div>
              {(selectedNode.config_fields || []).map((field) => {
                const opts = nodeOptions?.fields?.[field];
                const val = String((nodeConfig[selectedNode.node_id] || {})[field] ?? "");
                if (field.includes("date")) {
                  return (
                    <div key={field}>
                      <label className="block text-xs text-slate-500 mb-1">{FIELD_LABELS[field] || field}</label>
                      <input
                        type="date"
                        className="w-full border rounded px-2 py-1.5 text-sm"
                        value={val}
                        onChange={(e) => updateNodeField(selectedNode.node_id, field, e.target.value)}
                      />
                    </div>
                  );
                }
                if (opts?.length) {
                  return (
                    <div key={field}>
                      <label className="block text-xs text-slate-500 mb-1">{FIELD_LABELS[field] || field}</label>
                      <SelectInput
                        value={val}
                        onChange={(v) => updateNodeField(selectedNode.node_id, field, v)}
                        options={[{ value: "", label: "선택" }, ...opts.map((o) => ({ value: o.value, label: o.label }))]}
                      />
                    </div>
                  );
                }
                return (
                  <div key={field}>
                    <label className="block text-xs text-slate-500 mb-1">{FIELD_LABELS[field] || field}</label>
                    <TextInput value={val} onChange={(v) => updateNodeField(selectedNode.node_id, field, v)} />
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
      <div className="mt-4 grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="border rounded-lg p-4 bg-white text-xs">
          <h3 className="font-semibold text-slate-800 mb-2">검증 결과</h3>
          {!validation && <p className="text-slate-400">검증을 실행하세요.</p>}
          {validation && (
            <div className="space-y-1">
              <p className={validation.valid ? "text-emerald-700" : "text-red-700"}>
                {validation.valid ? "검증 통과" : `오류 ${validation.errors.length}건`}
                {validation.warnings.length > 0 && ` · 경고 ${validation.warnings.length}건`}
              </p>
              {validation.errors.map((e, i) => (
                <p key={`e-${i}`} className="text-red-700">• {e.message}</p>
              ))}
              {validation.warnings.map((w, i) => (
                <p key={`w-${i}`} className="text-amber-700">• {w.message}</p>
              ))}
            </div>
          )}
        </div>
        <div className="border rounded-lg p-4 bg-white text-xs">
          <h3 className="font-semibold text-slate-800 mb-2">실행 파라미터 미리보기 (Runtime Preview)</h3>
          <p className="text-slate-500 mb-2">R8에서는 Airflow 실행 없이 params preview만 제공합니다.</p>
          <pre className="bg-slate-50 border rounded p-2 overflow-x-auto text-[11px] max-h-48">
            {JSON.stringify(runtimePreview || validation?.runtime_params_preview || {}, null, 2)}
          </pre>
        </div>
      </div>
    </div>
  );
}
