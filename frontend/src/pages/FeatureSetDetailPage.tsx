import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { ArrowLeft, Eye, Play, Plus, Save, Trash2 } from "lucide-react";
import { deleteApi, extractApiErrorMessage, fetchApi, postApi, putApi, PagedData } from "@/api/client";
import { Button } from "@/components/Button";
import { DataTable } from "@/components/DataTable";
import { Modal } from "@/components/Modal";
import { SelectInput, TextInput } from "@/components/SearchPanel";
import { LoadingState, ErrorState } from "@/components/Pagination";
import { useToast } from "@/hooks/useToast";
import { PageHeader } from "@/layouts/MainLayout";
import { FeatureLineageSection } from "@/components/FeatureLineageSection";
import { FeatureQualitySection } from "@/components/FeatureQualitySection";
import type { FeatureBuildResult } from "@/types/featureRegistry";
import {
  FeatureSet,
  parseFeatureSetDescription,
  toFeatureSetPayload,
} from "@/types/featureSet";

interface FeatureItem {
  feature_id: string;
  feature_name: string;
  feature_group: string | null;
  status: string;
}

const SCOPE_OPTIONS = [
  { value: "ALL", label: "전체" },
  { value: "SITE", label: "지사" },
  { value: "REGION", label: "권역" },
];

const MISSING_OPTIONS = [
  { value: "PREV", label: "직전값" },
  { value: "MEAN", label: "평균값" },
  { value: "ZERO", label: "0" },
  { value: "DROP", label: "제외" },
];

export default function FeatureSetDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { showToast } = useToast();

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [addFeatureOpen, setAddFeatureOpen] = useState(false);
  const [previewOpen, setPreviewOpen] = useState(false);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [buildLoading, setBuildLoading] = useState(false);
  const [previewRows, setPreviewRows] = useState<Record<string, unknown>[]>([]);
  const [previewWarnings, setPreviewWarnings] = useState<string[]>([]);
  const [buildResult, setBuildResult] = useState<FeatureBuildResult | null>(null);
  const [allFeatures, setAllFeatures] = useState<FeatureItem[]>([]);
  const [selectedToAdd, setSelectedToAdd] = useState<string[]>([]);

  const [form, setForm] = useState({
    feature_set_name: "",
    target_domain: "HEAT_DEMAND",
    apply_site_scope: "ALL",
    features: [] as string[],
    text: "",
    missingHandling: "PREV",
    normalize: false,
  });

  const load = async () => {
    if (!id) return;
    setLoading(true);
    setError("");
    try {
      const fs = await fetchApi<FeatureSet>(`/feature-sets/${id}`);
      const meta = parseFeatureSetDescription(fs.description);
      setForm({
        feature_set_name: fs.feature_set_name,
        target_domain: fs.target_domain,
        apply_site_scope: fs.apply_site_scope || "ALL",
        features: fs.features || [],
        text: meta.text,
        missingHandling: meta.missingHandling,
        normalize: meta.normalize,
      });
    } catch {
      setError("Feature Set 정보를 불러오지 못했습니다.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, [id]);

  const openAddFeature = async () => {
    try {
      const res = await fetchApi<PagedData<FeatureItem>>("/features", { page: 1, size: 100 });
      setAllFeatures(res.items);
      setSelectedToAdd([]);
      setAddFeatureOpen(true);
    } catch {
      showToast("error", "Feature 목록을 불러오지 못했습니다.");
    }
  };

  const handleAddFeatures = () => {
    const merged = Array.from(new Set([...form.features, ...selectedToAdd]));
    setForm({ ...form, features: merged });
    setAddFeatureOpen(false);
    showToast("success", "Feature가 추가되었습니다.");
  };

  const handleRemoveFeature = (name: string) => {
    setForm({ ...form, features: form.features.filter((f) => f !== name) });
  };

  const handleSave = async () => {
    if (!id || !form.feature_set_name.trim()) {
      showToast("warning", "Feature Set 명을 입력하세요.");
      return;
    }
    setSaving(true);
    try {
      await putApi(`/feature-sets/${id}`, toFeatureSetPayload(form));
      showToast("success", "Feature Set이 저장되었습니다.");
      load();
    } catch {
      showToast("error", "저장에 실패했습니다.");
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async () => {
    if (!id) return;
    try {
      await deleteApi(`/feature-sets/${id}`);
      showToast("success", "Feature Set이 삭제되었습니다.");
      navigate("/feature-sets");
    } catch {
      showToast("error", "삭제에 실패했습니다.");
    }
  };

  const handlePreview = async () => {
    if (!id) return;
    setPreviewLoading(true);
    try {
      const res = await postApi<{
        preview: Record<string, unknown>[];
        preview_rows?: Record<string, unknown>[];
        warnings?: string[];
      }>(`/feature-sets/${id}/preview`);
      setPreviewRows(res.preview_rows || res.preview || []);
      setPreviewWarnings(res.warnings || []);
      setPreviewOpen(true);
    } catch {
      showToast("error", "Feature 미리보기에 실패했습니다.");
    } finally {
      setPreviewLoading(false);
    }
  };

  const handleBuild = async () => {
    if (!id) return;
    setBuildLoading(true);
    try {
      const res = await postApi<FeatureBuildResult>(
        `/feature-build-jobs?${new URLSearchParams({ feature_set_id: id })}`,
        {},
      );
      const lineageError = res.lineage_error ?? res.result_summary?.lineage_error;
      setBuildResult({
        ...res,
        lineage_error: lineageError,
        lineage_count: res.lineage_count ?? res.result_summary?.lineage_count,
        dataset_version_id: res.dataset_version_id ?? res.result_summary?.dataset_version_id,
      });
      const lineageMsg = res.lineage_count != null ? ` · Lineage ${res.lineage_count}건` : "";
      showToast("success", `Feature ${res.inserted_count}건 생성 완료 (${res.job_id})${lineageMsg}`);
    } catch (err) {
      showToast("error", extractApiErrorMessage(err, "Feature 생성에 실패했습니다."));
    } finally {
      setBuildLoading(false);
    }
  };

  const previewColumns = previewRows.length
    ? ["site_id", "measured_at", "heat_demand", ...form.features.filter((f) => f in previewRows[0])].slice(0, 8)
    : ["site_id", "measured_at", "heat_demand"];

  if (loading) return <LoadingState />;
  if (error) return <ErrorState message={error} onRetry={load} />;

  return (
    <div>
      <PageHeader
        title="Feature 설정 상세"
        description={`Feature Set ID: ${id}`}
        actions={
          <>
            <Button variant="secondary" icon={<ArrowLeft className="w-4 h-4" />} onClick={() => navigate("/feature-sets")}>
              목록
            </Button>
            <Button variant="secondary" icon={<Eye className="w-4 h-4" />} onClick={handlePreview} disabled={previewLoading}>
              {previewLoading ? "미리보기 중..." : "Feature 미리보기"}
            </Button>
            <Button variant="secondary" icon={<Play className="w-4 h-4" />} onClick={handleBuild} disabled={buildLoading}>
              {buildLoading ? "생성 중..." : "Feature 생성"}
            </Button>
            <Button variant="danger" icon={<Trash2 className="w-4 h-4" />} onClick={() => setDeleteOpen(true)}>
              삭제
            </Button>
            <Button icon={<Save className="w-4 h-4" />} onClick={handleSave} disabled={saving}>
              {saving ? "저장 중..." : "저장"}
            </Button>
          </>
        }
      />

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-6">
        <div className="bg-white rounded-lg border border-slate-200 p-4 space-y-3">
          <h3 className="text-sm font-semibold text-slate-800">기본 정보</h3>
          <div>
            <label className="block text-xs text-slate-500 mb-1">Feature Set 명</label>
            <TextInput value={form.feature_set_name} onChange={(v) => setForm({ ...form, feature_set_name: v })} />
          </div>
          <div>
            <label className="block text-xs text-slate-500 mb-1">대상 도메인</label>
            <SelectInput
              value={form.target_domain}
              onChange={(v) => setForm({ ...form, target_domain: v })}
              options={[{ value: "HEAT_DEMAND", label: "열수요(HEAT_DEMAND)" }]}
            />
          </div>
          <div>
            <label className="block text-xs text-slate-500 mb-1">설명</label>
            <TextInput value={form.text} onChange={(v) => setForm({ ...form, text: v })} placeholder="Feature Set 설명" />
          </div>
        </div>

        <div className="bg-white rounded-lg border border-slate-200 p-4 space-y-3">
          <h3 className="text-sm font-semibold text-slate-800">적용 및 전처리</h3>
          <div>
            <label className="block text-xs text-slate-500 mb-1">적용 대상</label>
            <SelectInput
              value={form.apply_site_scope}
              onChange={(v) => setForm({ ...form, apply_site_scope: v })}
              options={SCOPE_OPTIONS}
            />
          </div>
          <div>
            <label className="block text-xs text-slate-500 mb-1">결측 처리 방식</label>
            <SelectInput
              value={form.missingHandling}
              onChange={(v) => setForm({ ...form, missingHandling: v })}
              options={MISSING_OPTIONS}
            />
          </div>
          <div className="flex items-center gap-2 pt-1">
            <input
              id="normalize"
              type="checkbox"
              checked={form.normalize}
              onChange={(e) => setForm({ ...form, normalize: e.target.checked })}
              className="rounded border-slate-300"
            />
            <label htmlFor="normalize" className="text-sm text-slate-700">정규화 사용</label>
          </div>
        </div>
      </div>

      {buildResult && (
        <div className="bg-emerald-50 border border-emerald-200 rounded-lg p-4 mb-6 text-sm space-y-1">
          <p className="font-semibold text-emerald-800">최근 Feature 생성 결과</p>
          <p className="text-emerald-700">
            {buildResult.inserted_count.toLocaleString()}건 ·{" "}
            <span className="font-mono">{buildResult.job_id}</span>
          </p>
          {(buildResult.dataset_version_id ?? buildResult.result_summary?.dataset_version_id) && (
            <p className="text-emerald-600 text-xs">
              Dataset Version:{" "}
              <span className="font-mono">
                {buildResult.dataset_version_id ?? buildResult.result_summary?.dataset_version_id}
              </span>
            </p>
          )}
          <p className="text-emerald-600 text-xs">
            Lineage:{" "}
            {(buildResult.lineage_count ?? buildResult.result_summary?.lineage_count ?? 0).toLocaleString()}건 저장
            {(buildResult.lineage_count ?? buildResult.result_summary?.lineage_count ?? 0) === 0
              && (buildResult.lineage_error ?? buildResult.result_summary?.lineage_error) && (
                <span className="text-amber-700 ml-2">(저장 실패 — 아래 Lineage 섹션 참고)</span>
            )}
          </p>
          {buildResult.checked_start_at && (
            <p className="text-emerald-600 text-xs">
              기간: {buildResult.checked_start_at} ~ {buildResult.checked_end_at}
            </p>
          )}
          {buildResult.warnings && buildResult.warnings.length > 0 && (
            <p className="text-amber-700 text-xs">경고 {buildResult.warnings.length}건</p>
          )}
        </div>
      )}

      <div className="bg-white rounded-lg border border-slate-200 p-4">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-semibold text-slate-800">포함 Feature 목록 ({form.features.length})</h3>
          <Button variant="secondary" icon={<Plus className="w-4 h-4" />} onClick={openAddFeature}>
            Feature 추가
          </Button>
        </div>
        <DataTable
          columns={[
            { key: "name", header: "Feature명" },
            {
              key: "actions",
              header: "작업",
              render: (r) => (
                <Button variant="ghost" onClick={() => handleRemoveFeature(String(r.name))}>제거</Button>
              ),
            },
          ]}
          data={form.features.map((name) => ({ name }))}
        />
      </div>

      {id && <FeatureLineageSection featureSetId={id} buildResult={buildResult} />}

      {id && (
        <FeatureQualitySection
          featureSetId={id}
          datasetVersionId={
            buildResult?.dataset_version_id ?? buildResult?.result_summary?.dataset_version_id ?? null
          }
        />
      )}

      <Modal
        open={addFeatureOpen}
        title="Feature 추가"
        onClose={() => setAddFeatureOpen(false)}
        size="lg"
        footer={
          <>
            <Button variant="secondary" onClick={() => setAddFeatureOpen(false)}>취소</Button>
            <Button onClick={handleAddFeatures}>추가</Button>
          </>
        }
      >
        <div className="max-h-64 overflow-y-auto space-y-2">
          {allFeatures.map((f) => (
            <label key={f.feature_id} className="flex items-center gap-2 text-sm py-1 border-b border-slate-100">
              <input
                type="checkbox"
                checked={selectedToAdd.includes(f.feature_name)}
                disabled={form.features.includes(f.feature_name)}
                onChange={(e) => {
                  if (e.target.checked) setSelectedToAdd([...selectedToAdd, f.feature_name]);
                  else setSelectedToAdd(selectedToAdd.filter((n) => n !== f.feature_name));
                }}
              />
              <span className="font-medium">{f.feature_name}</span>
              <span className="text-slate-400 text-xs">{f.feature_group || "-"}</span>
            </label>
          ))}
        </div>
      </Modal>

      <Modal
        open={previewOpen}
        title="Feature 미리보기"
        onClose={() => setPreviewOpen(false)}
        size="lg"
        footer={<Button variant="secondary" onClick={() => setPreviewOpen(false)}>닫기</Button>}
      >
        {previewWarnings.length > 0 && (
          <div className="mb-3 text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded p-2">
            {previewWarnings.map((w) => <div key={w}>{w}</div>)}
          </div>
        )}
        <DataTable
          columns={previewColumns.map((key) => ({
            key,
            header: key,
            render: (r) => {
              const v = r[key];
              return v == null ? "-" : String(v);
            },
          }))}
          data={previewRows}
        />
      </Modal>

      <Modal
        open={deleteOpen}
        title="삭제 확인"
        onClose={() => setDeleteOpen(false)}
        footer={
          <>
            <Button variant="secondary" onClick={() => setDeleteOpen(false)}>취소</Button>
            <Button variant="danger" onClick={handleDelete}>삭제</Button>
          </>
        }
      >
        <p className="text-sm text-slate-600">
          <strong>{form.feature_set_name}</strong> Feature Set을 삭제하시겠습니까?
        </p>
      </Modal>
    </div>
  );
}
