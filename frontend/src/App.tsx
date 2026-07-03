import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { ToastProvider } from "@/hooks/useToast";
import { MainLayout } from "@/layouts/MainLayout";
import DashboardPage from "@/pages/DashboardPage";
import DataSourcesPage from "@/pages/DataSourcesPage";
import DataMappingsPage from "@/pages/DataMappingsPage";
import DataQualityPage from "@/pages/DataQualityPage";
import StandardDatasetsPage from "@/pages/StandardDatasetsPage";
import FeaturesPage from "@/pages/FeaturesPage";
import FeatureSetsPage from "@/pages/FeatureSetsPage";
import FeatureSetDetailPage from "@/pages/FeatureSetDetailPage";
import FeatureRecipesPage from "@/pages/FeatureRecipesPage";
import FeatureRecipeBuilderPage from "@/pages/FeatureRecipeBuilderPage";
import DatasetVersionsPage from "@/pages/DatasetVersionsPage";
import TrainingConfigsPage from "@/pages/TrainingConfigsPage";
import TrainingJobsPage from "@/pages/TrainingJobsPage";
import ModelPerformancePage from "@/pages/ModelPerformancePage";
import ModelRegistryPage from "@/pages/ModelRegistryPage";
import PredictionJobsPage from "@/pages/PredictionJobsPage";
import PredictionResultsPage from "@/pages/PredictionResultsPage";
import PredictionErrorsPage from "@/pages/PredictionErrorsPage";
import PipelineBuilderPage from "@/pages/PipelineBuilderPage";
import PipelineRunsPage from "@/pages/PipelineRunsPage";
import ModelMonitoringPage from "@/pages/ModelMonitoringPage";
import DriftReportsPage from "@/pages/DriftReportsPage";
import RetrainingCandidatesPage from "@/pages/RetrainingCandidatesPage";
import SystemConfigPage from "@/pages/SystemConfigPage";

export default function App() {
  return (
    <ToastProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<MainLayout />}>
            <Route index element={<Navigate to="/dashboard" replace />} />
            <Route path="dashboard" element={<DashboardPage />} />
            <Route path="data/sources" element={<DataSourcesPage />} />
            <Route path="standard-datasets" element={<StandardDatasetsPage />} />
            <Route path="data/mappings" element={<DataMappingsPage />} />
            <Route path="data/quality" element={<DataQualityPage />} />
            <Route path="features" element={<FeaturesPage />} />
            <Route path="feature-recipes" element={<FeatureRecipesPage />} />
            <Route path="feature-recipes/new" element={<FeatureRecipeBuilderPage />} />
            <Route path="feature-recipes/:recipeId" element={<FeatureRecipeBuilderPage />} />
            <Route path="feature-sets" element={<FeatureSetsPage />} />
            <Route path="feature-sets/:id" element={<FeatureSetDetailPage />} />
            <Route path="dataset-versions" element={<DatasetVersionsPage />} />
            <Route path="models/training-configs" element={<TrainingConfigsPage />} />
            <Route path="models/training-jobs" element={<TrainingJobsPage />} />
            <Route path="models/performance" element={<ModelPerformancePage />} />
            <Route path="models/registry" element={<ModelRegistryPage />} />
            <Route path="predictions/jobs" element={<PredictionJobsPage />} />
            <Route path="predictions/results" element={<PredictionResultsPage />} />
            <Route path="predictions/errors" element={<PredictionErrorsPage />} />
            <Route path="ops/pipeline-runs" element={<PipelineRunsPage />} />
            <Route path="pipeline-builder" element={<PipelineBuilderPage />} />
            <Route path="pipeline-builder/:pipelineId" element={<PipelineBuilderPage />} />
            <Route path="ops/model-monitoring" element={<ModelMonitoringPage />} />
            <Route path="ops/drift-reports" element={<DriftReportsPage />} />
            <Route path="ops/retraining-candidates" element={<RetrainingCandidatesPage />} />
            <Route path="system/configs" element={<SystemConfigPage />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </ToastProvider>
  );
}
