import type {
  FeatureRecipePreviewRequest,
  FeatureRecipePreviewResponse,
  RecipeTemplate,
} from "@/types/featureRecipeTemplates";
import { previewFeatureRecipe } from "@/api/featureRecipeTemplates";
import { Button } from "@/components/Button";
import { DataTable } from "@/components/DataTable";
import { Modal } from "@/components/Modal";
import { SelectInput } from "@/components/SearchPanel";
import { RECIPE_PREVIEW_NO_SAVE_NOTE } from "@/utils/featureRecipeTemplateFormat";
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
}

export function FeatureRecipePreviewModal({
  open,
  onClose,
  template,
  mappingId,
  columns,
}: Props) {
  const [sourceColumn, setSourceColumn] = useState("");
  const [selectedParts, setSelectedParts] = useState<string[]>(["hour"]);
  const [sampleSize, setSampleSize] = useState("100");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<FeatureRecipePreviewResponse | null>(null);

  const columnOptions = useMemo(
    () => columns.filter((c) => c.source_column).map((c) => ({
      value: c.source_column,
      label: `${c.source_column} → ${c.target_column}`,
    })),
    [columns],
  );

  useEffect(() => {
    if (!open) return;
    setResult(null);
    setError("");
    const defaultCol = template.recipe_type === "DATE_PART"
      ? columns.find((c) => c.target_column === "measured_at")?.source_column
        ?? columns[0]?.source_column
        ?? ""
      : columns.find((c) => c.source_column === "heat_demand")?.source_column
        ?? columns.find((c) => c.source_column === "supply_temp")?.source_column
        ?? columns[0]?.source_column
        ?? "";
    setSourceColumn(defaultCol);
    setSelectedParts(["hour"]);
    setSampleSize("100");
  }, [open, template.recipe_type, columns]);

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
  }, [mappingId, sampleSize, selectedParts, sourceColumn, template.recipe_type]);

  const previewColumns = useMemo(() => {
    if (!result?.preview_rows?.length) return [];
    const keys = Object.keys(result.preview_rows[0]);
    return keys.map((key) => ({
      key,
      header: key,
      render: (row: Record<string, unknown>) => String(row[key] ?? ""),
    }));
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

        <div>
          <div className="text-xs font-medium text-slate-700 mb-1">Source column</div>
          <SelectInput
            value={sourceColumn}
            onChange={setSourceColumn}
            options={[{ value: "", label: "선택" }, ...columnOptions]}
          />
        </div>

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
          <SelectInput
            value={sampleSize}
            onChange={setSampleSize}
            options={SAMPLE_SIZE_OPTIONS}
          />
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

            {result.warnings?.map((w) => (
              <p key={w} className="text-xs text-amber-700">• {w}</p>
            ))}

            {result.stats && (
              <div className="text-xs text-slate-600">
                샘플 {result.stats.row_count}행
                {result.quality_preview?.estimated_status && (
                  <span className="ml-2">품질 추정: {result.quality_preview.estimated_status}</span>
                )}
              </div>
            )}

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
