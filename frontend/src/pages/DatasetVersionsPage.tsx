import { useEffect, useState } from "react";
import { Archive, Eye, Star, Search } from "lucide-react";
import { fetchApi, postApi } from "@/api/client";
import { Button } from "@/components/Button";
import { DataTable } from "@/components/DataTable";
import type { Column } from "@/components/DataTable";
import { Modal } from "@/components/Modal";
import { SelectInput } from "@/components/SearchPanel";
import { LoadingState, ErrorState } from "@/components/Pagination";
import { useToast } from "@/hooks/useToast";
import { PageHeader } from "@/layouts/MainLayout";
import {
  BUILD_SCOPE_LABELS,
  DATASET_VERSION_ROLE_LABELS,
  DATASET_VERSION_STATUS_LABELS,
  EMPTY_MESSAGES,
  HELP_TEXTS,
  PAGE_DESCRIPTIONS,
  PAGE_TITLES,
  R9_S2_3_NOTE,
  buildScopeLabel,
  datasetVersionRoleLabel,
  datasetVersionStatusLabel,
} from "@/constants/displayLabels";
import type {
  DatasetVersion,
  DatasetVersionCleanupPreview,
  DatasetVersionSelectionPreview,
} from "@/types/datasetVersions";

interface FeatureSetOption {
  feature_set_id: string;
  feature_set_name: string;
}

export default function DatasetVersionsPage() {
  const { showToast } = useToast();
  const [items, setItems] = useState<DatasetVersion[]>([]);
  const [featureSets, setFeatureSets] = useState<FeatureSetOption[]>([]);
  const [filterFs, setFilterFs] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [detail, setDetail] = useState<DatasetVersion | null>(null);
  const [selectionPreview, setSelectionPreview] = useState<DatasetVersionSelectionPreview | null>(null);
  const [cleanupPreview, setCleanupPreview] = useState<DatasetVersionCleanupPreview | null>(null);
  const [actionLoading, setActionLoading] = useState(false);

  const load = async () => {
    setLoading(true);
    setError("");
    try {
      const params: Record<string, string> = {};
      if (filterFs) params.feature_set_id = filterFs;
      const [versions, fsList] = await Promise.all([
        fetchApi<DatasetVersion[]>("/dataset-versions", params),
        fetchApi<FeatureSetOption[]>("/feature-sets"),
      ]);
      setItems(versions);
      setFeatureSets(fsList);
    } catch {
      setError("학습 데이터 버전 목록을 불러오지 못했습니다.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, [filterFs]);

  const handleSetPrimary = async (row: DatasetVersion) => {
    setActionLoading(true);
    try {
      await postApi(`/dataset-versions/${row.dataset_version_id}/set-primary`);
      showToast("success", "대표 학습 데이터 버전으로 지정되었습니다.");
      load();
    } catch {
      showToast("error", "대표 지정에 실패했습니다.");
    } finally {
      setActionLoading(false);
    }
  };

  const handleArchive = async (row: DatasetVersion) => {
    if (!window.confirm("이 학습 데이터 버전을 보관 처리하시겠습니까? 자동 선택에서 제외됩니다.")) return;
    setActionLoading(true);
    try {
      await postApi(`/dataset-versions/${row.dataset_version_id}/archive`, { reason: "사용자 보관 처리" });
      showToast("success", "보관 처리되었습니다.");
      load();
    } catch {
      showToast("error", "보관 처리에 실패했습니다.");
    } finally {
      setActionLoading(false);
    }
  };

  const handleSelectionPreview = async (purpose: "TRAINING" | "PREDICTION") => {
    if (!filterFs) {
      showToast("warning", "변수 구성을 선택한 뒤 선택 정책을 확인하세요.");
      return;
    }
    try {
      const res = await postApi<DatasetVersionSelectionPreview>("/dataset-versions/selection-preview", {
        feature_set_id: filterFs,
        purpose,
      });
      setSelectionPreview(res);
    } catch {
      showToast("error", "선택 정책 미리보기에 실패했습니다.");
    }
  };

  const handleCleanupPreview = async () => {
    try {
      const res = await postApi<DatasetVersionCleanupPreview>("/dataset-versions/cleanup-preview", {
        feature_set_id: filterFs || undefined,
        roles: ["TEMPORARY", "PARTIAL"],
        dry_run: true,
      });
      setCleanupPreview(res);
    } catch {
      showToast("error", "정리 대상 미리보기에 실패했습니다.");
    }
  };

  if (loading && !items.length) return <LoadingState />;
  if (error && !items.length) return <ErrorState message={error} onRetry={load} />;

  const columns = [
    {
      key: "dataset_version_id",
      header: "버전 ID",
      render: (row: DatasetVersion) => <span className="font-mono text-xs">{row.dataset_version_id}</span>,
    },
    {
      key: "feature_set_id",
      header: "변수 구성",
      render: (row: DatasetVersion) => row.feature_set_id ?? "-",
    },
    {
      key: "dataset_version_role",
      header: "역할",
      render: (row: DatasetVersion) => datasetVersionRoleLabel(row.dataset_version_role),
    },
    {
      key: "dataset_version_status",
      header: "상태",
      render: (row: DatasetVersion) => datasetVersionStatusLabel(row.dataset_version_status),
    },
    {
      key: "build_scope",
      header: "생성 범위",
      render: (row: DatasetVersion) => buildScopeLabel(row.build_scope),
    },
    {
      key: "is_primary",
      header: "대표",
      render: (row: DatasetVersion) => (row.is_primary ? "예" : "-"),
    },
    {
      key: "record_count",
      header: "행 수",
      render: (row: DatasetVersion) => (row.record_count ?? 0).toLocaleString(),
    },
    {
      key: "feature_count",
      header: "변수 수",
      render: (row: DatasetVersion) => row.feature_count ?? "-",
    },
    {
      key: "coverage_ratio",
      header: "coverage",
      render: (row: DatasetVersion) =>
        row.coverage_ratio != null ? `${(row.coverage_ratio * 100).toFixed(1)}%` : "-",
    },
    {
      key: "null_ratio",
      header: "null 비율",
      render: (row: DatasetVersion) =>
        row.null_ratio != null ? `${(row.null_ratio * 100).toFixed(1)}%` : "-",
    },
    {
      key: "created_at",
      header: "생성일",
      render: (row: DatasetVersion) => row.created_at?.slice(0, 19).replace("T", " ") ?? "-",
    },
    {
      key: "actions",
      header: "작업",
      render: (row: DatasetVersion) => (
        <div className="flex gap-1">
          <Button variant="ghost" icon={<Eye className="w-3 h-3" />} onClick={() => setDetail(row)}>
            상세
          </Button>
          {!row.is_primary && row.dataset_version_role !== "ARCHIVED" && (
            <Button
              variant="ghost"
              icon={<Star className="w-3 h-3" />}
              disabled={actionLoading}
              onClick={() => void handleSetPrimary(row)}
            >
              대표
            </Button>
          )}
          {row.dataset_version_role !== "ARCHIVED" && (
            <Button
              variant="ghost"
              icon={<Archive className="w-3 h-3" />}
              disabled={actionLoading}
              onClick={() => void handleArchive(row)}
            >
              보관
            </Button>
          )}
        </div>
      ),
    },
  ];

  return (
    <div>
      <PageHeader title={PAGE_TITLES.datasetVersions} description={PAGE_DESCRIPTIONS.datasetVersions} />
      <p className="text-xs text-slate-500 mb-4">{R9_S2_3_NOTE}</p>
      <div className="bg-amber-50 border border-amber-100 rounded-lg p-3 mb-4 text-sm text-amber-900">
        {HELP_TEXTS.datasetVersionPolicy}
      </div>

      <div className="flex flex-wrap gap-3 mb-4 items-end">
        <div>
          <label className="block text-xs text-slate-500 mb-1">변수 구성</label>
          <SelectInput
            value={filterFs}
            onChange={setFilterFs}
            options={[
              { value: "", label: "전체" },
              ...featureSets.map((fs) => ({ value: fs.feature_set_id, label: fs.feature_set_name })),
            ]}
          />
        </div>
        <Button variant="secondary" icon={<Search className="w-4 h-4" />} onClick={() => void handleSelectionPreview("TRAINING")}>
          학습 자동 선택 확인
        </Button>
        <Button variant="secondary" onClick={() => void handleSelectionPreview("PREDICTION")}>
          예측 자동 선택 확인
        </Button>
        <Button variant="secondary" onClick={() => void handleCleanupPreview()}>
          정리 대상 미리보기
        </Button>
        <Button variant="secondary" onClick={() => load()}>
          새로고침
        </Button>
      </div>

      {items.length === 0 ? (
        <div className="text-center py-16 text-slate-500 bg-slate-50 rounded-lg border border-dashed">
          <p>{EMPTY_MESSAGES.datasetVersions}</p>
        </div>
      ) : (
        <DataTable
          columns={columns as unknown as Column<Record<string, unknown>>[]}
          data={items as Array<DatasetVersion & Record<string, unknown>>}
        />
      )}

      <Modal open={!!detail} onClose={() => setDetail(null)} title="학습 데이터 버전 상세">
        {detail && (
          <dl className="grid grid-cols-2 gap-2 text-sm">
            {[
              ["버전 ID", detail.dataset_version_id],
              ["변수 구성", detail.feature_set_id],
              ["역할", datasetVersionRoleLabel(detail.dataset_version_role)],
              ["상태", datasetVersionStatusLabel(detail.dataset_version_status)],
              ["생성 범위", buildScopeLabel(detail.build_scope)],
              ["대표 여부", detail.is_primary ? "예" : "아니오"],
              ["학습 가능", detail.is_training_ready ? "예" : "아니오"],
              ["예측 사용 가능", detail.is_serving_ready ? "예" : "아니오"],
              ["행 수", detail.record_count],
              ["변수 수", detail.feature_count],
              ["coverage", detail.coverage_ratio],
              ["null 비율", detail.null_ratio],
              ["품질 점수", detail.quality_score],
              ["생성일", detail.created_at],
              ["메모", detail.selection_policy_note],
            ].map(([k, v]) => (
              <div key={k} className="contents">
                <dt className="text-slate-500">{k}</dt>
                <dd className="font-mono text-xs break-all">{String(v ?? "-")}</dd>
              </div>
            ))}
          </dl>
        )}
      </Modal>

      <Modal open={!!selectionPreview} onClose={() => setSelectionPreview(null)} title="선택 정책 미리보기">
        {selectionPreview && (
          <div className="text-sm space-y-2">
            <p>목적: {selectionPreview.purpose === "TRAINING" ? "학습" : "예측"}</p>
            <p>선택 사유: <span className="font-mono">{selectionPreview.selection_reason}</span></p>
            {selectionPreview.selected && (
              <p>선택 버전: <span className="font-mono">{selectionPreview.selected.dataset_version_id}</span></p>
            )}
            {selectionPreview.warnings.length > 0 && (
              <ul className="text-amber-700 list-disc pl-4">
                {selectionPreview.warnings.map((w) => <li key={w}>{w}</li>)}
              </ul>
            )}
            {selectionPreview.excluded_candidates.length > 0 && (
              <div>
                <p className="font-medium">제외된 후보</p>
                <ul className="text-xs font-mono max-h-40 overflow-y-auto">
                  {selectionPreview.excluded_candidates.slice(0, 20).map((e) => (
                    <li key={e.dataset_version_id}>{e.dataset_version_id}: {e.reason}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}
      </Modal>

      <Modal open={!!cleanupPreview} onClose={() => setCleanupPreview(null)} title="정리 대상 미리보기 (dry-run)">
        {cleanupPreview && (
          <div className="text-sm">
            <p>대상 {cleanupPreview.count}건 (실제 삭제하지 않음)</p>
            <ul className="text-xs font-mono max-h-48 overflow-y-auto mt-2">
              {cleanupPreview.items.map((i) => (
                <li key={i.dataset_version_id}>
                  {i.dataset_version_id} · {datasetVersionRoleLabel(i.dataset_version_role)}
                </li>
              ))}
            </ul>
          </div>
        )}
      </Modal>

      <details className="mt-6 text-xs text-slate-400">
        <summary>역할·상태 코드 참고</summary>
        <pre className="mt-2">{JSON.stringify({ DATASET_VERSION_ROLE_LABELS, DATASET_VERSION_STATUS_LABELS, BUILD_SCOPE_LABELS }, null, 2)}</pre>
      </details>
    </div>
  );
}
