import { useCallback, useEffect, useState } from "react";
import { AlertTriangle, CloudSun, ExternalLink, Eye, Play, Settings2 } from "lucide-react";
import { Link, useNavigate } from "react-router-dom";
import { fetchApi, postApi } from "@/api/client";
import {
  getForecastProviderConfig,
  listConnectorOperations,
  previewForecastInput,
  resolveForecastBaseTime,
  saveForecastProviderConfig,
} from "@/api/forecastProvider";
import { Button } from "@/components/Button";
import { Modal } from "@/components/Modal";
import { SelectInput } from "@/components/SearchPanel";
import { LoadingState } from "@/components/Pagination";
import { useToast } from "@/hooks/useToast";
import { PageHeader } from "@/layouts/MainLayout";
import { PAGE_DESCRIPTIONS, PAGE_TITLES, HELP_TEXTS } from "@/constants/displayLabels";
import type { ForecastPreviewResult, ForecastProviderConfig } from "@/types/forecastProvider";
import type { PredictionEntity } from "@/types/predictionEntities";
import {
  defaultPredictionPeriod,
  effectiveRange,
  extractApiError,
  formatDisplayDateTime,
  formatPeriodErrorMessage,
  isPeriodWithinRange,
  type FeatureDatasetRange,
} from "@/utils/predictionPeriod";

interface Site {
  site_id: string;
  site_name: string;
}

interface FeatureSet {
  feature_set_id: string;
  feature_set_name: string;
}

interface ModelSummary {
  model_name: string;
  latest_version: string | null;
  champion_version: string | null;
}

interface ModelVersionRow {
  model_version_id: string;
  model_name: string;
  version: string;
  model_stage: string;
}

interface PredictionJobResult {
  job_id: string;
  status: string;
  predicted_count?: number;
  model_version_id?: string;
  model_name?: string;
  model_version?: string;
  result_summary?: {
    model_stage?: string;
    warnings?: string[];
    forecast_input_summary?: Record<string, unknown>;
  };
}

export default function PredictionJobsPage() {
  const navigate = useNavigate();
  const { showToast } = useToast();
  const [sites, setSites] = useState<Site[]>([]);
  const [featureSets, setFeatureSets] = useState<FeatureSet[]>([]);
  const [modelVersions, setModelVersions] = useState<ModelVersionRow[]>([]);
  const [entities, setEntities] = useState<PredictionEntity[]>([]);
  const [connectorOps, setConnectorOps] = useState<{ operation_id: string; operation_name: string }[]>([]);
  const [providerOpId, setProviderOpId] = useState("");
  const [datasetRange, setDatasetRange] = useState<FeatureDatasetRange | null>(null);
  const [rangeLoading, setRangeLoading] = useState(false);
  const [loading, setLoading] = useState(true);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [previewOpen, setPreviewOpen] = useState(false);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [previewResult, setPreviewResult] = useState<ForecastPreviewResult | null>(null);
  const [running, setRunning] = useState(false);
  const [form, setForm] = useState({
    site_id: "",
    feature_set_id: "",
    model_version_id: "",
    target_start: "",
    target_end: "",
    prediction_horizon: "BATCH",
    forecast_enabled: false,
    entity_id: "",
    forecast_base_date: "",
    forecast_base_time: "",
    forecast_cache_policy: "USE_CACHE",
    weather_input_required: false,
    forecast_manual_base: false,
  });

  const loadDatasetRange = useCallback(async (featureSetId: string, autoFill: boolean) => {
    if (!featureSetId) {
      setDatasetRange(null);
      return;
    }
    setRangeLoading(true);
    try {
      const range = await fetchApi<FeatureDatasetRange>(`/feature-sets/${encodeURIComponent(featureSetId)}/dataset-range`);
      setDatasetRange(range);
      if (autoFill && range.exists) {
        const { start, end } = defaultPredictionPeriod(range);
        setForm((f) => ({ ...f, target_start: start, target_end: end }));
      }
    } catch {
      setDatasetRange(null);
    } finally {
      setRangeLoading(false);
    }
  }, []);

  useEffect(() => {
    Promise.all([
      fetchApi<Site[]>("/sites"),
      fetchApi<FeatureSet[]>("/feature-sets"),
      fetchApi<ModelSummary[]>("/models"),
      fetchApi<PredictionEntity[]>("/prediction-entities?active_yn=true"),
      listConnectorOperations().catch(() => []),
      getForecastProviderConfig().catch(() => ({}) as ForecastProviderConfig),
    ])
      .then(async ([siteRes, fsRes, modelRes, entityRes, opsRes, cfgRes]) => {
        setSites(siteRes);
        setFeatureSets(fsRes);
        setEntities(entityRes);
        setConnectorOps(opsRes);
        setProviderOpId(cfgRes.source_operation_id || "");
        const preferred = fsRes[0];
        const featureSetId = preferred?.feature_set_id || "";
        setForm((f) => ({
          ...f,
          site_id: siteRes[0]?.site_id || "",
          feature_set_id: featureSetId,
        }));

        const versionLists = await Promise.all(
          modelRes.map((m) =>
            fetchApi<ModelVersionRow[]>(`/models/${encodeURIComponent(m.model_name)}/versions`).catch(() => []),
          ),
        );
        const flat = versionLists.flat();
        setModelVersions(flat);
        const champion = flat.find((v) => v.model_stage === "CHAMPION")
          || flat.find((v) => v.model_stage === "CANDIDATE")
          || flat[0];
        if (champion) setForm((f) => ({ ...f, model_version_id: champion.model_version_id }));

        if (featureSetId) await loadDatasetRange(featureSetId, true);
      })
      .finally(() => setLoading(false));
  }, [loadDatasetRange]);

  const handleFeatureSetChange = (featureSetId: string) => {
    setForm((f) => ({ ...f, feature_set_id: featureSetId }));
    void loadDatasetRange(featureSetId, true);
  };

  const selectedEntity = entities.find((e) => e.entity_id === form.entity_id);
  const forecastReady = Boolean(
    (selectedEntity?.weather_readiness as { forecast_ready?: boolean } | undefined)?.forecast_ready,
  );

  const effective = effectiveRange(datasetRange, form.site_id);
  const periodInRange = isPeriodWithinRange(
    form.target_start,
    form.target_end,
    effective.min,
    effective.max,
  );
  const siteMissingData = Boolean(form.site_id && datasetRange?.exists && !effective.min);

  const validateBeforeRun = (): string | null => {
    if (!form.feature_set_id) {
      return "Feature Set을 선택하세요.";
    }
    if (!datasetRange?.exists) {
      return "이 Feature Set으로 생성된 Feature Dataset이 없습니다. 먼저 Feature 생성을 실행하세요.";
    }
    if (siteMissingData) {
      return "선택한 지사에 대한 Feature Dataset이 없습니다. 지사를 변경하거나 Feature 생성을 확인하세요.";
    }
    if (!form.target_start || !form.target_end) {
      return "예측 기간 시작·종료를 입력하세요.";
    }
    if (form.target_start > form.target_end) {
      return "예측 시작 시각은 종료 시각보다 이전이어야 합니다.";
    }
    if (!periodInRange && effective.min && effective.max) {
      return `선택한 Feature Set의 사용 가능한 데이터 기간은 ${formatDisplayDateTime(effective.min)} ~ ${formatDisplayDateTime(effective.max)}입니다. 예측 기간을 이 범위 안으로 선택해 주세요.`;
    }
    if (form.forecast_enabled && !form.entity_id) {
      return "단기예보 입력 사용 시 예측 대상을 선택하세요.";
    }
    if (form.forecast_enabled && form.entity_id && !forecastReady) {
      return "선택한 예측 대상의 단기예보 격자(nx/ny)가 준비되지 않았습니다.";
    }
    return null;
  };

  const handleSaveProviderConfig = async () => {
    try {
      await saveForecastProviderConfig({ source_operation_id: providerOpId || null });
      showToast("success", "단기예보 입력 생성기 설정이 저장되었습니다.");
    } catch (err: unknown) {
      const { message } = extractApiError(err);
      showToast("error", message);
    }
  };

  const handleResolveBaseTime = async () => {
    try {
      const body = form.forecast_manual_base
        ? { base_date: form.forecast_base_date, base_time: form.forecast_base_time }
        : {};
      const resolved = await resolveForecastBaseTime(body) as {
        base_date: string;
        base_time: string;
        forecast_base_at?: string;
      };
      setForm((f) => ({
        ...f,
        forecast_base_date: resolved.base_date,
        forecast_base_time: resolved.base_time,
      }));
      showToast("success", `예보 발표 시각: ${resolved.base_date} ${resolved.base_time}`);
    } catch (err: unknown) {
      const { message } = extractApiError(err);
      showToast("error", message);
    }
  };

  const handlePreviewForecast = async () => {
    if (!form.entity_id) {
      showToast("warning", "예측 대상을 선택하세요.");
      return;
    }
    setPreviewLoading(true);
    setPreviewOpen(true);
    setPreviewResult(null);
    try {
      const body: Record<string, unknown> = {
        entity_id: form.entity_id,
        cache_policy: "REFRESH",
        target_start_at: new Date(form.target_start).toISOString(),
        target_end_at: new Date(form.target_end).toISOString(),
      };
      if (form.forecast_manual_base && form.forecast_base_date && form.forecast_base_time) {
        body.base_date = form.forecast_base_date;
        body.base_time = form.forecast_base_time;
      }
      if (providerOpId) body.source_operation_id = providerOpId;
      const result = await previewForecastInput(body);
      setPreviewResult(result);
    } catch (err: unknown) {
      const { message, detail } = extractApiError(err);
      showToast("error", detail ? formatPeriodErrorMessage(detail) : message);
      setPreviewOpen(false);
    } finally {
      setPreviewLoading(false);
    }
  };

  const handleOpenConfirm = () => {
    const err = validateBeforeRun();
    if (err) {
      showToast("warning", err);
      return;
    }
    setConfirmOpen(true);
  };

  const handleRun = async () => {
    const err = validateBeforeRun();
    if (err) {
      showToast("warning", err);
      return;
    }
    setRunning(true);
    try {
      const body: Record<string, unknown> = {
        feature_set_id: form.feature_set_id,
        start_at: new Date(form.target_start).toISOString(),
        end_at: new Date(form.target_end).toISOString(),
        prediction_horizon: form.prediction_horizon,
        overwrite_yn: true,
        forecast_provider_enabled: form.forecast_enabled,
        forecast_cache_policy: form.forecast_cache_policy,
        weather_input_required: form.weather_input_required,
      };
      if (form.site_id) body.site_ids = [form.site_id];
      if (form.model_version_id) body.model_version_id = form.model_version_id;
      if (form.forecast_enabled) {
        body.entity_id = form.entity_id;
        if (form.forecast_manual_base && form.forecast_base_date && form.forecast_base_time) {
          body.forecast_base_date = form.forecast_base_date;
          body.forecast_base_time = form.forecast_base_time;
        }
        if (providerOpId) body.forecast_source_operation_id = providerOpId;
      }

      const res = await postApi<PredictionJobResult>("/prediction-jobs", body);
      const modelLabel = res.model_name
        ? `${res.model_name} v${res.model_version}`
        : res.model_version_id || "-";
      const fc = res.result_summary?.forecast_input_summary;
      const fcNote = fc?.snapshot_id ? " · 단기예보 입력 스냅샷 저장됨" : "";
      showToast("success", `배치 예측 완료: ${res.predicted_count ?? 0}건 (${modelLabel})${fcNote}`);
      setConfirmOpen(false);
      navigate("/predictions/results");
    } catch (err: unknown) {
      const { message, detail } = extractApiError(err);
      showToast("error", detail ? formatPeriodErrorMessage(detail) : message);
    } finally {
      setRunning(false);
    }
  };

  if (loading) return <LoadingState />;

  const selectedModel = modelVersions.find((m) => m.model_version_id === form.model_version_id);
  const runBlocked = Boolean(validateBeforeRun());
  const forecastEntities = entities.filter(
    (e) => (e.weather_readiness as { forecast_ready?: boolean } | undefined)?.forecast_ready,
  );

  const rangeBoxClass = !datasetRange?.exists
    ? "bg-amber-50 border-amber-200 text-amber-900"
    : siteMissingData || (form.target_start && form.target_end && !periodInRange)
      ? "bg-red-50 border-red-200 text-red-900"
      : "bg-slate-50 border-slate-200 text-slate-700";

  return (
    <div>
      <PageHeader title={PAGE_TITLES.predictionJobs} description={PAGE_DESCRIPTIONS.predictionJobs} />
      <p className="text-xs text-slate-600 bg-slate-50 border border-slate-100 rounded p-2 mb-4">
        예측 입력 학습 데이터 버전을 지정하지 않으면 예측 사용 가능·대표 버전을 자동 선택합니다.
      </p>

      <div className="bg-white rounded-lg border border-slate-200 p-6 shadow-sm max-w-xl">
        <div className="space-y-4">
          <div>
            <label className="block text-xs text-slate-500 mb-1">Feature Set</label>
            <SelectInput
              value={form.feature_set_id}
              onChange={handleFeatureSetChange}
              options={featureSets.map((f) => ({ value: f.feature_set_id, label: f.feature_set_name }))}
            />
            <div className={`mt-2 rounded-md border px-3 py-2 text-xs ${rangeBoxClass}`}>
              {rangeLoading ? (
                <p>Feature Dataset 기간을 불러오는 중...</p>
              ) : !datasetRange?.exists ? (
                <div className="space-y-2">
                  <p className="flex items-start gap-1.5">
                    <AlertTriangle className="w-3.5 h-3.5 mt-0.5 shrink-0" />
                    이 Feature Set으로 생성된 Feature Dataset이 없습니다. 먼저 Feature Set 상세 화면에서 Feature 생성을 실행하세요.
                  </p>
                  <Link
                    to={`/feature-sets/${encodeURIComponent(form.feature_set_id)}`}
                    className="inline-flex items-center gap-1 text-blue-700 hover:underline"
                  >
                    Feature 생성하러 가기
                    <ExternalLink className="w-3 h-3" />
                  </Link>
                </div>
              ) : siteMissingData ? (
                <p className="flex items-start gap-1.5">
                  <AlertTriangle className="w-3.5 h-3.5 mt-0.5 shrink-0" />
                  선택한 지사에 Feature Dataset이 없습니다. 지사를 변경하거나 Feature 생성을 확인하세요.
                </p>
              ) : (
                <>
                  <p className="font-medium text-slate-800">사용 가능한 Feature Dataset 기간</p>
                  <p>
                    {formatDisplayDateTime(effective.min)} ~ {formatDisplayDateTime(effective.max)}
                  </p>
                  <p className="text-slate-500 mt-1">
                    총 {effective.rowCount}건
                    {form.site_id ? "" : ` / 지사 ${effective.siteCount}개`}
                  </p>
                  {form.target_start && form.target_end && !periodInRange && (
                    <p className="mt-2 flex items-start gap-1.5 text-red-800">
                      <AlertTriangle className="w-3.5 h-3.5 mt-0.5 shrink-0" />
                      예측 기간이 위 범위를 벗어났습니다. 범위 안으로 조정해 주세요.
                    </p>
                  )}
                </>
              )}
            </div>
          </div>
          <div>
            <label className="block text-xs text-slate-500 mb-1">모델 버전</label>
            <SelectInput value={form.model_version_id} onChange={(v) => setForm({ ...form, model_version_id: v })}
              options={[
                { value: "", label: "자동 (Champion → CANDIDATE)" },
                ...modelVersions.map((m) => ({
                  value: m.model_version_id,
                  label: `${m.model_name} v${m.version} (${m.model_stage})`,
                })),
              ]} />
            {selectedModel && (
              <p className="text-xs text-slate-400 mt-1">선택: {selectedModel.model_name} v{selectedModel.version}</p>
            )}
          </div>
          <div>
            <label className="block text-xs text-slate-500 mb-1">지사 (선택)</label>
            <SelectInput value={form.site_id} onChange={(v) => setForm({ ...form, site_id: v })}
              options={[{ value: "", label: "전체" }, ...sites.map((s) => ({ value: s.site_id, label: s.site_name }))]} />
          </div>
          <div>
            <label className="block text-xs text-slate-500 mb-1">예측 기간 시작</label>
            <input type="datetime-local" value={form.target_start}
              onChange={(e) => setForm({ ...form, target_start: e.target.value })}
              className="w-full border border-slate-200 rounded-md px-2 py-1.5 text-sm bg-slate-50" />
          </div>
          <div>
            <label className="block text-xs text-slate-500 mb-1">예측 기간 종료</label>
            <input type="datetime-local" value={form.target_end}
              onChange={(e) => setForm({ ...form, target_end: e.target.value })}
              className="w-full border border-slate-200 rounded-md px-2 py-1.5 text-sm bg-slate-50" />
          </div>
          <div>
            <label className="block text-xs text-slate-500 mb-1">예측 구간</label>
            <SelectInput value={form.prediction_horizon} onChange={(v) => setForm({ ...form, prediction_horizon: v })}
              options={[
                { value: "BATCH", label: "배치 (Feature 기간)" },
                { value: "D_PLUS_1", label: "D+1 (익일)" },
                { value: "D_PLUS_3", label: "D+3" },
                { value: "D_PLUS_7", label: "D+7" },
              ]} />
          </div>

          <div className="border-t border-slate-100 pt-4 space-y-3">
            <div className="flex items-center gap-2 text-sm font-medium text-slate-800">
              <CloudSun className="w-4 h-4 text-sky-600" />
              단기예보 입력
            </div>
            <p className="text-xs text-slate-500">{HELP_TEXTS.forecastOnDemand}</p>
            <p className="text-xs text-slate-500">예보 발표 시각·예보 대상 시각 기준으로 표준 단기예보 행을 만들며, 호출 결과는 기상 입력 스냅샷으로 저장됩니다.</p>
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={form.forecast_enabled}
                onChange={(e) => setForm({ ...form, forecast_enabled: e.target.checked })}
              />
              예측 시점 단기예보 호출
            </label>

            {form.forecast_enabled && (
              <>
                <div>
                  <label className="block text-xs text-slate-500 mb-1">예측 대상</label>
                  <SelectInput
                    value={form.entity_id}
                    onChange={(v) => setForm({ ...form, entity_id: v })}
                    options={[
                      { value: "", label: "선택" },
                      ...entities.map((e) => ({
                        value: e.entity_id,
                        label: `${e.entity_name} (${(e.weather_readiness as { forecast_ready?: boolean })?.forecast_ready ? "단기예보 준비" : "미준비"})`,
                      })),
                    ]}
                  />
                  {form.entity_id && !forecastReady && (
                    <p className="text-xs text-amber-700 mt-1 flex items-start gap-1">
                      <AlertTriangle className="w-3.5 h-3.5 shrink-0" />
                      nx/ny가 없으면 단기예보 입력을 사용할 수 없습니다.
                      <Link to="/prediction-entities" className="text-blue-700 underline ml-1">예측 대상 화면</Link>
                    </p>
                  )}
                  {forecastEntities.length === 0 && (
                    <p className="text-xs text-slate-500 mt-1">forecast_ready 예측 대상이 없습니다. 예측 대상 화면에서 격자 매핑을 완료하세요.</p>
                  )}
                </div>

                <div className="rounded border border-slate-100 p-3 space-y-2 bg-slate-50">
                  <div className="flex items-center gap-2 text-xs font-medium text-slate-700">
                    <Settings2 className="w-3.5 h-3.5" />
                    예측 시점 단기예보 입력 생성기 설정
                  </div>
                  <SelectInput
                    value={providerOpId}
                    onChange={setProviderOpId}
                    options={[
                      { value: "", label: "REST API 작업 선택" },
                      ...connectorOps.map((op) => ({ value: op.operation_id, label: op.operation_name })),
                    ]}
                  />
                  <Button variant="secondary" onClick={handleSaveProviderConfig}>설정 저장</Button>
                </div>

                <label className="flex items-center gap-2 text-xs">
                  <input
                    type="checkbox"
                    checked={form.forecast_manual_base}
                    onChange={(e) => setForm({ ...form, forecast_manual_base: e.target.checked })}
                  />
                  예보 발표 시각 수동 입력
                </label>
                {form.forecast_manual_base ? (
                  <div className="grid grid-cols-2 gap-2">
                    <input
                      placeholder="base_date (YYYYMMDD)"
                      value={form.forecast_base_date}
                      onChange={(e) => setForm({ ...form, forecast_base_date: e.target.value })}
                      className="border border-slate-200 rounded px-2 py-1 text-sm"
                    />
                    <input
                      placeholder="base_time (HHMM)"
                      value={form.forecast_base_time}
                      onChange={(e) => setForm({ ...form, forecast_base_time: e.target.value })}
                      className="border border-slate-200 rounded px-2 py-1 text-sm"
                    />
                  </div>
                ) : (
                  <p className="text-xs text-slate-500">예보 발표 시각은 자동 선택 정책(최신 발표 + 지연 보정)을 사용합니다.</p>
                )}

                <div>
                  <label className="block text-xs text-slate-500 mb-1">캐시 정책</label>
                  <SelectInput
                    value={form.forecast_cache_policy}
                    onChange={(v) => setForm({ ...form, forecast_cache_policy: v })}
                    options={[
                      { value: "USE_CACHE", label: "캐시 사용" },
                      { value: "REFRESH", label: "새로 호출" },
                      { value: "DISABLED", label: "캐시 없음" },
                    ]}
                  />
                </div>

                <label className="flex items-center gap-2 text-xs">
                  <input
                    type="checkbox"
                    checked={form.weather_input_required}
                    onChange={(e) => setForm({ ...form, weather_input_required: e.target.checked })}
                  />
                  단기예보 입력 필수 (실패 시 예측 중단)
                </label>

                <Button variant="secondary" icon={<Eye className="w-4 h-4" />} onClick={handlePreviewForecast} disabled={!form.entity_id}>
                  단기예보 입력 미리보기
                </Button>
                <Button variant="secondary" onClick={handleResolveBaseTime}>예보 발표 시각 자동 선택</Button>
              </>
            )}
            {!form.forecast_enabled && (
              <Button variant="secondary" icon={<Eye className="w-4 h-4" />} disabled>
                단기예보 입력 미리보기
              </Button>
            )}
          </div>

          <div className="pt-2">
            <Button icon={<Play className="w-4 h-4" />} onClick={handleOpenConfirm} disabled={runBlocked}>
              예측 실행
            </Button>
          </div>
        </div>
      </div>

      <Modal open={confirmOpen} title="배치 예측 실행 확인" onClose={() => setConfirmOpen(false)}
        footer={<>
          <Button variant="secondary" onClick={() => setConfirmOpen(false)}>취소</Button>
          <Button icon={<Play className="w-4 h-4" />} onClick={handleRun} disabled={running}>{running ? "실행 중..." : "실행"}</Button>
        </>}>
        <p className="text-sm text-slate-600">선택한 조건으로 배치 예측을 실행하시겠습니까?</p>
        <ul className="text-xs text-slate-500 mt-3 space-y-1">
          <li>Feature Set: {form.feature_set_id}</li>
          <li>모델: {selectedModel ? `${selectedModel.model_name} v${selectedModel.version}` : "자동 선택"}</li>
          <li>지사: {form.site_id ? sites.find((s) => s.site_id === form.site_id)?.site_name : "전체"}</li>
          <li>기간: {form.target_start || "-"} ~ {form.target_end || "-"}</li>
          {form.forecast_enabled && (
            <li>단기예보 입력: {selectedEntity?.entity_name || form.entity_id} / 캐시 {form.forecast_cache_policy}</li>
          )}
          {datasetRange?.exists && effective.min && (
            <li>사용 가능 범위: {formatDisplayDateTime(effective.min)} ~ {formatDisplayDateTime(effective.max)}</li>
          )}
        </ul>
        <p className="text-xs text-slate-400 mt-2">완료 후 예측 결과 화면으로 이동합니다. 단기예보 입력은 기상 입력 스냅샷으로 저장됩니다.</p>
      </Modal>

      <Modal open={previewOpen} title="단기예보 입력 미리보기" onClose={() => setPreviewOpen(false)}
        footer={<Button variant="secondary" onClick={() => setPreviewOpen(false)}>닫기</Button>}>
        {previewLoading ? (
          <p className="text-sm text-slate-500">미리보기 생성 중...</p>
        ) : previewResult ? (
          <div className="text-xs space-y-2">
            <p>격자 nx={previewResult.nx} ny={previewResult.ny}</p>
            <p>예보 발표 시각: {previewResult.forecast_base_at || "-"}</p>
            <p>행 수: {previewResult.row_count} (기간 매칭 {previewResult.matched_row_count})</p>
            <p>기상 입력 스냅샷: {previewResult.snapshot_id || "-"} {previewResult.cache_hit ? "(캐시 사용)" : ""}</p>
            {(previewResult.warnings || []).map((w) => (
              <p key={w} className="text-amber-700">{w}</p>
            ))}
            <pre className="bg-slate-50 p-2 rounded overflow-auto max-h-40 text-[11px]">
              {JSON.stringify(previewResult.sample_rows || [], null, 2)}
            </pre>
          </div>
        ) : null}
      </Modal>
    </div>
  );
}
