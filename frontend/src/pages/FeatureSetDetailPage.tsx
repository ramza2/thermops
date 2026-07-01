import { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { ArrowLeft, Eye, Play, Plus, Save, Trash2 } from "lucide-react";
import { deleteApi, extractApiErrorMessage, fetchApi, postApi, putApi, PagedData } from "@/api/client";
import { addRecipeFeatureToFeatureSet, listFeatureRecipes } from "@/api/featureRecipes";
import { validateFeatureName, replaceLegacyFeatures } from "@/api/featureRegistration";
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
import type { FeatureNameValidation, FeatureSetLegacyReplaceResult } from "@/types/featureRegistration";
import type { FeatureRecipe } from "@/types/featureRecipes";
import { R6_BUILD_INFO } from "@/types/featureRecipes";
import {
  CATALOG_ONLY_WARNING_MSG,
  FEATURE_QUALITY_REGISTRATION_HINT,
  LEGACY_ALIAS_WARNING_MSG,
  LEGACY_REPLACE_AFTER_HINT,
  LEGACY_REPLACE_HINT,
  TPL_FEATURE_BLOCK_MSG,
  matchesFeatureListFilter,
  registrationStatusClass,
  registrationStatusLabel,
  type FeatureListFilter,
} from "@/utils/featureRegistrationFormat";
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
  registration?: FeatureNameValidation;
}

function FeatureRegistrationBadge({ registration }: { registration?: FeatureNameValidation }) {
  if (!registration) return <span className="text-xs text-slate-400">-</span>;
  const status = (registration.registration_status ?? registration.status) as FeatureNameValidation["status"];
  const title = registration.build_supported
    ? `${registration.message} (Recipe Engine Build 지원)`
    : registration.message;
  return (
    <span
      className={`inline-flex text-[11px] px-1.5 py-0.5 rounded border ${registrationStatusClass(status)}`}
      title={title}
    >
      {registrationStatusLabel(status)}
    </span>
  );
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
  const [featureStatusMap, setFeatureStatusMap] = useState<Record<string, FeatureNameValidation>>({});
  const [addWarnings, setAddWarnings] = useState<string[]>([]);
  const [featureFilter, setFeatureFilter] = useState<FeatureListFilter>("all");
  const [featureSearch, setFeatureSearch] = useState("");
  const [replaceModalOpen, setReplaceModalOpen] = useState(false);
  const [replacePlan, setReplacePlan] = useState<FeatureSetLegacyReplaceResult | null>(null);
  const [replaceLoading, setReplaceLoading] = useState(false);
  const [replaceApplying, setReplaceApplying] = useState(false);
  const [recipeAddOpen, setRecipeAddOpen] = useState(false);
  const [publishedRecipes, setPublishedRecipes] = useState<FeatureRecipe[]>([]);
  const [selectedRecipeId, setSelectedRecipeId] = useState("");
  const [recipeAddLoading, setRecipeAddLoading] = useState(false);

  const isTplSet = Boolean(id?.startsWith("FS-TPL-"));

  const openAddRecipeFeature = async () => {
    if (isTplSet) return;
    setRecipeAddOpen(true);
    setSelectedRecipeId("");
    try {
      const res = await listFeatureRecipes({ status: "PUBLISHED", limit: 100 });
      setPublishedRecipes(res.items);
    } catch {
      showToast("error", "발행된 Recipe 목록을 불러오지 못했습니다.");
    }
  };

  const handleAddRecipeFeature = async () => {
    if (!id || !selectedRecipeId) return;
    setRecipeAddLoading(true);
    try {
      const res = await addRecipeFeatureToFeatureSet(id, { recipe_id: selectedRecipeId });
      setForm({ ...form, features: res.features });
      setRecipeAddOpen(false);
      showToast("success", res.message || "Recipe Feature가 추가되었습니다.");
      if (res.warnings?.length) showToast("warning", res.warnings.join(" "));
    } catch (e) {
      showToast("error", extractApiErrorMessage(e));
    } finally {
      setRecipeAddLoading(false);
    }
  };

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

  useEffect(() => {
    if (!form.features.length) {
      setFeatureStatusMap({});
      return;
    }
    let cancelled = false;
    (async () => {
      const entries = await Promise.all(
        form.features.map(async (name) => {
          try {
            const v = await validateFeatureName(name);
            return [name, v] as const;
          } catch {
            return [name, null] as const;
          }
        }),
      );
      if (cancelled) return;
      const map: Record<string, FeatureNameValidation> = {};
      for (const [name, v] of entries) {
        if (v) map[name] = v;
      }
      setFeatureStatusMap(map);
    })();
    return () => { cancelled = true; };
  }, [form.features]);

  const filteredFeatures = useMemo(() => {
    const q = featureSearch.trim().toLowerCase();
    return allFeatures.filter((f) => {
      if (!matchesFeatureListFilter(f.registration, featureFilter)) return false;
      if (!q) return true;
      return (
        f.feature_name.toLowerCase().includes(q)
        || (f.feature_group || "").toLowerCase().includes(q)
      );
    });
  }, [allFeatures, featureFilter, featureSearch]);

  const legacyFeaturesInSet = useMemo(
    () => form.features.filter((name) => featureStatusMap[name]?.status === "LEGACY_ALIAS"),
    [form.features, featureStatusMap],
  );

  const hasLegacyInSet = legacyFeaturesInSet.length > 0;
  const buildHasLegacy = (buildResult?.result_summary?.legacy_alias_features?.length ?? 0) > 0;

  const openReplaceLegacyModal = async () => {
    if (!id) return;
    setReplaceLoading(true);
    try {
      const plan = await replaceLegacyFeatures(id, true);
      if (!plan.changed || plan.replacement_count === 0) {
        showToast("info", plan.message || "대체할 Legacy Feature가 없습니다.");
        return;
      }
      setReplacePlan(plan);
      setReplaceModalOpen(true);
    } catch (err) {
      showToast("error", extractApiErrorMessage(err, "Legacy Feature 대체 계획 조회에 실패했습니다."));
    } finally {
      setReplaceLoading(false);
    }
  };

  const handleApplyLegacyReplace = async () => {
    if (!id) return;
    const confirmMsg = isTplSet
      ? `공식 TPL Feature Set의 features 목록을 공식명 기준으로 업데이트합니다.\n${LEGACY_REPLACE_AFTER_HINT}\n\n계속하시겠습니까?`
      : `Feature Set의 features 목록을 공식명 기준으로 업데이트합니다.\n${LEGACY_REPLACE_AFTER_HINT}\n\n계속하시겠습니까?`;
    if (!window.confirm(confirmMsg)) return;

    setReplaceApplying(true);
    try {
      const result = await replaceLegacyFeatures(id, false);
      setReplaceModalOpen(false);
      setReplacePlan(null);
      await load();
      showToast(
        "success",
        `Legacy Feature ${result.replacement_count}개를 공식명으로 대체했습니다. Feature 생성을 다시 실행하세요.`,
      );
    } catch (err) {
      showToast("error", extractApiErrorMessage(err, "Legacy Feature 대체 적용에 실패했습니다."));
    } finally {
      setReplaceApplying(false);
    }
  };

  const isAddCheckboxDisabled = (f: FeatureItem) => {
    if (form.features.includes(f.feature_name)) return true;
    if (f.registration?.status === "LEGACY_ALIAS") return true;
    if (isTplSet && f.registration && !f.registration.computable) return true;
    return false;
  };

  const openAddFeature = async () => {
    try {
      const res = await fetchApi<PagedData<FeatureItem>>("/features", { page: 1, size: 100 });
      setAllFeatures(res.items);
      setSelectedToAdd([]);
      setFeatureFilter("all");
      setFeatureSearch("");
      setAddFeatureOpen(true);
    } catch {
      showToast("error", "Feature 목록을 불러오지 못했습니다.");
    }
  };

  const handleAddFeatures = () => {
    const legacySelected = selectedToAdd.filter((name) => {
      const reg = allFeatures.find((f) => f.feature_name === name)?.registration;
      return reg?.status === "LEGACY_ALIAS";
    });
    if (legacySelected.length) {
      const alias = legacySelected[0];
      const rec = allFeatures.find((f) => f.feature_name === alias)?.registration?.recommended_name || "공식명";
      showToast("warning", LEGACY_ALIAS_WARNING_MSG(alias, rec));
      return;
    }
    if (isTplSet) {
      const blocked = selectedToAdd.filter((name) => {
        const reg = allFeatures.find((f) => f.feature_name === name)?.registration;
        return !reg?.computable;
      });
      if (blocked.length) {
        showToast("warning", `${TPL_FEATURE_BLOCK_MSG} (${blocked.join(", ")})`);
        return;
      }
    }
    const merged = Array.from(new Set([...form.features, ...selectedToAdd]));
    setForm({ ...form, features: merged });
    setAddFeatureOpen(false);
    setAddWarnings([]);
    showToast("success", "Feature가 추가되었습니다.");
  };

  useEffect(() => {
    if (!addFeatureOpen || !selectedToAdd.length) {
      setAddWarnings([]);
      return;
    }
    const warnings: string[] = [];
    for (const name of selectedToAdd) {
      const reg = allFeatures.find((f) => f.feature_name === name)?.registration;
      if (!reg) continue;
      if (reg.status === "LEGACY_ALIAS") {
        warnings.push(LEGACY_ALIAS_WARNING_MSG(name, reg.recommended_name || "공식명"));
      } else if (reg.status === "CATALOG_ONLY" || !reg.computable) {
        warnings.push(`${name}: ${CATALOG_ONLY_WARNING_MSG}`);
      }
    }
    setAddWarnings(warnings);
  }, [addFeatureOpen, selectedToAdd, allFeatures]);

  const handleRemoveFeature = (name: string) => {
    setForm({ ...form, features: form.features.filter((f) => f !== name) });
  };

  const handleSave = async () => {
    if (!id || !form.feature_set_name.trim()) {
      showToast("warning", "Feature Set 명을 입력하세요.");
      return;
    }
    const legacyInSet = form.features.filter((name) => featureStatusMap[name]?.status === "LEGACY_ALIAS");
    if (legacyInSet.length) {
      showToast("warning", `레거시 별칭은 저장할 수 없습니다: ${legacyInSet.join(", ")}`);
      return;
    }
    if (!isTplSet) {
      const catalogOnly = form.features.filter(
        (name) => featureStatusMap[name] && !featureStatusMap[name].computable,
      );
      if (catalogOnly.length) {
        const ok = window.confirm(
          `카탈로그 전용(비계산) Feature ${catalogOnly.length}건이 포함되어 있습니다.\n`
          + `${CATALOG_ONLY_WARNING_MSG}\n\n저장하시겠습니까?`,
        );
        if (!ok) return;
      }
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
          {(buildResult.result_summary?.template_generated_feature_count ?? 0) > 0 && (
            <p className="text-emerald-700 text-xs">
              Recipe Engine Build: TEMPLATE {buildResult.result_summary?.template_generated_feature_count}건 생성
              {(buildResult.result_summary?.template_recipe_features as string[] | undefined)?.length ? (
                <span className="font-mono ml-1">
                  ({(buildResult.result_summary?.template_recipe_features as string[]).join(", ")})
                </span>
              ) : null}
            </p>
          )}
          {((buildResult.result_summary?.template_build_failed_features as string[] | undefined)?.length ?? 0) > 0 && (
            <p className="text-amber-800 text-xs">
              TEMPLATE Build 실패: {(buildResult.result_summary?.template_build_failed_features as string[]).join(", ")}
            </p>
          )}
          {((buildResult.result_summary?.template_build_unsupported_features as string[] | undefined)?.length ?? 0) > 0 && (
            <p className="text-amber-800 text-xs">
              TEMPLATE Build 미지원: {(buildResult.result_summary?.template_build_unsupported_features as string[]).join(", ")}
            </p>
          )}
          {(buildResult.result_summary?.missing_feature_count ?? 0) > 0 && (
            <div className="text-amber-800 text-xs mt-1 bg-amber-50 border border-amber-100 rounded p-2">
              미생성 Feature {buildResult.result_summary?.missing_feature_count}건
              {(buildResult.result_summary?.catalog_only_features?.length ?? 0) > 0 && (
                <span> · 카탈로그 전용: {buildResult.result_summary?.catalog_only_features?.join(", ")}</span>
              )}
              {(buildResult.result_summary?.legacy_alias_features?.length ?? 0) > 0 && (
                <span> · 레거시: {buildResult.result_summary?.legacy_alias_features?.join(", ")}</span>
              )}
              <p className="mt-1 text-amber-700">{FEATURE_QUALITY_REGISTRATION_HINT}</p>
              {hasLegacyInSet && (
                <div className="mt-2">
                  <Button variant="secondary" onClick={() => void openReplaceLegacyModal()} disabled={replaceLoading}>
                    {replaceLoading ? "확인 중..." : "공식명으로 대체"}
                  </Button>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {(hasLegacyInSet || buildHasLegacy) && (
        <div className="mb-6 text-xs text-orange-800 bg-orange-50 border border-orange-200 rounded-lg p-3 flex flex-wrap items-start justify-between gap-3">
          <div>
            <p className="font-medium text-orange-900">레거시 Feature명 감지</p>
            <p className="mt-1">{LEGACY_REPLACE_HINT}</p>
            {legacyFeaturesInSet.length > 0 && (
              <p className="mt-1 font-mono text-[11px]">{legacyFeaturesInSet.join(", ")}</p>
            )}
          </div>
          {hasLegacyInSet && (
            <Button onClick={() => void openReplaceLegacyModal()} disabled={replaceLoading}>
              {replaceLoading ? "확인 중..." : "공식명으로 대체"}
            </Button>
          )}
        </div>
      )}

      <div className="bg-white rounded-lg border border-slate-200 p-4">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-semibold text-slate-800">포함 Feature 목록 ({form.features.length})</h3>
          <div className="flex gap-2">
            <Button variant="secondary" icon={<Plus className="w-4 h-4" />} onClick={openAddFeature}>
              Feature 추가
            </Button>
            <Button
              variant="secondary"
              disabled={isTplSet}
              onClick={() => void openAddRecipeFeature()}
            >
              Recipe Feature 추가
            </Button>
          </div>
        </div>
        {isTplSet && (
          <p className="text-xs text-blue-800 bg-blue-50 border border-blue-100 rounded p-2 mb-3">
            {TPL_FEATURE_BLOCK_MSG}
          </p>
        )}
        <DataTable
          columns={[
            { key: "name", header: "Feature명" },
            {
              key: "registration",
              header: "등록 유형",
              render: (r) => (
                <FeatureRegistrationBadge registration={featureStatusMap[String(r.name)]} />
              ),
            },
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
          hasLegacyFeatures={hasLegacyInSet}
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
        {isTplSet && (
          <p className="text-xs text-blue-800 bg-blue-50 border border-blue-100 rounded p-2 mb-3">
            {TPL_FEATURE_BLOCK_MSG}
          </p>
        )}
        <div className="flex flex-wrap gap-2 mb-3">
          <SelectInput
            value={featureFilter}
            onChange={(v) => setFeatureFilter(v as FeatureListFilter)}
            options={[
              { value: "all", label: "전체" },
              { value: "computable", label: "계산 가능" },
              { value: "catalog_only", label: "카탈로그 전용" },
              { value: "legacy", label: "레거시/비권장" },
            ]}
          />
          <div className="flex-1 min-w-[160px]">
            <TextInput
              value={featureSearch}
              onChange={setFeatureSearch}
              placeholder="Feature명·그룹 검색"
            />
          </div>
        </div>
        <div className="max-h-64 overflow-y-auto space-y-2">
          {addWarnings.length > 0 && (
            <div className="text-xs text-amber-800 bg-amber-50 border border-amber-200 rounded p-2 mb-2">
              {addWarnings.map((w) => <div key={w}>{w}</div>)}
            </div>
          )}
          {filteredFeatures.length === 0 && (
            <p className="text-xs text-slate-500 py-4 text-center">조건에 맞는 Feature가 없습니다.</p>
          )}
          {filteredFeatures.map((f) => (
            <label key={f.feature_id} className="flex items-center gap-2 text-sm py-1 border-b border-slate-100">
              <input
                type="checkbox"
                checked={selectedToAdd.includes(f.feature_name)}
                disabled={isAddCheckboxDisabled(f)}
                onChange={(e) => {
                  if (e.target.checked) setSelectedToAdd([...selectedToAdd, f.feature_name]);
                  else setSelectedToAdd(selectedToAdd.filter((n) => n !== f.feature_name));
                }}
              />
              <span className={`font-medium ${isAddCheckboxDisabled(f) ? "text-slate-400" : ""}`}>
                {f.feature_name}
              </span>
              <FeatureRegistrationBadge registration={f.registration} />
              {f.registration?.status === "LEGACY_ALIAS" && f.registration.recommended_name && (
                <span className="text-xs text-orange-700">공식명: {f.registration.recommended_name}</span>
              )}
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
        open={replaceModalOpen}
        title="Legacy Feature 공식명 대체"
        onClose={() => setReplaceModalOpen(false)}
        size="lg"
        footer={
          <>
            <Button variant="secondary" onClick={() => setReplaceModalOpen(false)}>취소</Button>
            <Button onClick={() => void handleApplyLegacyReplace()} disabled={replaceApplying}>
              {replaceApplying ? "적용 중..." : "대체 적용"}
            </Button>
          </>
        }
      >
        {replacePlan && (
          <div className="space-y-3 text-sm">
            <p className="text-slate-600">{replacePlan.message}</p>
            {replacePlan.replacements.length > 0 && (
              <div>
                <p className="text-xs font-semibold text-slate-700 mb-1">대체 예정</p>
                <ul className="text-xs space-y-1">
                  {replacePlan.replacements.map((r) => (
                    <li key={r.from} className="font-mono">
                      {r.from} → {r.to}
                    </li>
                  ))}
                </ul>
              </div>
            )}
            {replacePlan.removed_duplicates.length > 0 && (
              <div className="text-xs text-amber-800 bg-amber-50 border border-amber-100 rounded p-2">
                <p className="font-medium">중복 제거 예정</p>
                <p>{replacePlan.removed_duplicates.join(", ")}</p>
              </div>
            )}
            {replacePlan.warnings.length > 0 && (
              <div className="text-xs text-amber-800 bg-amber-50 border border-amber-100 rounded p-2">
                {replacePlan.warnings.map((w) => <p key={w}>{w}</p>)}
              </div>
            )}
            <div className="text-xs text-slate-500 bg-slate-50 border border-slate-100 rounded p-2">
              <p className="font-medium text-slate-700">적용 후 결과 (미리보기)</p>
              <p className="font-mono mt-1 break-all">{replacePlan.replaced_features.join(", ")}</p>
            </div>
            <p className="text-xs text-slate-600">{LEGACY_REPLACE_AFTER_HINT}</p>
          </div>
        )}
      </Modal>

      <Modal
        open={recipeAddOpen}
        title="Recipe Feature 추가"
        onClose={() => setRecipeAddOpen(false)}
        footer={(
          <>
            <Button variant="secondary" onClick={() => setRecipeAddOpen(false)}>취소</Button>
            <Button disabled={!selectedRecipeId || recipeAddLoading} onClick={() => void handleAddRecipeFeature()}>
              {recipeAddLoading ? "추가 중..." : "추가"}
            </Button>
          </>
        )}
      >
        <p className="text-xs text-violet-800 bg-violet-50 border border-violet-100 rounded p-2 mb-3">
          {R6_BUILD_INFO}
        </p>
        <SelectInput
          value={selectedRecipeId}
          onChange={setSelectedRecipeId}
          options={[
            { value: "", label: "발행된 Recipe 선택" },
            ...publishedRecipes.map((r) => ({
              value: r.recipe_id,
              label: `${r.feature_name} (${r.recipe_type})`,
            })),
          ]}
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
