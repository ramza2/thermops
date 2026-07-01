import type {
  FeatureRecipePreviewRequest,
  FeatureRecipePreviewResponse,
  RecipeTemplate,
} from "@/types/featureRecipeTemplates";
import type { FeatureColumnRole } from "@/types/featureColumnRoles";
import { previewFeatureRecipe } from "@/api/featureRecipeTemplates";
import { Button } from "@/components/Button";
import { DataTable } from "@/components/DataTable";
import { Modal } from "@/components/Modal";
import { SelectInput, TextInput } from "@/components/SearchPanel";
import {
  RECIPE_PREVIEW_NO_SAVE_NOTE,
  RECIPE_PREVIEW_ROW_STEP_NOTE,
  RECIPE_PREVIEW_R4_NOTE,
} from "@/utils/featureRecipeTemplateFormat";
import { useCallback, useEffect, useMemo, useState } from "react";

const DATE_PART_OPTIONS = [
  { value: "hour", label: "hour (0~23)" },
  { value: "day_of_week", label: "day_of_week (월=0)" },
  { value: "month", label: "month (1~12)" },
  { value: "day", label: "day (1~31)" },
  { value: "is_weekend", label: "is_weekend (0/1)" },
  { value: "week_of_year", label: "week_of_year" },
];

const SAMPLE_SIZE_OPTIONS = [
  { value: "50", label: "50행" },
  { value: "100", label: "100행" },
  { value: "200", label: "200행" },
];

const GRANULARITY_OPTIONS = [
  { value: "1h", label: "1h" },
  { value: "1d", label: "1d" },
  { value: "1w", label: "1w" },
];

const LAG_OFFSET_PRESETS = [1, 3, 6, 12, 24, 168];
const ROLLING_WINDOW_PRESETS = [3, 6, 12, 24, 168];

const NUMERIC_ROLES = new Set(["NUMERIC_INPUT", "MEASURE", "TARGET"]);
const TIME_SERIES_TYPES = new Set(["LAG", "ROLLING_MEAN", "ROLLING_SUM"]);

interface MappingColumn {
  source_column: string;
  target_column: string;
}

interface Props {
  open: boolean;
  onClose: () => void;
  template: RecipeTemplate;
  mappingId: string;
  columns: MappingColumn[];
  columnRoles: FeatureColumnRole[];
}

export function FeatureRecipePreviewModal({
  open,
  onClose,
  template,
  mappingId,
  columns,
  columnRoles,
}: Props) {
  const [sourceColumn, setSourceColumn] = useState("");
  const [entityKey, setEntityKey] = useState("");
  const [timeKey, setTimeKey] = useState("");
  const [targetColumn, setTargetColumn] = useState("");
  const [selectedParts, setSelectedParts] = useState<string[]>(["hour"]);
  const [sampleSize, setSampleSize] = useState("100");
  const [offsetSteps, setOffsetSteps] = useState("24");
  const [windowSteps, setWindowSteps] = useState("24");
  const [minPeriods, setMinPeriods] = useState("24");
  const [granularity, setGranularity] = useState("1h");
  const [includeCurrentRow, setIncludeCurrentRow] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<FeatureRecipePreviewResponse | null>(null);

  const numericColumns = useMemo(
    () => columnRoles
      .filter((r) => r.column_role && NUMERIC_ROLES.has(r.column_role))
      .map((r) => r.source_column)
      .filter(Boolean),
    [columnRoles],
  );

  const entityKeyOptions = useMemo(
    () => columnRoles
      .filter((r) => r.column_role === "ENTITY_KEY")
      .map((r) => ({ value: r.source_column, label: r.source_column })),
    [columnRoles],
  );

  const timeKeyOptions = useMemo(
    () => columnRoles
      .filter((r) => r.column_role === "TIME_KEY" || r.column_role === "DATETIME")
      .map((r) => ({ value: r.source_column, label: r.source_column })),
    [columnRoles],
  );

  const columnOptions = useMemo(
    () => columns.filter((c) => c.source_column).map((c) => ({
      value: c.source_column,
      label: `${c.source_column} → ${c.target_column}`,
    })),
    [columns],
  );

  const sourceOptions = useMemo(() => {
    const allowed = new Set(numericColumns);
    const filtered = columnOptions.filter((c) => allowed.has(c.value));
    return filtered.length ? filtered : columnOptions;
  }, [columnOptions, numericColumns]);

  const isTimeSeries = TIME_SERIES_TYPES.has(template.recipe_type);

  useEffect(() => {
    if (!open) return;
    setResult(null);
    setError("");
    const defaultEntity = entityKeyOptions[0]?.value ?? "site_id";
    const defaultTime = timeKeyOptions[0]?.value
      ?? columns.find((c) => c.target_column === "measured_at")?.source_column
      ?? "measured_at";
    const defaultSource = template.recipe_type === "DATE_PART"
      ? defaultTime
      : sourceOptions.find((c) => c.value === "heat_demand")?.value
        ?? sourceOptions[0]?.value
        ?? "";
    const defaultTarget = columnRoles.find((r) => r.column_role === "TARGET")?.source_column ?? "";

    setEntityKey(defaultEntity);
    setTimeKey(defaultTime);
    setTargetColumn(defaultTarget);
    setSourceColumn(defaultSource);
    setSelectedParts(["hour"]);
    setSampleSize("100");
    setOffsetSteps("24");
    setWindowSteps("24");
    setMinPeriods("24");
    setGranularity("1h");
    setIncludeCurrentRow(false);
  }, [open, template.recipe_type, columns, columnRoles, entityKeyOptions, timeKeyOptions, sourceOptions]);

  const togglePart = (part: string) => {
    setSelectedParts((prev) => (
      prev.includes(part) ? prev.filter((p) => p !== part) : [...prev, part]
    ));
  };

  const runPreview = useCallback(async () => {
    if (!sourceColumn) {
      setError("source column을 선택하세요.");
      return;
    }
    if (isTimeSeries && (!entityKey || !timeKey)) {
      setError("entity key와 time key가 필요합니다.");
      return;
    }
    setLoading(true);
    setError("");
    try {
      const payload: FeatureRecipePreviewRequest = {
        mapping_id: mappingId,
        recipe_type: template.recipe_type,
        source_columns: [sourceColumn],
        sample_size: Number(sampleSize),
      };
      if (template.recipe_type === "DATE_PART") {
        payload.time_key = sourceColumn;
        payload.params = { parts: selectedParts.length ? selectedParts : ["hour"] };
      } else if (isTimeSeries) {
        payload.entity_keys = [entityKey];
        payload.time_key = timeKey;
        payload.target_column = targetColumn || undefined;
        payload.params = {
          granularity,
          ...(template.recipe_type === "LAG"
            ? { offset_steps: Number(offsetSteps), include_current_row: false }
            : {
              window_steps: Number(windowSteps),
              min_periods: Number(minPeriods),
              include_current_row: includeCurrentRow,
            }),
        };
      }
      const res = await previewFeatureRecipe(payload);
      setResult(res);
      if (!res.valid && res.errors?.length) {
        setError(res.errors[0]?.message ?? "Preview 검증에 실패했습니다.");
      }
    } catch {
      setError("Preview 요청에 실패했습니다.");
      setResult(null);
    } finally {
      setLoading(false);
    }
  }, [
    entityKey,
    granularity,
    includeCurrentRow,
    isTimeSeries,
    mappingId,
    minPeriods,
    offsetSteps,
    sampleSize,
    selectedParts,
    sourceColumn,
    targetColumn,
    template.recipe_type,
    timeKey,
    windowSteps,
  ]);

  const previewColumns = useMemo(() => {
    if (!result?.preview_rows?.length) return [];
    const keys = Object.keys(result.preview_rows[0]);
    return keys.map((key) => ({
      key,
      header: key,
      render: (row: Record<string, unknown>) => String(row[key] ?? ""),
    }));
  }, [result]);

  const featStats = useMemo(() => {
    const name = result?.output_feature_names?.[0];
    if (!name || !result?.stats?.features) return null;
    return result.stats.features[name];
  }, [result]);

  return (
    <Modal
      open={open}
      title={`Recipe Preview — ${template.display_name}`}
      onClose={onClose}
      size="lg"
      footer={(
        <>
          <Button variant="secondary" onClick={onClose}>닫기</Button>
          <Button variant="primary" disabled={loading} onClick={runPreview}>
            {loading ? "실행 중..." : "Preview 실행"}
          </Button>
        </>
      )}
    >
      <div className="space-y-4 text-sm">
        <p className="text-xs text-slate-500">{RECIPE_PREVIEW_NO_SAVE_NOTE}</p>
        {isTimeSeries && (
          <>
            <p className="text-xs text-slate-500">{RECIPE_PREVIEW_ROW_STEP_NOTE}</p>
            <p className="text-xs text-slate-500">{RECIPE_PREVIEW_R4_NOTE}</p>
          </>
        )}

        <div>
          <div className="text-xs font-medium text-slate-700 mb-1">Source column</div>
          <SelectInput
            value={sourceColumn}
            onChange={setSourceColumn}
            options={[{ value: "", label: "선택" }, ...sourceOptions]}
          />
        </div>

        {isTimeSeries && (
          <>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <div className="text-xs font-medium text-slate-700 mb-1">Entity key</div>
                <SelectInput
                  value={entityKey}
                  onChange={setEntityKey}
                  options={[{ value: "", label: "선택" }, ...entityKeyOptions]}
                />
              </div>
              <div>
                <div className="text-xs font-medium text-slate-700 mb-1">Time key</div>
                <SelectInput
                  value={timeKey}
                  onChange={setTimeKey}
                  options={[{ value: "", label: "선택" }, ...timeKeyOptions]}
                />
              </div>
            </div>
            <div>
              <div className="text-xs font-medium text-slate-700 mb-1">Granularity</div>
              <SelectInput value={granularity} onChange={setGranularity} options={GRANULARITY_OPTIONS} />
            </div>
            {template.recipe_type === "LAG" ? (
              <div>
                <div className="text-xs font-medium text-slate-700 mb-1">offset_steps</div>
                <div className="flex flex-wrap gap-1 mb-2">
                  {LAG_OFFSET_PRESETS.map((n) => (
                    <Button key={n} variant="secondary" onClick={() => setOffsetSteps(String(n))}>
                      {n}
                    </Button>
                  ))}
                </div>
                <TextInput value={offsetSteps} onChange={setOffsetSteps} placeholder="24" />
              </div>
            ) : (
              <div className="space-y-2">
                <div>
                  <div className="text-xs font-medium text-slate-700 mb-1">window_steps</div>
                  <div className="flex flex-wrap gap-1 mb-2">
                    {ROLLING_WINDOW_PRESETS.map((n) => (
                      <Button
                        key={n}
                        variant="secondary"
                        onClick={() => {
                          setWindowSteps(String(n));
                          setMinPeriods(String(n));
                        }}
                      >
                        {n}
                      </Button>
                    ))}
                  </div>
                  <TextInput value={windowSteps} onChange={setWindowSteps} placeholder="24" />
                </div>
                <div>
                  <div className="text-xs font-medium text-slate-700 mb-1">min_periods</div>
                  <TextInput value={minPeriods} onChange={setMinPeriods} placeholder="24" />
                </div>
                <label className="flex items-center gap-2 text-xs text-slate-600">
                  <input
                    type="checkbox"
                    checked={includeCurrentRow}
                    onChange={(e) => setIncludeCurrentRow(e.target.checked)}
                  />
                  include_current_row (기본 false 권장)
                </label>
              </div>
            )}
          </>
        )}

        {template.recipe_type === "DATE_PART" && (
          <div>
            <div className="text-xs font-medium text-slate-700 mb-2">DATE_PART parts</div>
            <div className="flex flex-wrap gap-2">
              {DATE_PART_OPTIONS.map((opt) => (
                <label key={opt.value} className="flex items-center gap-1 text-xs text-slate-600">
                  <input
                    type="checkbox"
                    checked={selectedParts.includes(opt.value)}
                    onChange={() => togglePart(opt.value)}
                  />
                  {opt.label}
                </label>
              ))}
            </div>
          </div>
        )}

        <div>
          <div className="text-xs font-medium text-slate-700 mb-1">Sample size</div>
          <SelectInput value={sampleSize} onChange={setSampleSize} options={SAMPLE_SIZE_OPTIONS} />
        </div>

        {error && (
          <p className="text-xs text-red-700 bg-red-50 border border-red-200 rounded p-2">{error}</p>
        )}

        {result && (
          <div className="space-y-3 border-t border-slate-100 pt-3">
            <div className="text-xs text-slate-600">
              <span className="font-medium">출력 Feature:</span>
              {" "}
              {(result.output_feature_names ?? result.generated_feature_names ?? []).join(", ") || "-"}
            </div>

            {result.reusable_existing_features?.length ? (
              <div className="text-xs text-blue-800 bg-blue-50 border border-blue-200 rounded p-2">
                기존 Feature 재사용 가능:
                {" "}
                {result.reusable_existing_features.map((r) => r.feature_name).join(", ")}
              </div>
            ) : null}

            {featStats && (
              <div className="text-xs text-slate-600 space-y-1">
                <div>
                  샘플 {result.stats.row_count}행
                  {result.quality_preview?.estimated_status && (
                    <span className="ml-2">품질 추정: {result.quality_preview.estimated_status}</span>
                  )}
                </div>
                <div>
                  null {featStats.null_count} ({(featStats.null_ratio * 100).toFixed(1)}%)
                  {featStats.insufficient_history_count != null && (
                    <span className="ml-2">이력부족 null: {featStats.insufficient_history_count}</span>
                  )}
                </div>
              </div>
            )}

            {[...(result.time_gap_warnings ?? []), ...(result.leakage_warnings ?? []), ...(result.history_warnings ?? []), ...(result.warnings ?? [])].map((w) => (
              <p key={w} className="text-xs text-amber-700">• {w}</p>
            ))}

            {result.preview_rows?.length ? (
              <DataTable
                columns={previewColumns}
                data={result.preview_rows as unknown as Record<string, unknown>[]}
              />
            ) : (
              <p className="text-xs text-slate-400">표시할 Preview 행이 없습니다.</p>
            )}

            {result.lineage_preview && (
              <details className="text-xs text-slate-500">
                <summary className="cursor-pointer font-medium text-slate-700">Lineage preview</summary>
                <pre className="mt-1 p-2 bg-slate-50 rounded overflow-x-auto text-[10px]">
                  {JSON.stringify(result.lineage_preview, null, 2)}
                </pre>
              </details>
            )}
          </div>
        )}
      </div>
    </Modal>
  );
}
