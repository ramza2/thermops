import { useState } from "react";
import {
  SCHEMA_KEY_HELPER_HINT,
  SCHEMA_KEY_HELPER_PREVIEW_HINT,
  formatConflictKeysLabel,
  type SchemaKeyMappingSummary,
} from "@/utils/schemaKeyMappingHelper";

export type VpSchemaKeyMappingHelperProps = {
  summary: SchemaKeyMappingSummary;
  disabled?: boolean;
  onApplyRecommendedKeys?: (keys: string[]) => void;
  defaultOpen?: boolean;
};

export function VpSchemaKeyMappingHelper({
  summary,
  disabled,
  onApplyRecommendedKeys,
  defaultOpen = true,
}: VpSchemaKeyMappingHelperProps) {
  const [open, setOpen] = useState(defaultOpen);

  return (
    <div
      className="rounded-md border border-violet-200 bg-violet-50/40 p-2.5 space-y-2"
      data-testid="visual-pipeline-schema-key-helper"
      data-status={summary.status}
      data-key-compare={summary.keyCompareState}
    >
      <div className="flex items-start justify-between gap-2">
        <div>
          <div className="text-[11px] font-semibold text-slate-800">Schema / Key Helper</div>
          <p className="text-[10px] text-slate-500 mt-0.5">{SCHEMA_KEY_HELPER_HINT}</p>
        </div>
        <button
          type="button"
          className="inline-flex items-center justify-center h-7 px-2 text-[10px] font-medium text-slate-600 hover:bg-white/80 rounded-md border border-slate-200 bg-white"
          data-testid="visual-pipeline-schema-key-helper-toggle"
          onClick={() => setOpen((v) => !v)}
        >
          {open ? "접기" : "펼치기"}
        </button>
      </div>

      {!open ? null : (
        <div className="space-y-2" data-testid="visual-pipeline-schema-key-helper-body">
          <p
            className="text-[10px] text-slate-600"
            data-testid="visual-pipeline-schema-key-helper-status"
          >
            {summary.statusMessage}
          </p>

          <div
            className="rounded border border-slate-200 bg-white px-2 py-1.5 space-y-1"
            data-testid="visual-pipeline-schema-key-helper-summary"
          >
            <div className="text-[10px] text-slate-700">
              Source {summary.sourceColumnCount}개 / Target {summary.targetColumnCount}개 / 매칭{" "}
              {summary.matchedCount}개
            </div>
            <div className="text-[10px] text-slate-600">
              누락 {summary.missingTargetCount}개 · Source만 {summary.unmatchedSourceCount}개 · 타입
              확인 {summary.typeMismatchCount}개 · 모호 {summary.ambiguousCount}개
            </div>
            <div className="text-[10px] text-slate-700" data-testid="visual-pipeline-schema-key-helper-current-keys">
              현재 기준키: {formatConflictKeysLabel(summary.currentConflictKeys)}
            </div>
            <div
              className="text-[10px] text-slate-700"
              data-testid="visual-pipeline-schema-key-helper-recommended-keys"
            >
              추천 기준키: {formatConflictKeysLabel(summary.recommendedConflictKeys)}
            </div>
            <div
              className="text-[10px] text-slate-600"
              data-testid="visual-pipeline-schema-key-helper-recommend-reason"
            >
              {summary.keyRecommendationReason}
            </div>
            <div
              className="text-[10px] font-medium text-slate-800"
              data-testid="visual-pipeline-schema-key-helper-key-compare"
            >
              상태: {summary.keyCompareMessage}
            </div>
            {summary.keyValidationMessage && (
              <div
                className="text-[10px] text-slate-500"
                data-testid="visual-pipeline-schema-key-helper-key-validation"
                data-overall={summary.keyValidationLevel}
              >
                검증: [{summary.keyValidationLevel}] {summary.keyValidationMessage}
              </div>
            )}
          </div>

          {summary.canApplyRecommendedKeys ? (
            <button
              type="button"
              className="inline-flex items-center justify-center h-8 px-2.5 text-xs font-medium rounded-md bg-violet-700 text-white hover:bg-violet-800 disabled:opacity-50"
              disabled={disabled}
              data-testid="visual-pipeline-schema-key-helper-apply"
              onClick={() => onApplyRecommendedKeys?.(summary.recommendedConflictKeys)}
            >
              추천 기준키 적용
            </button>
          ) : (
            <p
              className="text-[10px] text-slate-500"
              data-testid="visual-pipeline-schema-key-helper-apply-unavailable"
            >
              {summary.recommendedConflictKeys.length
                ? "현재 기준키가 추천과 같거나 적용할 수 없습니다."
                : "추천 기준키가 없어 적용 버튼이 비활성입니다. Target 컬럼을 직접 선택하세요."}
            </p>
          )}

          <p className="text-[10px] text-slate-500" data-testid="visual-pipeline-schema-key-helper-preview-hint">
            {SCHEMA_KEY_HELPER_PREVIEW_HINT}
          </p>

          {summary.rows.length > 0 ? (
            <div className="overflow-x-auto" data-testid="visual-pipeline-schema-key-helper-table">
              <table className="w-full text-[10px] text-left">
                <thead className="text-slate-500">
                  <tr>
                    <th className="py-1 pr-1 font-medium">Source</th>
                    <th className="py-1 pr-1 font-medium">Target</th>
                    <th className="py-1 pr-1 font-medium">상태</th>
                    <th className="py-1 font-medium">Key</th>
                  </tr>
                </thead>
                <tbody>
                  {summary.rows.slice(0, 40).map((row, idx) => (
                    <tr
                      key={`${row.sourceColumn || ""}-${row.targetColumn || ""}-${idx}`}
                      className="border-t border-slate-100"
                      data-testid={`visual-pipeline-schema-key-helper-row-${idx}`}
                      data-match-status={row.matchStatus}
                    >
                      <td className="py-1 pr-1 font-mono text-slate-700">
                        {row.sourceColumn || "-"}
                        {row.sourceType ? (
                          <span className="text-slate-400"> ({row.sourceType})</span>
                        ) : null}
                      </td>
                      <td className="py-1 pr-1 font-mono text-slate-700">
                        {row.targetColumn || "-"}
                        {row.targetType ? (
                          <span className="text-slate-400"> ({row.targetType})</span>
                        ) : null}
                      </td>
                      <td className="py-1 pr-1 text-slate-600">{row.matchLabel}</td>
                      <td className="py-1 text-slate-600">
                        {row.isRecommendedKey ? "추천" : ""}
                        {row.isRecommendedKey && row.isCurrentKey ? " · " : ""}
                        {row.isCurrentKey ? "현재" : ""}
                        {!row.isRecommendedKey && !row.isCurrentKey ? "-" : ""}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {summary.rows.length > 40 && (
                <p className="text-[9px] text-slate-400 mt-1">상위 40개만 표시합니다.</p>
              )}
            </div>
          ) : (
            <p className="text-[10px] text-slate-500" data-testid="visual-pipeline-schema-key-helper-empty-rows">
              비교할 Source/Target 컬럼이 없습니다.
            </p>
          )}
        </div>
      )}
    </div>
  );
}
