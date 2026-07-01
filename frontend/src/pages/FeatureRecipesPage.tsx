import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Plus } from "lucide-react";
import { listFeatureRecipes } from "@/api/featureRecipes";
import { Button } from "@/components/Button";
import { DataTable } from "@/components/DataTable";
import { ErrorState, LoadingState } from "@/components/Pagination";
import { PageHeader } from "@/layouts/MainLayout";
import type { FeatureRecipe } from "@/types/featureRecipes";
import { R6_BUILD_INFO } from "@/types/featureRecipes";
import { recipeBuildSupportClass, recipeBuildSupportLabel, recipeStatusClass, recipeStatusLabel } from "@/utils/featureRecipeFormat";

export default function FeatureRecipesPage() {
  const [items, setItems] = useState<FeatureRecipe[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const res = await listFeatureRecipes({ limit: 100 });
      setItems(res.items);
    } catch {
      setError("Recipe 목록을 불러오지 못했습니다.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  if (loading) return <LoadingState />;
  if (error) return <ErrorState message={error} onRetry={() => void load()} />;

  return (
    <div>
      <PageHeader
        title="Feature Recipe"
        description="Template 기반 Feature Recipe를 저장·검증·발행합니다."
        actions={(
          <Link to="/feature-recipes/new">
            <Button icon={<Plus className="w-4 h-4" />}>Recipe 만들기</Button>
          </Link>
        )}
      />

      <div className="mb-4 text-xs text-slate-600 bg-blue-50 border border-blue-200 rounded-lg p-3 space-y-1">
        <p className="font-medium text-slate-800">Feature Recipe Builder (R5–R6)</p>
        <p>{R6_BUILD_INFO}</p>
        <p>DIFF/RATIO/BINNING 등은 Build 미지원이며 Preview·저장만 가능합니다.</p>
      </div>

      <DataTable
        columns={[
          { key: "recipe_id", header: "ID", width: "140px" },
          { key: "display_name", header: "표시명" },
          { key: "recipe_type", header: "템플릿", width: "120px" },
          {
            key: "status",
            header: "상태",
            width: "90px",
            render: (r) => (
              <span className={`text-[10px] px-1 py-0.5 rounded border ${recipeStatusClass(r.status as FeatureRecipe["status"])}`}>
                {recipeStatusLabel(r.status as FeatureRecipe["status"])}
              </span>
            ),
          },
          { key: "feature_name", header: "Feature명", render: (r) => String(r.feature_name ?? "-") },
          {
            key: "build_supported",
            header: "Build",
            width: "100px",
            render: (r) => {
              const recipe = r as unknown as FeatureRecipe;
              return (
              <span className={`text-[10px] px-1 py-0.5 rounded border ${recipeBuildSupportClass(recipe)}`}>
                {recipeBuildSupportLabel(recipe)}
              </span>
              );
            },
          },
          { key: "mapping_id", header: "매핑", width: "110px", render: (r) => String(r.mapping_id ?? "-") },
          {
            key: "actions",
            header: "",
            render: (r) => (
              <Link to={`/feature-recipes/${r.recipe_id}`} className="text-xs text-blue-600 hover:underline">
                열기
              </Link>
            ),
          },
        ]}
        data={items as unknown as Record<string, unknown>[]}
      />
    </div>
  );
}
