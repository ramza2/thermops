import { useCallback, useEffect, useMemo, useState } from "react";
import { Eye, Plus, Trash2 } from "lucide-react";
import { deleteApi, fetchApi, postApi, PagedData } from "@/api/client";
import { validateFeatureName } from "@/api/featureRegistration";
import { getFeatureRegistry } from "@/api/featureRegistry";
import { Button } from "@/components/Button";
import { DataTable } from "@/components/DataTable";
import { Modal } from "@/components/Modal";
import { StatusBadge } from "@/components/StatusBadge";
import { Pagination, LoadingState, ErrorState } from "@/components/Pagination";
import { SelectInput, TextInput } from "@/components/SearchPanel";
import { useToast } from "@/hooks/useToast";
import { PageHeader } from "@/layouts/MainLayout";
import { CalcMemoText, FeatureRegistryPanel } from "@/components/FeatureRegistryPanel";
import type { FeatureNameValidation } from "@/types/featureRegistration";
import type { FeatureRegistryItem } from "@/types/featureRegistry";
import { formatRegistrySummary } from "@/utils/featureRegistryFormat";
import {
  FEATURE_USAGE_STEPS,
  registrationStatusClass,
  registrationStatusLabel,
  validationBlocksRegistration,
  validationWarnsRegistration,
} from "@/utils/featureRegistrationFormat";

interface Feature {
  feature_id: string;
  feature_name: string;
  feature_group: string | null;
  feature_type: string;
  calc_expression: string | null;
  status: string;
  description: string | null;
  registration?: FeatureNameValidation;
}

const EMPTY = { feature_name: "", feature_group: "", feature_type: "NUMERIC", calc_expression: "", description: "" };

const CALC_MEMO_HELP = `계산식 메모는 설명용입니다. 입력한 LAG(...) 식이 자동 실행되지는 않습니다.
현재 계산식은 설명용 메타데이터입니다.
LAG(heat_demand, 24)와 같이 입력해도 자동 계산되지는 않습니다.
실제 계산에 사용하려면 Feature Set 포함과 별도 계산 로직 구현이 필요합니다.`;

const REGISTER_INFO = `Feature 등록은 카탈로그 등록 단계입니다.
모델 학습/예측에 사용하려면 Feature Set에 포함하고 Feature 생성 작업을 실행해야 합니다.
신규 파생 Feature는 현재 계산 로직이 코드에 구현되어 있어야 값이 생성됩니다.`;

function RegistrationBadge({ registration }: { registration?: FeatureNameValidation }) {
  if (!registration) return <span className="text-xs text-slate-400">-</span>;
  return (
    <span
      className={`inline-flex text-[11px] px-1.5 py-0.5 rounded border ${registrationStatusClass(registration.status)}`}
      title={registration.message}
    >
      {registrationStatusLabel(registration.status)}
    </span>
  );
}

function ValidationResultPanel({ validation, validating }: { validation: FeatureNameValidation | null; validating: boolean }) {
  if (validating) {
    return <p className="text-xs text-slate-400">Feature명 검증 중...</p>;
  }
  if (!validation) return null;
  const tone =
    validation.status === "COMPUTABLE"
      ? "text-emerald-800 bg-emerald-50 border-emerald-200"
      : validation.status === "LEGACY_ALIAS" || validation.status === "DUPLICATE"
        ? "text-red-800 bg-red-50 border-red-200"
        : "text-amber-800 bg-amber-50 border-amber-200";
  return (
    <div className={`text-xs border rounded-lg p-3 ${tone}`}>
      <div className="flex items-center gap-2 mb-1">
        <RegistrationBadge registration={validation} />
        {validation.recommended_name && validation.status === "LEGACY_ALIAS" && (
          <span className="font-medium">권장: {validation.recommended_name}</span>
        )}
      </div>
      <p>{validation.message}</p>
      {validation.status === "COMPUTABLE" && (
        <p className="mt-1 text-emerald-700">
          이 Feature는 코드 기반 Registry에 등록되어 있어 Feature Set에 포함 후 Feature 생성에 사용할 수 있습니다.
        </p>
      )}
      {validation.status === "CATALOG_ONLY" && !validation.catalog_registered && (
        <p className="mt-1">
          이 Feature는 카탈로그에만 등록됩니다. 현재 계산 로직이 없으므로 Feature 생성 결과에 값이 생성되지 않을 수 있습니다.
        </p>
      )}
    </div>
  );
}

export default function FeaturesPage() {
  const { showToast } = useToast();
  const [items, setItems] = useState<Feature[]>([]);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [createOpen, setCreateOpen] = useState(false);
  const [detailTarget, setDetailTarget] = useState<Feature | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<Feature | null>(null);
  const [form, setForm] = useState(EMPTY);
  const [saving, setSaving] = useState(false);
  const [registryMap, setRegistryMap] = useState<Record<string, FeatureRegistryItem>>({});
  const [registryWarning, setRegistryWarning] = useState("");
  const [nameValidation, setNameValidation] = useState<FeatureNameValidation | null>(null);
  const [validatingName, setValidatingName] = useState(false);

  const loadRegistry = async () => {
    try {
      const res = await getFeatureRegistry();
      const map: Record<string, FeatureRegistryItem> = {};
      for (const f of res.features || []) {
        map[f.feature_name] = f;
      }
      setRegistryMap(map);
      setRegistryWarning("");
    } catch {
      setRegistryWarning("Feature Registry 정보를 불러오지 못했습니다. 카탈로그 목록만 표시됩니다.");
    }
  };

  const load = async (p = page) => {
    setLoading(true);
    setError("");
    try {
      const res = await fetchApi<PagedData<Feature>>("/features", { page: p, size: 20 });
      setItems(res.items);
      setTotalPages(res.total_pages);
    } catch {
      setError("Feature 목록을 불러오지 못했습니다.");
    } finally {
      setLoading(false);
    }
  };

  const runNameValidation = useCallback(async (name: string) => {
    const trimmed = name.trim();
    if (!trimmed) {
      setNameValidation(null);
      return;
    }
    setValidatingName(true);
    try {
      const result = await validateFeatureName(trimmed);
      setNameValidation(result);
    } catch {
      setNameValidation(null);
    } finally {
      setValidatingName(false);
    }
  }, []);

  useEffect(() => {
    load(page);
    loadRegistry();
  }, [page]);

  useEffect(() => {
    if (!createOpen) {
      setNameValidation(null);
      return;
    }
    const timer = window.setTimeout(() => {
      void runNameValidation(form.feature_name);
    }, 400);
    return () => window.clearTimeout(timer);
  }, [createOpen, form.feature_name, runNameValidation]);

  const detailRegistry = useMemo(
    () => (detailTarget ? registryMap[detailTarget.feature_name] : undefined),
    [detailTarget, registryMap],
  );

  const createBlocked = validationBlocksRegistration(nameValidation);

  const handleCreate = async () => {
    if (!form.feature_name.trim()) {
      showToast("warning", "Feature명을 입력하세요.");
      return;
    }
    if (createBlocked) {
      showToast("warning", nameValidation?.message || "등록할 수 없는 Feature명입니다.");
      return;
    }
    setSaving(true);
    try {
      await postApi("/features", {
        feature_name: form.feature_name.trim(),
        feature_group: form.feature_group || null,
        feature_type: form.feature_type,
        calc_expression: form.calc_expression || null,
        description: form.description || null,
      });
      showToast("success", "Feature가 등록되었습니다.");
      setCreateOpen(false);
      setForm(EMPTY);
      setNameValidation(null);
      load(1);
      setPage(1);
    } catch {
      showToast("error", "등록에 실패했습니다.");
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async () => {
    if (!deleteTarget) return;
    try {
      await deleteApi(`/features/${deleteTarget.feature_id}`);
      showToast("success", "Feature가 삭제되었습니다.");
      setDeleteTarget(null);
      load();
    } catch {
      showToast("error", "삭제에 실패했습니다.");
    }
  };

  if (loading && !items.length) return <LoadingState />;
  if (error && !items.length) return <ErrorState message={error} onRetry={() => load()} />;

  return (
    <div>
      <PageHeader
        title="Feature 목록"
        description="모델 학습에 사용되는 Feature 메타데이터(카탈로그)를 정의합니다. 등록만으로는 값이 생성되지 않습니다."
        actions={<Button icon={<Plus className="w-4 h-4" />} onClick={() => setCreateOpen(true)}>신규 Feature</Button>}
      />

      <div className="mb-4 text-xs text-slate-600 bg-blue-50 border border-blue-200 rounded-lg p-3 whitespace-pre-line">
        <strong className="text-slate-800">신규 Feature 사용 절차</strong>
        {"\n"}
        {FEATURE_USAGE_STEPS}
      </div>

      <div className="mb-4 text-xs text-slate-500 bg-slate-50 border border-slate-200 rounded-lg p-3 whitespace-pre-line">
        {REGISTER_INFO}
      </div>

      {registryWarning && (
        <div className="mb-4 text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded-lg p-3">
          {registryWarning}
        </div>
      )}

      <DataTable
        loading={loading}
        columns={[
          { key: "feature_id", header: "ID", width: "120px" },
          { key: "feature_name", header: "Feature명" },
          { key: "feature_group", header: "그룹", render: (r) => String(r.feature_group || "-") },
          {
            key: "registration",
            header: "등록 유형",
            render: (r) => (
              <RegistrationBadge registration={r.registration as FeatureNameValidation | undefined} />
            ),
          },
          { key: "feature_type", header: "유형" },
          {
            key: "calc_expression",
            header: "계산식 메모",
            render: (r) => <CalcMemoText expression={r.calc_expression as string | null} />,
          },
          {
            key: "registry",
            header: "Registry",
            render: (r) => {
              const name = String(r.feature_name);
              const reg = registryMap[name];
              if (!reg && registryWarning) return <span className="text-xs text-slate-400">-</span>;
              return (
                <span className={`text-xs ${reg ? "text-slate-600" : "text-amber-700"}`}>
                  {formatRegistrySummary(reg)}
                </span>
              );
            },
          },
          { key: "status", header: "상태", render: (r) => <StatusBadge status={r.status as string} /> },
          {
            key: "actions",
            header: "작업",
            render: (r) => (
              <div className="flex gap-1">
                <Button
                  variant="ghost"
                  icon={<Eye className="w-3 h-3" />}
                  onClick={(e) => {
                    e.stopPropagation();
                    setDetailTarget(r as unknown as Feature);
                  }}
                >
                  상세
                </Button>
                <Button
                  variant="danger"
                  icon={<Trash2 className="w-3 h-3" />}
                  onClick={(e) => {
                    e.stopPropagation();
                    setDeleteTarget(r as unknown as Feature);
                  }}
                >
                  삭제
                </Button>
              </div>
            ),
          },
        ]}
        data={items as unknown as Record<string, unknown>[]}
      />
      <Pagination page={page} totalPages={totalPages} onChange={setPage} />

      <Modal
        open={!!detailTarget}
        title={`Feature 상세 — ${detailTarget?.feature_name ?? ""}`}
        onClose={() => setDetailTarget(null)}
        size="lg"
        footer={<Button variant="secondary" onClick={() => setDetailTarget(null)}>닫기</Button>}
      >
        {detailTarget && (
          <div className="space-y-4">
            <dl className="grid grid-cols-2 gap-2 text-sm">
              <dt className="text-slate-500 text-xs">ID</dt>
              <dd className="font-mono text-xs">{detailTarget.feature_id}</dd>
              <dt className="text-slate-500 text-xs">등록 유형</dt>
              <dd><RegistrationBadge registration={detailTarget.registration} /></dd>
              <dt className="text-slate-500 text-xs">상태</dt>
              <dd><StatusBadge status={detailTarget.status} /></dd>
              <dt className="text-slate-500 text-xs">카탈로그 설명</dt>
              <dd>{detailTarget.description || "-"}</dd>
            </dl>
            <div>
              <h4 className="text-sm font-semibold text-slate-800 mb-2">Registry 정보</h4>
              <FeatureRegistryPanel
                registry={detailRegistry}
                catalogCalcExpression={detailTarget.calc_expression}
              />
            </div>
            <p className="text-[11px] text-slate-500">
              calc_expression은 설명용 메타데이터이며 자동 계산되지 않습니다. 실제 값 생성은 Feature Set 포함 후
              Feature 생성 작업이 필요합니다.
            </p>
          </div>
        )}
      </Modal>

      <Modal
        open={createOpen}
        title="Feature 등록"
        onClose={() => setCreateOpen(false)}
        footer={
          <>
            <Button variant="secondary" onClick={() => setCreateOpen(false)}>취소</Button>
            <Button onClick={handleCreate} disabled={saving || createBlocked}>
              {saving ? "저장 중..." : "저장"}
            </Button>
          </>
        }
      >
        <div className="space-y-3">
          <div>
            <label className="block text-xs text-slate-500 mb-1">Feature명</label>
            <TextInput
              value={form.feature_name}
              onChange={(v) => setForm({ ...form, feature_name: v })}
              placeholder="demand_lag_24h"
            />
            <p className="text-[11px] text-slate-400 mt-1">공식 명칭은 docs/md/THERMOps_Feature_명칭_및_계산식_정책.md 참고</p>
            <div className="mt-2">
              <ValidationResultPanel validation={nameValidation} validating={validatingName} />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs text-slate-500 mb-1">그룹</label>
              <TextInput value={form.feature_group} onChange={(v) => setForm({ ...form, feature_group: v })} placeholder="열수요 이력" />
            </div>
            <div>
              <label className="block text-xs text-slate-500 mb-1">유형</label>
              <SelectInput value={form.feature_type} onChange={(v) => setForm({ ...form, feature_type: v })}
                options={[{ value: "NUMERIC", label: "수치" }, { value: "CATEGORICAL", label: "범주" }, { value: "DATETIME", label: "일시" }]} />
            </div>
          </div>
          <div>
            <label className="block text-xs text-slate-500 mb-1">계산식 메모 <span className="text-amber-600">[설명용]</span></label>
            <TextInput value={form.calc_expression} onChange={(v) => setForm({ ...form, calc_expression: v })} placeholder="예: 24시간 전 열수요" />
            <p className="text-[11px] text-slate-500 mt-1 whitespace-pre-line">{CALC_MEMO_HELP}</p>
          </div>
          <div>
            <label className="block text-xs text-slate-500 mb-1">설명</label>
            <TextInput value={form.description} onChange={(v) => setForm({ ...form, description: v })} />
          </div>
          {validationWarnsRegistration(nameValidation) && (
            <div className="text-xs text-amber-800 bg-amber-50 border border-amber-200 rounded p-3">
              등록은 가능하지만 계산 로직이 없어 Feature 생성 시 값이 만들어지지 않을 수 있습니다.
            </div>
          )}
          <div className="text-xs text-slate-600 bg-slate-50 border border-slate-200 rounded p-3 whitespace-pre-line">
            {REGISTER_INFO}
          </div>
        </div>
      </Modal>

      <Modal open={!!deleteTarget} title="삭제 확인" onClose={() => setDeleteTarget(null)}
        footer={<>
          <Button variant="secondary" onClick={() => setDeleteTarget(null)}>취소</Button>
          <Button variant="danger" onClick={handleDelete}>삭제</Button>
        </>}>
        <p className="text-sm text-slate-600"><strong>{deleteTarget?.feature_name}</strong> Feature를 삭제하시겠습니까?</p>
      </Modal>
    </div>
  );
}
