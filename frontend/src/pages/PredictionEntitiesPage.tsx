import { useCallback, useEffect, useState } from "react";
import { Plus, MapPin } from "lucide-react";
import {
  archivePredictionEntity,
  convertLatLonToGrid,
  createEntityLocation,
  createPredictionEntity,
  createWeatherMapping,
  getPredictionEntity,
  getWeatherMappingPreview,
  listForecastGrids,
  listObservationStations,
  listPredictionEntities,
  upsertForecastGrid,
  upsertObservationStation,
} from "@/api/predictionEntities";
import { extractApiErrorMessage } from "@/api/client";
import { Button } from "@/components/Button";
import { DataTable } from "@/components/DataTable";
import { Modal } from "@/components/Modal";
import { SelectInput, TextInput } from "@/components/SearchPanel";
import { LoadingState, ErrorState } from "@/components/Pagination";
import { useToast } from "@/hooks/useToast";
import { PageHeader } from "@/layouts/MainLayout";
import {
  EMPTY_MESSAGES,
  HELP_TEXTS,
  PAGE_DESCRIPTIONS,
  PAGE_TITLES,
} from "@/constants/displayLabels";
import type { PredictionEntity, PredictionEntityDetail } from "@/types/predictionEntities";
import { ENTITY_TYPE_OPTIONS } from "@/types/predictionEntities";

type Tab = "entities" | "grids" | "stations";

const EMPTY_ENTITY = {
  entity_code: "",
  entity_name: "",
  entity_type: "SITE",
  business_domain: "",
  description: "",
};

export default function PredictionEntitiesPage() {
  const { showToast } = useToast();
  const [tab, setTab] = useState<Tab>("entities");
  const [items, setItems] = useState<PredictionEntity[]>([]);
  const [grids, setGrids] = useState<Record<string, unknown>[]>([]);
  const [stations, setStations] = useState<Record<string, unknown>[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [createOpen, setCreateOpen] = useState(false);
  const [form, setForm] = useState(EMPTY_ENTITY);
  const [detail, setDetail] = useState<PredictionEntityDetail | null>(null);
  const [detailOpen, setDetailOpen] = useState(false);
  const [locationForm, setLocationForm] = useState({ address: "", latitude: "", longitude: "" });
  const [gridForm, setGridForm] = useState({ nx: "", ny: "", grid_name: "" });
  const [stationForm, setStationForm] = useState({ station_code: "", station_name: "", station_type: "ASOS" });
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [ents, g, s] = await Promise.all([
        listPredictionEntities(),
        listForecastGrids(),
        listObservationStations(),
      ]);
      setItems(ents);
      setGrids(g as unknown as Record<string, unknown>[]);
      setStations(s as unknown as Record<string, unknown>[]);
    } catch {
      setError("예측 대상 목록을 불러오지 못했습니다.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void load(); }, [load]);

  const openDetail = async (entityId: string) => {
    try {
      const d = await getPredictionEntity(entityId);
      setDetail(d);
      const loc = d.locations?.find((l) => l.active_yn);
      setLocationForm({
        address: loc?.address || "",
        latitude: loc?.latitude != null ? String(loc.latitude) : "",
        longitude: loc?.longitude != null ? String(loc.longitude) : "",
      });
      setDetailOpen(true);
    } catch {
      showToast("error", "상세 정보를 불러오지 못했습니다.");
    }
  };

  const handleCreate = async () => {
    if (!form.entity_code.trim() || !form.entity_name.trim()) {
      showToast("warning", "예측 대상 코드와 이름을 입력하세요.");
      return;
    }
    setBusy(true);
    try {
      await createPredictionEntity({ ...form, business_domain: form.business_domain || undefined });
      showToast("success", "예측 대상이 등록되었습니다.");
      setCreateOpen(false);
      setForm(EMPTY_ENTITY);
      void load();
    } catch (e) {
      showToast("error", extractApiErrorMessage(e, "등록에 실패했습니다."));
    } finally {
      setBusy(false);
    }
  };

  const handleSaveLocation = async () => {
    if (!detail) return;
    setBusy(true);
    try {
      await createEntityLocation(detail.entity_id, {
        address: locationForm.address || undefined,
        latitude: locationForm.latitude ? Number(locationForm.latitude) : undefined,
        longitude: locationForm.longitude ? Number(locationForm.longitude) : undefined,
        active_yn: true,
      });
      showToast("success", "위치 정보가 저장되었습니다.");
      await openDetail(detail.entity_id);
      void load();
    } catch (e) {
      showToast("error", extractApiErrorMessage(e, "위치 저장에 실패했습니다."));
    } finally {
      setBusy(false);
    }
  };

  const handleCalcGrid = async () => {
    const lat = Number(locationForm.latitude);
    const lon = Number(locationForm.longitude);
    if (!lat || !lon) {
      showToast("warning", "위도와 경도를 입력하세요.");
      return;
    }
    setBusy(true);
    try {
      const res = await convertLatLonToGrid(lat, lon);
      setGridForm({ nx: String(res.nx), ny: String(res.ny), grid_name: `격자 ${res.nx},${res.ny}` });
      showToast("success", `nx=${res.nx}, ny=${res.ny} (검토 후 저장하세요)`);
    } catch (e) {
      showToast("error", extractApiErrorMessage(e, "격자 계산에 실패했습니다."));
    } finally {
      setBusy(false);
    }
  };

  const handleSaveGridMapping = async () => {
    if (!detail || !gridForm.nx || !gridForm.ny) return;
    setBusy(true);
    try {
      const grid = await upsertForecastGrid({
        nx: Number(gridForm.nx),
        ny: Number(gridForm.ny),
        grid_name: gridForm.grid_name || undefined,
        latitude: locationForm.latitude ? Number(locationForm.latitude) : undefined,
        longitude: locationForm.longitude ? Number(locationForm.longitude) : undefined,
        mapping_method: "LATLON_TO_GRID",
      });
      await createWeatherMapping(detail.entity_id, {
        forecast_grid_id: grid.forecast_grid_id,
        mapping_type: "FORECAST_GRID",
        mapping_method: gridForm.nx ? "LATLON_TO_GRID" : "MANUAL",
      });
      showToast("success", "단기예보 격자 매핑이 저장되었습니다.");
      await openDetail(detail.entity_id);
      void load();
    } catch (e) {
      showToast("error", extractApiErrorMessage(e, "격자 매핑 저장에 실패했습니다."));
    } finally {
      setBusy(false);
    }
  };

  const handleSaveStation = async () => {
    if (!detail || !stationForm.station_code || !stationForm.station_name) return;
    setBusy(true);
    try {
      const st = await upsertObservationStation(stationForm);
      await createWeatherMapping(detail.entity_id, {
        station_id: st.station_id,
        mapping_type: "OBSERVATION_STATION",
        mapping_method: "MANUAL",
      });
      showToast("success", "관측소 매핑이 저장되었습니다.");
      setStationForm({ station_code: "", station_name: "", station_type: "ASOS" });
      await openDetail(detail.entity_id);
      void load();
    } catch (e) {
      showToast("error", extractApiErrorMessage(e, "관측소 저장에 실패했습니다."));
    } finally {
      setBusy(false);
    }
  };

  const handlePreview = async () => {
    if (!detail) return;
    try {
      const p = await getWeatherMappingPreview(detail.entity_id);
      showToast("success", `준비 상태 — 단기예보: ${p.forecast_ready ? "완료" : "미완료"}, 관측: ${p.observation_ready ? "완료" : "미완료"}`);
      setDetail({ ...detail, weather_readiness: p });
    } catch (e) {
      showToast("error", extractApiErrorMessage(e, "준비 상태 확인에 실패했습니다."));
    }
  };

  const readinessBadge = (ready: boolean) => (
    <span className={ready ? "text-green-700" : "text-amber-700"}>{ready ? "준비 완료" : "필요"}</span>
  );

  if (loading) return <LoadingState />;
  if (error) return <ErrorState message={error} onRetry={() => void load()} />;

  return (
    <div>
      <PageHeader title={PAGE_TITLES.predictionEntities} description={PAGE_DESCRIPTIONS.predictionEntities} />
      <div className="bg-blue-50 border border-blue-100 rounded p-3 mb-4 text-xs text-blue-900 space-y-1">
        <p>{HELP_TEXTS.forecastGrid}</p>
        <p>{HELP_TEXTS.observationStation}</p>
        <p>{HELP_TEXTS.weatherMappingSplit}</p>
        <p>{HELP_TEXTS.restApiConnectorLink}</p>
      </div>

      <div className="flex gap-2 mb-4">
        {[
          ["entities", "예측 대상"],
          ["grids", "단기예보 격자"],
          ["stations", "ASOS 관측소"],
        ].map(([id, label]) => (
          <button
            key={id}
            type="button"
            onClick={() => setTab(id as Tab)}
            className={`px-3 py-1.5 text-sm rounded border ${tab === id ? "bg-blue-50 border-blue-200 text-blue-700" : "bg-white text-slate-600"}`}
          >
            {label}
          </button>
        ))}
        {tab === "entities" && (
          <Button icon={<Plus className="w-4 h-4" />} onClick={() => setCreateOpen(true)}>예측 대상 등록</Button>
        )}
      </div>

      {tab === "entities" && (
        items.length === 0 ? (
          <div className="text-center py-12 text-slate-500 bg-slate-50 rounded border border-dashed text-sm">
            {EMPTY_MESSAGES.predictionEntities}
          </div>
        ) : (
          <DataTable
            columns={[
              { key: "entity_code", header: "예측 대상 코드" },
              { key: "entity_name", header: "예측 대상명" },
              { key: "entity_type", header: "유형" },
              { key: "business_domain", header: "업무 영역", render: (r) => String(r.business_domain || "-") },
              {
                key: "location_ready",
                header: "위치 정보",
                render: (r) => readinessBadge(!!(r.weather_readiness as { location_ready?: boolean })?.location_ready),
              },
              {
                key: "forecast_ready",
                header: "단기예보 준비",
                render: (r) => readinessBadge(!!(r.weather_readiness as { forecast_ready?: boolean })?.forecast_ready),
              },
              {
                key: "observation_ready",
                header: "관측 기상 준비",
                render: (r) => readinessBadge(!!(r.weather_readiness as { observation_ready?: boolean })?.observation_ready),
              },
              {
                key: "actions",
                header: "작업",
                render: (r) => (
                  <Button variant="ghost" icon={<MapPin className="w-3 h-3" />} onClick={() => void openDetail(String(r.entity_id))}>
                    상세
                  </Button>
                ),
              },
            ]}
            data={items as unknown as Record<string, unknown>[]}
          />
        )
      )}

      {tab === "grids" && (
        <DataTable
          columns={[
            { key: "nx", header: "nx" },
            { key: "ny", header: "ny" },
            { key: "grid_name", header: "격자명" },
            { key: "grid_system", header: "격자 체계" },
          ]}
          data={grids}
          emptyMessage="등록된 단기예보 격자가 없습니다."
        />
      )}

      {tab === "stations" && (
        <DataTable
          columns={[
            { key: "station_code", header: "관측소 코드" },
            { key: "station_name", header: "관측소명" },
            { key: "station_type", header: "유형" },
          ]}
          data={stations}
          emptyMessage="등록된 ASOS 관측소가 없습니다."
        />
      )}

      <Modal open={createOpen} onClose={() => setCreateOpen(false)} title="예측 대상 등록">
        <div className="space-y-3 text-sm">
          <label className="block text-xs text-slate-500">예측 대상 코드</label>
          <TextInput value={form.entity_code} onChange={(v) => setForm({ ...form, entity_code: v })} />
          <label className="block text-xs text-slate-500">예측 대상명</label>
          <TextInput value={form.entity_name} onChange={(v) => setForm({ ...form, entity_name: v })} />
          <SelectInput value={form.entity_type} onChange={(v) => setForm({ ...form, entity_type: v })} options={ENTITY_TYPE_OPTIONS} />
          <label className="block text-xs text-slate-500">업무 영역</label>
          <TextInput value={form.business_domain} onChange={(v) => setForm({ ...form, business_domain: v })} />
          <Button onClick={() => void handleCreate()} disabled={busy}>저장</Button>
        </div>
      </Modal>

      <Modal open={detailOpen} onClose={() => setDetailOpen(false)} title="예측 대상 상세" size="xl">
        {detail && (
          <div className="space-y-4 text-sm">
            <div className="grid grid-cols-2 gap-2 text-xs border rounded p-3">
              <p><strong>코드:</strong> {detail.entity_code}</p>
              <p><strong>유형:</strong> {detail.entity_type}</p>
              <p className="col-span-2"><strong>이름:</strong> {detail.entity_name}</p>
            </div>
            {detail.weather_readiness && (
              <div className="grid grid-cols-3 gap-2 text-xs">
                <div className="border rounded p-2">위치 정보: {readinessBadge(detail.weather_readiness.location_ready)}</div>
                <div className="border rounded p-2">단기예보 격자: {readinessBadge(detail.weather_readiness.forecast_ready)}</div>
                <div className="border rounded p-2">관측 기상: {readinessBadge(detail.weather_readiness.observation_ready)}</div>
              </div>
            )}
            <div>
              <h4 className="font-medium mb-2">위치 정보</h4>
              <div className="grid grid-cols-2 gap-2">
                <TextInput value={locationForm.address} onChange={(v) => setLocationForm({ ...locationForm, address: v })} />
                <div />
                <div><label className="text-xs text-slate-500">위도</label><TextInput value={locationForm.latitude} onChange={(v) => setLocationForm({ ...locationForm, latitude: v })} /></div>
                <div><label className="text-xs text-slate-500">경도</label><TextInput value={locationForm.longitude} onChange={(v) => setLocationForm({ ...locationForm, longitude: v })} /></div>
              </div>
              <div className="flex gap-2 mt-2">
                <Button variant="secondary" onClick={() => void handleSaveLocation()} disabled={busy}>위치 저장</Button>
                <Button variant="ghost" onClick={() => void handleCalcGrid()} disabled={busy}>nx/ny 계산</Button>
              </div>
              <p className="text-xs text-amber-700 mt-1">{HELP_TEXTS.gridCalcHint}</p>
            </div>
            <div>
              <h4 className="font-medium mb-2">단기예보 격자 매핑</h4>
              <div className="grid grid-cols-3 gap-2">
                <div><label className="text-xs">forecast_nx</label><TextInput value={gridForm.nx} onChange={(v) => setGridForm({ ...gridForm, nx: v })} /></div>
                <div><label className="text-xs">forecast_ny</label><TextInput value={gridForm.ny} onChange={(v) => setGridForm({ ...gridForm, ny: v })} /></div>
                <div><label className="text-xs">격자명</label><TextInput value={gridForm.grid_name} onChange={(v) => setGridForm({ ...gridForm, grid_name: v })} /></div>
              </div>
              <Button className="mt-2" variant="secondary" onClick={() => void handleSaveGridMapping()} disabled={busy}>격자 매핑 저장</Button>
            </div>
            <div>
              <h4 className="font-medium mb-2">ASOS 관측소 매핑</h4>
              <div className="grid grid-cols-3 gap-2">
                <TextInput value={stationForm.station_code} onChange={(v) => setStationForm({ ...stationForm, station_code: v })} />
                <TextInput value={stationForm.station_name} onChange={(v) => setStationForm({ ...stationForm, station_name: v })} />
                <SelectInput value={stationForm.station_type} onChange={(v) => setStationForm({ ...stationForm, station_type: v })} options={[{ value: "ASOS", label: "ASOS" }, { value: "AWS", label: "AWS" }]} />
              </div>
              <Button className="mt-2" variant="secondary" onClick={() => void handleSaveStation()} disabled={busy}>관측소 매핑 저장</Button>
            </div>
            <div className="flex gap-2">
              <Button variant="ghost" onClick={() => void handlePreview()}>기상 매핑 미리보기</Button>
              <Button variant="danger" onClick={async () => {
                await archivePredictionEntity(detail.entity_id);
                setDetailOpen(false);
                void load();
              }}>보관</Button>
            </div>
          </div>
        )}
      </Modal>
    </div>
  );
}
