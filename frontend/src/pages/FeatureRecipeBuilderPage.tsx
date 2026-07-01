import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import {
  createFeatureRecipe,
  getFeatureRecipe,
  previewSavedFeatureRecipe,
  publishFeatureRecipe,
  updateFeatureRecipe,
  validateSavedFeatureRecipe,
} from "@/api/featureRecipes";
import { getColumnRoles } from "@/api/featureColumnRoles";
import { fetchApi, PagedData, postApi, putApi } from "@/api/client";
import { getFeatureRecipeTemplates, previewFeatureRecipe, validateFeatureRecipe } from "@/api/featureRecipeTemplates";
import { Button } from "@/components/Button";
import { DataTable } from "@/components/DataTable";
import { SelectInput, TextInput } from "@/components/SearchPanel";
import { useToast } from "@/hooks/useToast";
import { PageHeader } from "@/layouts/MainLayout";
import type { FeatureColumnRole } from "@/types/featureColumnRoles";
import type { FeatureRecipe } from "@/types/featureRecipes";
import { R5_BUILD_WARNING, RECIPE_PREVIEW_NO_SAVE_NOTE } from "@/types/featureRecipes";
import type { FeatureRecipePreviewResponse, RecipeTemplate } from "@/types/featureRecipeTemplates";
import {
  BUILDER_FUTURE_TYPES,
  BUILDER_SUPPORTED_TYPES,
  recipeStatusClass,
  recipeStatusLabel,
} from "@/utils/featureRecipeFormat";
import { RECIPE_PREVIEW_ROW_STEP_NOTE } from "@/utils/featureRecipeTemplateFormat";

interface MappingItem {
  mapping_id: string;
  mapping_name: string;
  source_id: string;
  columns: { source_column: string; target_column: string }[];
}

const TIME_SERIES = new Set(["LAG", "ROLLING_MEAN", "ROLLING_SUM"]);
const NUMERIC_ROLES = new Set(["NUMERIC_INPUT", "MEASURE", "TARGET"]);

export default function FeatureRecipeBuilderPage() {
  const { recipeId } = useParams();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const { showToast } = useToast();
  const isNew = !recipeId || recipeId === "new";

  const [recipe, setRecipe] = useState<FeatureRecipe | null>(null);
  const [templates, setTemplates] = useState<RecipeTemplate[]>([]);
  const [mappings, setMappings] = useState<MappingItem[]>([]);
  const [columnRoles, setColumnRoles] = useState<FeatureColumnRole[]>([]);
  const [recipeType, setRecipeType] = useState(searchParams.get("recipe_type") || "LAG");
  const [mappingId, setMappingId] = useState(searchParams.get("mapping_id") || "MAP-CSV-001");
  const [sourceColumn, setSourceColumn] = useState(searchParams.get("source_column") || "heat_demand");
  const [entityKey, setEntityKey] = useState("site_id");
  const [timeKey, setTimeKey] = useState("measured_at");
  const [displayName, setDisplayName] = useState("");
  const [description, setDescription] = useState("");
  const [outputFeatureName, setOutputFeatureName] = useState("");
  const [offsetSteps, setOffsetSteps] = useState("24");
  const [windowSteps, setWindowSteps] = useState("24");
  const [minPeriods, setMinPeriods] = useState("24");
  const [granularity, setGranularity] = useState("1h");
  const [includeCurrentRow, setIncludeCurrentRow] = useState(false);
  const [dateParts, setDateParts] = useState<string[]>(["hour"]);
  const [loading, setLoading] = useState(!isNew);
  const [busy, setBusy] = useState("");
  const [validateResult, setValidateResult] = useState<Record<string, unknown> | null>(null);
  const [previewResult, setPreviewResult] = useState<FeatureRecipePreviewResponse | null>(null);

  const loadMappings = useCallback(async () => {
    const res = await fetchApi<PagedData<MappingItem>>("/mappings", { page: 1, size: 50 });
    setMappings((res.items || []) as MappingItem[]);
  }, []);

  const loadTemplates = useCallback(async () => {
    const res = await getFeatureRecipeTemplates({ mapping_id: mappingId, include_availability: true });
    setTemplates(res.items || []);
  }, [mappingId]);

  const loadRoles = useCallback(async () => {
    if (!mappingId) return;
    const res = await getColumnRoles({ mapping_id: mappingId, include_inferred: false });
    setColumnRoles(res.items || []);
    const entity = res.items.find((r) => r.column_role === "ENTITY_KEY")?.source_column;
    const time = res.items.find((r) => r.column_role === "TIME_KEY" || r.column_role === "DATETIME")?.source_column;
    if (entity) setEntityKey(entity);
    if (time) setTimeKey(time);
  }, [mappingId]);

  const loadRecipe = useCallback(async () => {
    if (isNew) return;
    setLoading(true);
    try {
      const row = await getFeatureRecipe(recipeId!);
      setRecipe(row);
      setRecipeType(row.recipe_type);
      setMappingId(row.mapping_id || "");
      setSourceColumn(row.source_columns[0] || "");
      setEntityKey(row.entity_keys?.[0] || "site_id");
      setTimeKey(row.time_key || "measured_at");
      setDisplayName(row.display_name);
      setDescription(row.description || "");
      setOutputFeatureName(row.output_feature_names?.[0] || "");
      const params = row.params || {};
      if (row.recipe_type === "LAG") setOffsetSteps(String(params.offset_steps ?? 24));
      if (TIME_SERIES.has(row.recipe_type)) {
        setWindowSteps(String(params.window_steps ?? 24));
        setMinPeriods(String(params.min_periods ?? params.window_steps ?? 24));
        setGranularity(String(params.granularity ?? "1h"));
        setIncludeCurrentRow(Boolean(params.include_current_row));
      }
      if (row.recipe_type === "DATE_PART") {
        setDateParts((params.parts as string[]) || ["hour"]);
      }
    } catch {
      showToast("error", "Recipe를 불러오지 못했습니다.");
    } finally {
      setLoading(false);
    }
  }, [isNew, recipeId, showToast]);

  useEffect(() => { void loadMappings(); }, [loadMappings]);
  useEffect(() => { void loadTemplates(); }, [loadTemplates]);
  useEffect(() => { void loadRoles(); }, [loadRoles]);
  useEffect(() => { void loadRecipe(); }, [loadRecipe]);

  const buildPayload = useMemo(() => {
    const params: Record<string, unknown> = recipeType === "DATE_PART"
      ? { parts: dateParts }
      : recipeType === "LAG"
        ? { offset_steps: Number(offsetSteps), granularity }
        : TIME_SERIES.has(recipeType)
          ? {
            window_steps: Number(windowSteps),
            min_periods: Number(minPeriods),
            granularity,
            include_current_row: includeCurrentRow,
          }
          : {};
    return {
      mapping_id: mappingId,
      recipe_type: recipeType,
      source_columns: [sourceColumn],
      entity_keys: TIME_SERIES.has(recipeType) || recipeType === "LAG" ? [entityKey] : undefined,
      time_key: recipeType === "DATE_PART" ? sourceColumn : (TIME_SERIES.has(recipeType) || recipeType === "LAG" ? timeKey : undefined),
      params,
      output_feature_name: outputFeatureName || undefined,
      display_name: displayName || undefined,
      description: description || undefined,
    };
  }, [
    dateParts, description, displayName, entityKey, granularity, includeCurrentRow,
    mappingId, minPeriods, offsetSteps, outputFeatureName, recipeType, sourceColumn, timeKey, windowSteps,
  ]);

  const sourceOptions = useMemo(() => {
    const mapping = mappings.find((m) => m.mapping_id === mappingId);
    const cols = mapping?.columns || [];
    const allowed = new Set(
      columnRoles.filter((r) => r.column_role && NUMERIC_ROLES.has(r.column_role)).map((r) => r.source_column),
    );
    return cols
      .filter((c) => !allowed.size || allowed.has(c.source_column) || recipeType === "DATE_PART")
      .map((c) => ({ value: c.source_column, label: c.source_column }));
  }, [columnRoles, mappingId, mappings, recipeType]);

  const runValidate = async () => {
    setBusy("validate");
    try {
      const res = isNew || !recipe
        ? await validateFeatureRecipe(buildPayload)
        : (await validateSavedFeatureRecipe(recipe.recipe_id)).validation;
      setValidateResult(res as unknown as Record<string, unknown>);
      if (res.output_feature_names && !outputFeatureName) {
        const names = res.output_feature_names as string[];
        if (names[0]) setOutputFeatureName(names[0]);
      }
      if (!res.valid) showToast("warning", "검증에 실패했습니다.");
      else showToast("success", "검증에 성공했습니다.");
    } catch {
      showToast("error", "검증 요청에 실패했습니다.");
    } finally {
      setBusy("");
    }
  };

  const runPreview = async () => {
    setBusy("preview");
    try {
      if (recipe?.recipe_id && recipe.status !== "PUBLISHED") {
        const res = await previewSavedFeatureRecipe(recipe.recipe_id, 50);
        setPreviewResult(res.preview);
        setRecipe(res.recipe);
      } else {
        const res = await previewFeatureRecipe({ ...buildPayload, sample_size: 50 });
        setPreviewResult(res);
      }
      showToast("success", "Preview를 실행했습니다.");
    } catch {
      showToast("error", "Preview 요청에 실패했습니다.");
    } finally {
      setBusy("");
    }
  };

  const saveDraft = async () => {
    setBusy("save");
    try {
      if (recipe?.recipe_id) {
        const updated = await updateFeatureRecipe(recipe.recipe_id, buildPayload);
        setRecipe(updated);
        showToast("success", "Recipe가 저장되었습니다.");
      } else {
        const created = await createFeatureRecipe(buildPayload);
        setRecipe(created);
        showToast("success", "Recipe 초안이 저장되었습니다.");
        navigate(`/feature-recipes/${created.recipe_id}`, { replace: true });
      }
    } catch {
      showToast("error", "저장에 실패했습니다.");
    } finally {
      setBusy("");
    }
  };

  const runPublish = async () => {
    if (!recipe?.recipe_id) {
      showToast("warning", "먼저 초안을 저장하세요.");
      return;
    }
    setBusy("publish");
    try {
      const res = await publishFeatureRecipe(recipe.recipe_id);
      setRecipe(res.recipe);
      showToast("success", "Recipe가 발행되었습니다.");
      if (res.warnings?.length) showToast("warning", res.warnings.join(" "));
    } catch {
      showToast("error", "발행에 실패했습니다.");
    } finally {
      setBusy("");
    }
  };

  const previewColumns = previewResult?.preview_rows?.length
    ? Object.keys(previewResult.preview_rows[0]).map((k) => ({ key: k, header: k }))
    : [];

  if (loading) return <p className="text-sm text-slate-500 p-4">불러오는 중...</p>;

  return (
    <div>
      <PageHeader
        title="Feature Recipe Builder"
        description="Template 기반 Feature Recipe를 생성·검증·미리보기·저장·발행합니다."
        actions={<Link to="/feature-recipes" className="text-sm text-blue-600 hover:underline">Recipe 목록</Link>}
      />

      <div className="mb-4 text-xs text-slate-600 bg-blue-50 border border-blue-200 rounded-lg p-3 space-y-1">
        <p>{R5_BUILD_WARNING}</p>
        <p>{RECIPE_PREVIEW_NO_SAVE_NOTE}</p>
        {TIME_SERIES.has(recipeType) && <p>{RECIPE_PREVIEW_ROW_STEP_NOTE}</p>}
      </div>

      {recipe && (
        <div className="mb-4 flex items-center gap-2 text-sm">
          <span className="font-mono text-slate-600">{recipe.recipe_id}</span>
          <span className={`text-[10px] px-1 py-0.5 rounded border ${recipeStatusClass(recipe.status)}`}>
            {recipeStatusLabel(recipe.status)}
          </span>
          {recipe.feature_name && <span className="text-slate-700">→ {recipe.feature_name}</span>}
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <section className="lg:col-span-1 border border-slate-200 rounded-lg p-4 bg-white space-y-3">
          <h3 className="text-sm font-semibold text-slate-800">1. 템플릿</h3>
          <div className="space-y-1">
            {BUILDER_SUPPORTED_TYPES.map((t) => (
              <button
                key={t}
                type="button"
                disabled={recipe?.status === "PUBLISHED"}
                className={`w-full text-left text-xs px-2 py-1.5 rounded border ${recipeType === t ? "border-blue-400 bg-blue-50" : "border-slate-200"}`}
                onClick={() => setRecipeType(t)}
              >
                {t}
              </button>
            ))}
            {BUILDER_FUTURE_TYPES.map((t) => (
              <div key={t} className="text-[10px] text-slate-400 px-2 py-1">{t} — 후속 단계</div>
            ))}
          </div>
        </section>

        <section className="lg:col-span-2 border border-slate-200 rounded-lg p-4 bg-white space-y-4">
          <h3 className="text-sm font-semibold text-slate-800">2. 매핑·컬럼·파라미터</h3>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <div className="text-xs text-slate-500 mb-1">매핑</div>
              <SelectInput
                value={mappingId}
                onChange={setMappingId}
                options={mappings.map((m) => ({ value: m.mapping_id, label: m.mapping_name }))}
              />
            </div>
            <div>
              <div className="text-xs text-slate-500 mb-1">Source column</div>
              <SelectInput
                value={sourceColumn}
                onChange={setSourceColumn}
                options={sourceOptions}
              />
            </div>
          </div>

          {(recipeType === "LAG" || TIME_SERIES.has(recipeType)) && (
            <div className="grid grid-cols-2 gap-3">
              <div>
                <div className="text-xs text-slate-500 mb-1">Entity key</div>
                <TextInput value={entityKey} onChange={setEntityKey} />
              </div>
              <div>
                <div className="text-xs text-slate-500 mb-1">Time key</div>
                <TextInput value={timeKey} onChange={setTimeKey} />
              </div>
            </div>
          )}

          {recipeType === "LAG" && (
            <div className="grid grid-cols-2 gap-3">
              <div>
                <div className="text-xs text-slate-500 mb-1">offset_steps</div>
                <TextInput value={offsetSteps} onChange={setOffsetSteps} />
              </div>
              <div>
                <div className="text-xs text-slate-500 mb-1">granularity</div>
                <SelectInput value={granularity} onChange={setGranularity} options={[
                  { value: "1h", label: "1h" }, { value: "1d", label: "1d" },
                ]} />
              </div>
            </div>
          )}

          {TIME_SERIES.has(recipeType) && recipeType !== "LAG" && (
            <div className="space-y-2">
              <div className="grid grid-cols-3 gap-2">
                <TextInput value={windowSteps} onChange={setWindowSteps} placeholder="window" />
                <TextInput value={minPeriods} onChange={setMinPeriods} placeholder="min_periods" />
                <SelectInput value={granularity} onChange={setGranularity} options={[{ value: "1h", label: "1h" }]} />
              </div>
              <label className="flex items-center gap-2 text-xs">
                <input type="checkbox" checked={includeCurrentRow} onChange={(e) => setIncludeCurrentRow(e.target.checked)} />
                include_current_row
              </label>
            </div>
          )}

          {recipeType === "DATE_PART" && (
            <div className="flex flex-wrap gap-2 text-xs">
              {["hour", "day_of_week", "month"].map((p) => (
                <label key={p} className="flex items-center gap-1">
                  <input
                    type="checkbox"
                    checked={dateParts.includes(p)}
                    onChange={() => setDateParts((prev) => (
                      prev.includes(p) ? prev.filter((x) => x !== p) : [...prev, p]
                    ))}
                  />
                  {p}
                </label>
              ))}
              <p className="text-amber-700 w-full">R5 Publish는 output 1개만 허용합니다. part 1개만 선택하세요.</p>
            </div>
          )}

          <div className="grid grid-cols-2 gap-3">
            <div>
              <div className="text-xs text-slate-500 mb-1">표시명</div>
              <TextInput value={displayName} onChange={setDisplayName} />
            </div>
            <div>
              <div className="text-xs text-slate-500 mb-1">output feature name</div>
              <TextInput value={outputFeatureName} onChange={setOutputFeatureName} />
            </div>
          </div>
          <div>
            <div className="text-xs text-slate-500 mb-1">설명 (선택)</div>
            <TextInput value={description} onChange={setDescription} />
          </div>
        </section>
      </div>

      <div className="mt-4 flex flex-wrap gap-2">
        <Button variant="secondary" disabled={!!busy || recipe?.status === "PUBLISHED"} onClick={runValidate}>
          {busy === "validate" ? "검증 중..." : "검증"}
        </Button>
        <Button variant="secondary" disabled={!!busy} onClick={runPreview}>
          {busy === "preview" ? "Preview..." : "미리보기"}
        </Button>
        <Button variant="primary" disabled={!!busy || recipe?.status === "PUBLISHED"} onClick={saveDraft}>
          {busy === "save" ? "저장 중..." : "초안 저장"}
        </Button>
        <Button variant="primary" disabled={!!busy || recipe?.status === "PUBLISHED"} onClick={runPublish}>
          {busy === "publish" ? "발행 중..." : "발행"}
        </Button>
      </div>

      {validateResult && (
        <div className="mt-4 text-xs border border-slate-200 rounded p-3 bg-slate-50">
          <p className="font-medium">검증: {validateResult.valid ? "성공" : "실패"}</p>
          {(validateResult.errors as { message: string }[] | undefined)?.map((e) => (
            <p key={e.message} className="text-red-700">{e.message}</p>
          ))}
        </div>
      )}

      {previewResult && (
        <div className="mt-4 border border-slate-200 rounded p-3 bg-white">
          <p className="text-sm font-medium mb-2">Preview 결과</p>
          {previewResult.preview_rows?.length ? (
            <DataTable columns={previewColumns} data={previewResult.preview_rows as Record<string, unknown>[]} />
          ) : (
            <p className="text-xs text-slate-400">표시할 행이 없습니다.</p>
          )}
        </div>
      )}
    </div>
  );
}
