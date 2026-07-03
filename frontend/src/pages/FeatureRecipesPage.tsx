import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { Plus } from "lucide-react";
import { getRecipeBuildHistory, listFeatureRecipes } from "@/api/featureRecipes";
import type { RecipeBuildHistoryItem } from "@/types/featureRecipes";
import { Button } from "@/components/Button";
import { DataTable } from "@/components/DataTable";
import { ErrorState, LoadingState } from "@/components/Pagination";
import { PageHeader } from "@/layouts/MainLayout";
import { EMPTY_MESSAGES, PAGE_DESCRIPTIONS, PAGE_TITLES } from "@/constants/displayLabels";
import type { FeatureRecipe } from "@/types/featureRecipes";
import { R6_BUILD_INFO } from "@/types/featureRecipes";
import {
  LEGACY_JOB_DIAGNOSTICS_NOTE,
  formatNullRatio,
  getRecipeBuildStatusBadgeClass,
  getRecipeBuildStatusLabel,
  mapTemplateFeatureStatusToBadge,
  recipeBuildSupportClass,
  recipeBuildSupportLabel,
  recipeStatusClass,
  recipeStatusLabel,
  summarizeBuildHistoryItem,
} from "@/utils/featureRecipeFormat";

const MAX_BUILD_STATUS_LOOKUP = 20;

interface RecipeBuildSnapshot {
  badge: ReturnType<typeof mapTemplateFeatureStatusToBadge>;
  nullRatio?: number;
  issueSummary: string;
  latestItem?: RecipeBuildHistoryItem;
}

export default function FeatureRecipesPage() {
  const [items, setItems] = useState<FeatureRecipe[]>([]);
  const [buildSnapshots, setBuildSnapshots] = useState<Record<string, RecipeBuildSnapshot>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const loadBuildSnapshots = useCallback(async (recipes: FeatureRecipe[]) => {
    const published = recipes
      .filter((r) => r.status === "PUBLISHED")
      .slice(0, MAX_BUILD_STATUS_LOOKUP);
    const entries = await Promise.allSettled(
      published.map(async (recipe) => {
        const hist = await getRecipeBuildHistory(recipe.recipe_id, 1);
        const item = hist.items[0];
        const badge = mapTemplateFeatureStatusToBadge(hist.latest_build_status);
        return [
          recipe.recipe_id,
          {
            badge,
            nullRatio: item?.null_ratio,
            issueSummary: summarizeBuildHistoryItem(item),
            latestItem: item,
          } satisfies RecipeBuildSnapshot,
        ] as const;
      }),
    );
    const map: Record<string, RecipeBuildSnapshot> = {};
    for (const entry of entries) {
      if (entry.status === "fulfilled") {
        const [id, snap] = entry.value;
        map[id] = snap;
      }
    }
    setBuildSnapshots(map);
  }, []);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const res = await listFeatureRecipes({ limit: 100 });
      setItems(res.items);
      void loadBuildSnapshots(res.items);
    } catch {
      setError("변수 생성 규칙 목록을 불러오지 못했습니다.");
    } finally {
      setLoading(false);
    }
  }, [loadBuildSnapshots]);

  useEffect(() => {
    void load();
  }, [load]);

  const tableData = useMemo(
    () => items.map((recipe) => ({ ...recipe, _snapshot: buildSnapshots[recipe.recipe_id] })),
    [items, buildSnapshots],
  );

  if (loading) return <LoadingState />;
  if (error) return <ErrorState message={error} onRetry={() => void load()} />;

  return (
    <div>
      <PageHeader
        title={PAGE_TITLES.featureRecipes}
        description={PAGE_DESCRIPTIONS.featureRecipes}
        actions={(
          <Link to="/feature-recipes/new">
            <Button icon={<Plus className="w-4 h-4" />}>규칙 만들기</Button>
          </Link>
        )}
      />

      <div className="mb-4 text-xs text-slate-600 bg-blue-50 border border-blue-200 rounded-lg p-3 space-y-1">
        <p className="font-medium text-slate-800">변수 생성 규칙 (R5–R6)</p>
        <p>{R6_BUILD_INFO}</p>
        <p>목록에서 사용 가능 규칙의 <strong>최근 변수 생성</strong> 상태를 확인할 수 있습니다.</p>
        <p>상세 화면에서 <strong>미리보기/생성 비교</strong>를 실행할 수 있습니다.</p>
        <p className="text-slate-500">{LEGACY_JOB_DIAGNOSTICS_NOTE}</p>
      </div>

      <DataTable
        emptyMessage={EMPTY_MESSAGES.featureRecipes}
        columns={[
          { key: "recipe_id", header: "ID", width: "130px" },
          { key: "display_name", header: "표시명" },
          { key: "recipe_type", header: "템플릿", width: "110px" },
          {
            key: "status",
            header: "상태",
            width: "80px",
            render: (r) => (
              <span className={`text-[10px] px-1 py-0.5 rounded border ${recipeStatusClass(r.status as FeatureRecipe["status"])}`}>
                {recipeStatusLabel(r.status as FeatureRecipe["status"])}
              </span>
            ),
          },
          { key: "feature_name", header: "변수명", render: (r) => String(r.feature_name ?? "-") },
          {
            key: "build_supported",
            header: "생성 지원",
            width: "90px",
            render: (r) => {
              const recipe = r as unknown as FeatureRecipe;
              return (
                <span className={`text-[10px] px-1 py-0.5 rounded border ${recipeBuildSupportClass(recipe)}`}>
                  {recipeBuildSupportLabel(recipe)}
                </span>
              );
            },
          },
          {
            key: "recent_build",
            header: "최근 생성",
            width: "120px",
            render: (r) => {
              const recipe = r as unknown as FeatureRecipe & { _snapshot?: RecipeBuildSnapshot };
              if (recipe.status === "ARCHIVED") {
                return <span className="text-[10px] text-slate-400">생성 대상 아님</span>;
              }
              if (recipe.status !== "PUBLISHED") {
                return <span className="text-[10px] text-slate-500">발행 후 생성 가능</span>;
              }
              const snap = recipe._snapshot;
              if (!snap) return <span className="text-[10px] text-slate-400">조회 중...</span>;
              return (
                <span className={`text-[10px] px-1 py-0.5 rounded border ${getRecipeBuildStatusBadgeClass(snap.badge)}`}>
                  {getRecipeBuildStatusLabel(snap.badge)}
                </span>
              );
            },
          },
          {
            key: "null_ratio",
            header: "최근 null%",
            width: "80px",
            render: (r) => {
              const snap = (r as { _snapshot?: RecipeBuildSnapshot })._snapshot;
              return snap?.nullRatio != null ? formatNullRatio(snap.nullRatio) : "-";
            },
          },
          {
            key: "issues",
            header: "경고/실패",
            render: (r) => {
              const snap = (r as { _snapshot?: RecipeBuildSnapshot })._snapshot;
              return <span className="text-[10px] text-slate-600">{snap?.issueSummary || "-"}</span>;
            },
          },
          {
            key: "actions",
            header: "",
            width: "140px",
            render: (r) => {
              const recipe = r as unknown as FeatureRecipe & { _snapshot?: RecipeBuildSnapshot };
              const dsv = recipe._snapshot?.latestItem?.dataset_version_id;
              return (
                <div className="flex flex-col gap-1 text-xs">
                  <Link to={`/feature-recipes/${recipe.recipe_id}`} className="text-blue-600 hover:underline">
                    상세
                  </Link>
                  {recipe.status === "PUBLISHED" && dsv && (
                    <Link
                      to={`/feature-recipes/${recipe.recipe_id}?compare_dsv=${encodeURIComponent(dsv)}`}
                      className="text-violet-700 hover:underline"
                    >
                      미리보기/생성 비교
                    </Link>
                  )}
                </div>
              );
            },
          },
        ]}
        data={tableData as unknown as Record<string, unknown>[]}
      />
    </div>
  );
}
