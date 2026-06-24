import { useState, useCallback, useRef } from "react";
import {
  LineChart, Line, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  Legend, ResponsiveContainer, AreaChart, Area,
} from "recharts";
import {
  Bell, ChevronDown, ChevronRight, AlertTriangle, CheckCircle, XCircle,
  Clock, RefreshCw, Download, Play, Star, Trash2, Edit, Eye, Plus,
  Search, RotateCcw, X, LogOut, Settings, User, Activity, Database,
  Cpu, BarChart2, Zap, TrendingUp, TrendingDown, Pause, StopCircle,
  FileText, Filter, MoreHorizontal, ArrowRight, Layers,
} from "lucide-react";

// ─── Types ───────────────────────────────────────────────────────────────────

type Screen =
  | "SCR-001" | "SCR-002" | "SCR-003" | "SCR-004" | "SCR-005"
  | "SCR-006" | "SCR-007" | "SCR-008" | "SCR-009" | "SCR-010"
  | "SCR-011" | "SCR-012" | "SCR-013" | "SCR-014" | "SCR-015"
  | "SCR-016" | "SCR-017" | "SCR-018";

type Modal =
  | null | "MOD-001" | "MOD-002" | "MOD-003" | "MOD-004" | "MOD-005"
  | "MOD-006" | "MOD-007" | "MOD-008" | "MOD-009" | "MOD-010";

type ToastType = "success" | "error" | "warning" | "info";
interface Toast { id: number; type: ToastType; message: string; }

type StatusKey =
  | "READY" | "RUNNING" | "SUCCESS" | "FAILED" | "WARNING"
  | "REGISTERED" | "CHAMPION" | "CANDIDATE" | "DISABLED"
  | "DRIFT_DETECTED" | "RETRAIN_REQUIRED" | "정상" | "오류" | "비활성"
  | "검토중" | "요청완료" | "보류" | "제외";

// ─── Dummy Data ───────────────────────────────────────────────────────────────

const forecastVsActual = [
  { time: "00:00", 예측: 142, 실제: 138 }, { time: "02:00", 예측: 128, 실제: 125 },
  { time: "04:00", 예측: 118, 실제: 122 }, { time: "06:00", 예측: 135, 실제: 131 },
  { time: "08:00", 예측: 178, 실제: 182 }, { time: "10:00", 예측: 195, 실제: 191 },
  { time: "12:00", 예측: 201, 실제: 198 }, { time: "14:00", 예측: 208, 실제: 212 },
  { time: "16:00", 예측: 215, 실제: 209 }, { time: "18:00", 예측: 222, 실제: 218 },
  { time: "20:00", 예측: 198, 실제: 195 }, { time: "22:00", 예측: 168, 실제: 171 },
];

const branchError = [
  { name: "중앙지사", mape: 4.2 }, { name: "강남지사", mape: 5.8 },
  { name: "분당지사", mape: 3.9 }, { name: "고양지사", mape: 6.1 },
  { name: "대전지사", mape: 5.3 },
];

const perfTrend = [
  { date: "06-18", mape: 5.2 }, { date: "06-19", mape: 4.9 },
  { date: "06-20", mape: 5.1 }, { date: "06-21", mape: 4.7 },
  { date: "06-22", mape: 4.5 }, { date: "06-23", mape: 4.8 },
  { date: "06-24", mape: 4.6 },
];

const modelPerfComp = [
  { model: "LGBM-v12", mae: 12.4, rmse: 18.7, mape: 4.8 },
  { model: "XGB-v07", mae: 14.1, rmse: 20.3, mape: 5.6 },
  { model: "RF-v05", mae: 16.8, rmse: 23.1, mape: 6.9 },
  { model: "Baseline-v03", mae: 21.2, rmse: 29.4, mape: 9.2 },
];

const featureImportance = [
  { feature: "lag_24h_demand", importance: 0.234 },
  { feature: "temperature", importance: 0.187 },
  { feature: "lag_168h_demand", importance: 0.156 },
  { feature: "hour_of_day", importance: 0.112 },
  { feature: "day_of_week", importance: 0.098 },
  { feature: "supply_temp", importance: 0.087 },
  { feature: "humidity", importance: 0.072 },
  { feature: "flow_rate", importance: 0.054 },
];

const driftScores = [
  { feature: "temperature", score: 0.412, status: "DRIFT_DETECTED" },
  { feature: "lag_24h_demand", score: 0.287, status: "WARNING" },
  { feature: "humidity", score: 0.198, status: "READY" },
  { feature: "supply_temp", score: 0.156, status: "READY" },
  { feature: "flow_rate", score: 0.089, status: "READY" },
];

const pipelineRuns = [
  { id: "RUN-20260624-001", name: "daily_prediction_dag", type: "예측", status: "SUCCESS", start: "2026-06-24 02:00", end: "2026-06-24 02:15", duration: "15분" },
  { id: "RUN-20260624-002", name: "model_training_dag", type: "학습", status: "RUNNING", start: "2026-06-24 03:00", end: "-", duration: "-" },
  { id: "RUN-20260624-003", name: "drift_monitoring_dag", type: "모니터링", status: "FAILED", start: "2026-06-24 04:00", end: "2026-06-24 04:03", duration: "3분" },
  { id: "RUN-20260623-012", name: "data_ingestion_dag", type: "데이터 적재", status: "SUCCESS", start: "2026-06-23 23:00", end: "2026-06-23 23:08", duration: "8분" },
  { id: "RUN-20260623-011", name: "feature_generation_dag", type: "Feature 생성", status: "SUCCESS", start: "2026-06-23 22:00", end: "2026-06-23 22:12", duration: "12분" },
];

const dataSources = [
  { id: "DS-001", type: "열수요 실적", method: "DB", name: "HEAT_DEMAND_HOURLY", status: "정상", lastLoaded: "2026-06-24 02:00" },
  { id: "DS-002", type: "기상", method: "API", name: "KMA_WEATHER_API", status: "정상", lastLoaded: "2026-06-24 01:30" },
  { id: "DS-003", type: "달력", method: "CSV", name: "CALENDAR_2026", status: "정상", lastLoaded: "2026-06-01 00:00" },
  { id: "DS-004", type: "운영", method: "DB", name: "SUPPLY_OPERATION_LOG", status: "오류", lastLoaded: "2026-06-23 22:00" },
  { id: "DS-005", type: "기상", method: "API", name: "OPENWEATHER_API", status: "비활성", lastLoaded: "2026-06-10 00:00" },
];

const featureList = [
  { id: "FEAT-001", name: "lag_24h_demand", group: "열수요 이력", derived: "파생", calc: "24시간 전 수요", active: "사용", importance: 0.234 },
  { id: "FEAT-002", name: "lag_168h_demand", group: "열수요 이력", derived: "파생", calc: "168시간 전 수요", active: "사용", importance: 0.156 },
  { id: "FEAT-003", name: "temperature", group: "기상", derived: "원천", calc: "외기온도(°C)", active: "사용", importance: 0.187 },
  { id: "FEAT-004", name: "humidity", group: "기상", derived: "원천", calc: "습도(%)", active: "사용", importance: 0.072 },
  { id: "FEAT-005", name: "hour_of_day", group: "달력", derived: "파생", calc: "시간대(0-23)", active: "사용", importance: 0.112 },
  { id: "FEAT-006", name: "day_of_week", group: "달력", derived: "파생", calc: "요일(0-6)", active: "사용", importance: 0.098 },
  { id: "FEAT-007", name: "supply_temp", group: "운영", derived: "원천", calc: "공급온도(°C)", active: "사용", importance: 0.087 },
  { id: "FEAT-008", name: "is_holiday", group: "달력", derived: "파생", calc: "공휴일 여부", active: "미사용", importance: 0.041 },
];

const modelRegistry = [
  { name: "heat-demand-lgbm", version: "v12", algo: "LightGBM", status: "CHAMPION", registered: "2026-06-20", mape: "4.8%", runId: "TRN-20260620-001" },
  { name: "heat-demand-xgb", version: "v07", algo: "XGBoost", status: "CANDIDATE", registered: "2026-06-18", mape: "5.6%", runId: "TRN-20260618-003" },
  { name: "heat-demand-rf", version: "v05", algo: "RandomForest", status: "REGISTERED", registered: "2026-06-10", mape: "6.9%", runId: "TRN-20260610-002" },
  { name: "heat-demand-baseline", version: "v03", algo: "Baseline", status: "REGISTERED", registered: "2026-05-15", mape: "9.2%", runId: "TRN-20260515-001" },
];

const retrainingCandidates = [
  { id: "RTC-001", reason: "MAPE 임계치 초과 (6.2%)", model: "heat-demand-lgbm v12", site: "강남지사", risk: "높음", status: "검토중", created: "2026-06-24" },
  { id: "RTC-002", reason: "드리프트 감지 (temperature)", model: "heat-demand-lgbm v12", site: "전체", risk: "중간", status: "검토중", created: "2026-06-23" },
  { id: "RTC-003", reason: "MAPE 임계치 초과 (6.8%)", model: "heat-demand-xgb v07", site: "고양지사", risk: "높음", status: "요청완료", created: "2026-06-22" },
];

const predictionResults = [
  { targetAt: "2026-06-25 00:00", predicted: 142.3, actual: "-", errorRate: "-", site: "중앙지사" },
  { targetAt: "2026-06-25 01:00", predicted: 128.7, actual: "-", errorRate: "-", site: "중앙지사" },
  { targetAt: "2026-06-24 23:00", predicted: 168.4, actual: 171.2, errorRate: "1.6%", site: "중앙지사" },
  { targetAt: "2026-06-24 22:00", predicted: 185.1, actual: 181.8, errorRate: "1.8%", site: "중앙지사" },
  { targetAt: "2026-06-24 21:00", predicted: 202.6, actual: 198.3, errorRate: "2.1%", site: "중앙지사" },
];

// ─── Status Badge ─────────────────────────────────────────────────────────────

const STATUS_CONFIG: Record<StatusKey, { label: string; bg: string; text: string }> = {
  READY:            { label: "대기",       bg: "bg-slate-100",   text: "text-slate-600" },
  RUNNING:          { label: "실행중",     bg: "bg-blue-100",    text: "text-blue-700" },
  SUCCESS:          { label: "성공",       bg: "bg-emerald-100", text: "text-emerald-700" },
  FAILED:           { label: "실패",       bg: "bg-red-100",     text: "text-red-700" },
  WARNING:          { label: "경고",       bg: "bg-amber-100",   text: "text-amber-700" },
  REGISTERED:       { label: "등록",       bg: "bg-blue-100",    text: "text-blue-700" },
  CHAMPION:         { label: "운영중",     bg: "bg-emerald-100", text: "text-emerald-700" },
  CANDIDATE:        { label: "후보",       bg: "bg-purple-100",  text: "text-purple-700" },
  DISABLED:         { label: "비활성",     bg: "bg-slate-100",   text: "text-slate-500" },
  DRIFT_DETECTED:   { label: "드리프트감지", bg: "bg-amber-100",text: "text-amber-700" },
  RETRAIN_REQUIRED: { label: "재학습필요", bg: "bg-red-100",     text: "text-red-700" },
  정상:             { label: "정상",       bg: "bg-emerald-100", text: "text-emerald-700" },
  오류:             { label: "오류",       bg: "bg-red-100",     text: "text-red-700" },
  비활성:           { label: "비활성",     bg: "bg-slate-100",   text: "text-slate-500" },
  검토중:           { label: "검토중",     bg: "bg-amber-100",   text: "text-amber-700" },
  요청완료:         { label: "요청완료",   bg: "bg-blue-100",    text: "text-blue-700" },
  보류:             { label: "보류",       bg: "bg-slate-100",   text: "text-slate-600" },
  제외:             { label: "제외",       bg: "bg-slate-100",   text: "text-slate-400" },
};

function StatusBadge({ status }: { status: string }) {
  const cfg = STATUS_CONFIG[status as StatusKey] ?? { label: status, bg: "bg-slate-100", text: "text-slate-600" };
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium font-mono ${cfg.bg} ${cfg.text}`}>
      {cfg.label}
    </span>
  );
}

// ─── Buttons ──────────────────────────────────────────────────────────────────

function PrimaryBtn({ children, onClick, disabled, icon }: { children: React.ReactNode; onClick?: () => void; disabled?: boolean; icon?: React.ReactNode }) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-blue-700 hover:bg-blue-800 disabled:bg-slate-300 disabled:cursor-not-allowed text-white text-sm font-medium rounded transition-colors"
    >
      {icon}{children}
    </button>
  );
}

function SecondaryBtn({ children, onClick }: { children: React.ReactNode; onClick?: () => void }) {
  return (
    <button
      onClick={onClick}
      className="inline-flex items-center gap-1.5 px-3 py-1.5 border border-slate-300 bg-white hover:bg-slate-50 text-slate-700 text-sm font-medium rounded transition-colors"
    >
      {children}
    </button>
  );
}

function DangerBtn({ children, onClick }: { children: React.ReactNode; onClick?: () => void }) {
  return (
    <button
      onClick={onClick}
      className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-red-600 hover:bg-red-700 text-white text-sm font-medium rounded transition-colors"
    >
      {children}
    </button>
  );
}

function GhostBtn({ children, onClick }: { children: React.ReactNode; onClick?: () => void }) {
  return (
    <button
      onClick={onClick}
      className="inline-flex items-center gap-1 px-2 py-1 text-blue-700 hover:bg-blue-50 text-xs font-medium rounded transition-colors"
    >
      {children}
    </button>
  );
}

// ─── Metric Card ──────────────────────────────────────────────────────────────

function MetricCard({
  label, value, unit, sub, color, icon,
}: {
  label: string; value: string | number; unit?: string; sub?: string;
  color?: string; icon?: React.ReactNode;
}) {
  return (
    <div className="bg-white rounded-lg border border-slate-200 p-4 flex flex-col gap-1">
      <div className="flex items-center justify-between">
        <span className="text-xs text-slate-500 font-medium uppercase tracking-wide">{label}</span>
        {icon && <span className="text-slate-400">{icon}</span>}
      </div>
      <div className={`text-2xl font-bold font-mono ${color ?? "text-slate-900"}`}>
        {value}{unit && <span className="text-sm font-normal text-slate-500 ml-1">{unit}</span>}
      </div>
      {sub && <span className="text-xs text-slate-400">{sub}</span>}
    </div>
  );
}

// ─── Page Header ──────────────────────────────────────────────────────────────

function PageHeader({
  breadcrumb, title, sub,
}: { breadcrumb: string[]; title: string; sub?: string }) {
  return (
    <div className="mb-4">
      <div className="flex items-center gap-1 text-xs text-slate-400 mb-1">
        {breadcrumb.map((b, i) => (
          <span key={i} className="flex items-center gap-1">
            {i > 0 && <ChevronRight size={12} />}
            {b}
          </span>
        ))}
      </div>
      <h1 className="text-lg font-semibold text-slate-900">{title}</h1>
      {sub && <p className="text-xs text-slate-500 mt-0.5">{sub}</p>}
    </div>
  );
}

// ─── Search Panel ─────────────────────────────────────────────────────────────

function SearchPanel({ children, onSearch, onReset }: { children?: React.ReactNode; onSearch?: () => void; onReset?: () => void }) {
  return (
    <div className="bg-white border border-slate-200 rounded-lg p-4 mb-4">
      <div className="flex flex-wrap gap-3 items-end">
        {children}
        <div className="flex gap-2">
          <PrimaryBtn onClick={onSearch} icon={<Search size={13} />}>조회</PrimaryBtn>
          <SecondaryBtn onClick={onReset}><RotateCcw size={13} /> 초기화</SecondaryBtn>
        </div>
      </div>
    </div>
  );
}

function FormField({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-1">
      <label className="text-xs font-medium text-slate-600">{label}</label>
      {children}
    </div>
  );
}

function SelectBox({ options, value, onChange }: { options: string[]; value?: string; onChange?: (v: string) => void }) {
  return (
    <select
      value={value}
      onChange={(e) => onChange?.(e.target.value)}
      className="h-8 px-2 text-sm border border-slate-300 rounded bg-white text-slate-700 focus:outline-none focus:ring-1 focus:ring-blue-500"
    >
      {options.map((o) => <option key={o}>{o}</option>)}
    </select>
  );
}

function TextInput({ placeholder }: { placeholder?: string }) {
  return (
    <input
      placeholder={placeholder}
      className="h-8 px-2 text-sm border border-slate-300 rounded bg-white text-slate-700 focus:outline-none focus:ring-1 focus:ring-blue-500 w-44"
    />
  );
}

// ─── Table ────────────────────────────────────────────────────────────────────

function Table({
  headers, rows, emptyMsg = "조회된 데이터가 없습니다.",
}: { headers: string[]; rows: React.ReactNode[][]; emptyMsg?: string }) {
  return (
    <div className="overflow-auto">
      <table className="w-full text-sm border-collapse">
        <thead>
          <tr className="bg-slate-50 border-y border-slate-200">
            {headers.map((h) => (
              <th key={h} className="px-3 py-2 text-left text-xs font-semibold text-slate-500 uppercase tracking-wide whitespace-nowrap">
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.length === 0 ? (
            <tr>
              <td colSpan={headers.length} className="text-center py-10 text-slate-400 text-sm">
                {emptyMsg}
              </td>
            </tr>
          ) : (
            rows.map((row, i) => (
              <tr key={i} className="border-b border-slate-100 hover:bg-slate-50 transition-colors">
                {row.map((cell, j) => (
                  <td key={j} className="px-3 py-2 text-slate-700 whitespace-nowrap">
                    {cell}
                  </td>
                ))}
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}

// ─── Modal Shell ──────────────────────────────────────────────────────────────

function ModalShell({
  title, onClose, children, footer,
}: { title: string; onClose: () => void; children: React.ReactNode; footer?: React.ReactNode }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-[1px]">
      <div className="bg-white rounded-lg shadow-2xl w-full max-w-lg mx-4 overflow-hidden">
        <div className="flex items-center justify-between px-5 py-3.5 border-b border-slate-200">
          <h2 className="text-base font-semibold text-slate-900">{title}</h2>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-600 transition-colors"><X size={18} /></button>
        </div>
        <div className="px-5 py-4">{children}</div>
        {footer && (
          <div className="flex justify-end gap-2 px-5 py-3 border-t border-slate-100 bg-slate-50">
            {footer}
          </div>
        )}
      </div>
    </div>
  );
}

// ─── Toast System ─────────────────────────────────────────────────────────────

function ToastContainer({ toasts, onRemove }: { toasts: Toast[]; onRemove: (id: number) => void }) {
  const icons = { success: <CheckCircle size={16} />, error: <XCircle size={16} />, warning: <AlertTriangle size={16} />, info: <Bell size={16} /> };
  const colors = { success: "bg-emerald-50 border-emerald-300 text-emerald-800", error: "bg-red-50 border-red-300 text-red-800", warning: "bg-amber-50 border-amber-300 text-amber-800", info: "bg-blue-50 border-blue-300 text-blue-800" };
  return (
    <div className="fixed top-4 right-4 z-[100] flex flex-col gap-2 w-72">
      {toasts.map((t) => (
        <div key={t.id} className={`flex items-start gap-2.5 px-3.5 py-3 border rounded-lg shadow-lg text-sm ${colors[t.type]}`}>
          <span className="mt-0.5 shrink-0">{icons[t.type]}</span>
          <span className="flex-1">{t.message}</span>
          <button onClick={() => onRemove(t.id)} className="shrink-0 opacity-60 hover:opacity-100"><X size={14} /></button>
        </div>
      ))}
    </div>
  );
}

// ─── Menu Structure ───────────────────────────────────────────────────────────

const MENU = [
  {
    label: "대시보드", icon: <Activity size={16} />,
    children: [
      { label: "열수요 예측 현황", screen: "SCR-001" as Screen },
    ],
  },
  {
    label: "데이터 관리", icon: <Database size={16} />,
    children: [
      { label: "데이터 소스 관리", screen: "SCR-002" as Screen },
      { label: "데이터 매핑 설정", screen: "SCR-003" as Screen },
      { label: "데이터 품질 점검", screen: "SCR-004" as Screen },
    ],
  },
  {
    label: "Feature 관리", icon: <Layers size={16} />,
    children: [
      { label: "Feature 목록", screen: "SCR-005" as Screen },
      { label: "Feature Set 관리", screen: "SCR-006" as Screen },
      { label: "Feature 설정 상세", screen: "SCR-007" as Screen },
    ],
  },
  {
    label: "모델 관리", icon: <Cpu size={16} />,
    children: [
      { label: "모델 학습 설정", screen: "SCR-008" as Screen },
      { label: "모델 학습 실행", screen: "SCR-009" as Screen },
      { label: "모델 성능 비교", screen: "SCR-010" as Screen },
      { label: "모델 Registry 관리", screen: "SCR-011" as Screen },
    ],
  },
  {
    label: "예측 관리", icon: <BarChart2 size={16} />,
    children: [
      { label: "배치 예측 실행", screen: "SCR-012" as Screen },
      { label: "예측 결과 조회", screen: "SCR-013" as Screen },
      { label: "실제값 매칭 및 오차 분석", screen: "SCR-014" as Screen },
    ],
  },
  {
    label: "운영 관리", icon: <Settings size={16} />,
    children: [
      { label: "파이프라인 실행 이력", screen: "SCR-015" as Screen },
      { label: "성능 모니터링", screen: "SCR-016" as Screen },
      { label: "드리프트 리포트", screen: "SCR-017" as Screen },
      { label: "재학습 후보 관리", screen: "SCR-018" as Screen },
    ],
  },
];

// ─── Screens ──────────────────────────────────────────────────────────────────

function SCR001({ navigate, openModal, addToast }: AppActions) {
  return (
    <div>
      <PageHeader breadcrumb={["대시보드"]} title="열수요 예측 현황" sub="전체 열수요 예측 운영 상태 및 최근 예측 정확도를 확인합니다." />
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-4">
        <MetricCard label="오늘 예측 대상" value="247" unit="건" icon={<BarChart2 size={16} />} />
        <MetricCard label="평균 MAPE" value="4.8" unit="%" color="text-emerald-600" icon={<TrendingUp size={16} />} />
        <MetricCard label="운영 모델" value="1" unit="개" sub="HDM-LGBM-v12" icon={<Star size={16} />} />
        <MetricCard label="실패 파이프라인" value="1" unit="건" color="text-red-600" icon={<XCircle size={16} />} />
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-4">
        <div className="bg-white border border-slate-200 rounded-lg p-4">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-semibold text-slate-700">시간대별 예측 vs 실제 열수요</h3>
            <GhostBtn onClick={() => navigate("SCR-013")}>결과 상세 <ChevronRight size={12} /></GhostBtn>
          </div>
          <ResponsiveContainer width="100%" height={200}>
            <LineChart data={forecastVsActual}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
              <XAxis dataKey="time" tick={{ fontSize: 11 }} />
              <YAxis tick={{ fontSize: 11 }} />
              <Tooltip />
              <Legend wrapperStyle={{ fontSize: 11 }} />
              <Line type="monotone" dataKey="예측" stroke="#3b82f6" strokeWidth={2} dot={false} />
              <Line type="monotone" dataKey="실제" stroke="#10b981" strokeWidth={2} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </div>
        <div className="bg-white border border-slate-200 rounded-lg p-4">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-semibold text-slate-700">지사별 예측 오차 (MAPE)</h3>
            <GhostBtn onClick={() => navigate("SCR-016")}>성능 상세 <ChevronRight size={12} /></GhostBtn>
          </div>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={branchError}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
              <XAxis dataKey="name" tick={{ fontSize: 11 }} />
              <YAxis tick={{ fontSize: 11 }} unit="%" />
              <Tooltip formatter={(v) => [`${v}%`, "MAPE"]} />
              <Bar dataKey="mape" fill="#3b82f6" radius={[3, 3, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="bg-white border border-slate-200 rounded-lg p-4">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-semibold text-slate-700">최근 예측 실행 이력</h3>
            <GhostBtn onClick={() => navigate("SCR-015")}>실패 이력 보기 <ChevronRight size={12} /></GhostBtn>
          </div>
          <Table
            headers={["실행ID", "파이프라인", "상태", "시작시각"]}
            rows={pipelineRuns.slice(0, 3).map((r) => [
              <span key="id" className="font-mono text-xs text-slate-500">{r.id}</span>,
              r.name,
              <StatusBadge key="s" status={r.status} />,
              <span key="t" className="font-mono text-xs">{r.start}</span>,
            ])}
          />
        </div>
        <div className="bg-white border border-slate-200 rounded-lg p-4">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-semibold text-slate-700">재학습 후보 목록</h3>
            <GhostBtn onClick={() => navigate("SCR-018")}>후보 관리 <ChevronRight size={12} /></GhostBtn>
          </div>
          <Table
            headers={["후보ID", "사유", "위험도", "상태"]}
            rows={retrainingCandidates.map((r) => [
              <span key="id" className="font-mono text-xs text-slate-500">{r.id}</span>,
              <span key="r" className="text-xs">{r.reason}</span>,
              <span key="rk" className={`text-xs font-medium ${r.risk === "높음" ? "text-red-600" : "text-amber-600"}`}>{r.risk}</span>,
              <StatusBadge key="s" status={r.status} />,
            ])}
          />
        </div>
      </div>
      <div className="mt-4 bg-amber-50 border border-amber-200 rounded-lg p-4">
        <div className="flex items-center gap-2 mb-2">
          <AlertTriangle size={15} className="text-amber-600" />
          <span className="text-sm font-semibold text-amber-800">운영 알림</span>
        </div>
        <div className="flex flex-col gap-1.5 text-xs text-amber-700">
          <div className="flex items-center gap-2"><span className="w-1.5 h-1.5 bg-amber-500 rounded-full" />드리프트 감지 2건 — temperature, lag_24h_demand Feature 분포 이상</div>
          <div className="flex items-center gap-2"><span className="w-1.5 h-1.5 bg-red-500 rounded-full" />drift_monitoring_dag 실행 실패 — 2026-06-24 04:00</div>
          <div className="flex items-center gap-2"><span className="w-1.5 h-1.5 bg-amber-500 rounded-full" />재학습 후보 3건 — 검토 필요</div>
        </div>
      </div>
    </div>
  );
}

function SCR002({ openModal, addToast }: AppActions) {
  return (
    <div>
      <PageHeader breadcrumb={["데이터 관리", "데이터 소스 관리"]} title="데이터 소스 관리" sub="열수요 실적, 기상, 달력, 운영 데이터의 원천 데이터 소스를 등록하고 연결 상태를 관리합니다." />
      <SearchPanel onSearch={() => addToast("info", "목록을 조회합니다.")}>
        <FormField label="데이터 유형"><SelectBox options={["전체", "열수요", "기상", "달력", "운영"]} /></FormField>
        <FormField label="연결 방식"><SelectBox options={["전체", "CSV", "DB", "API"]} /></FormField>
        <FormField label="상태"><SelectBox options={["전체", "정상", "오류", "비활성"]} /></FormField>
        <FormField label="키워드"><TextInput placeholder="데이터 소스명 검색" /></FormField>
      </SearchPanel>
      <div className="bg-white border border-slate-200 rounded-lg overflow-hidden">
        <div className="flex items-center justify-between px-4 py-3 border-b border-slate-100">
          <span className="text-sm font-medium text-slate-700">총 {dataSources.length}건</span>
          <div className="flex gap-2">
            <PrimaryBtn onClick={() => addToast("info", "데이터 소스 등록 창을 표시합니다.")} icon={<Plus size={13} />}>신규 등록</PrimaryBtn>
            <SecondaryBtn><Download size={13} /> 다운로드</SecondaryBtn>
          </div>
        </div>
        <Table
          headers={["소스ID", "데이터 유형", "연결 방식", "원천명", "상태", "최근 적재시각", "작업"]}
          rows={dataSources.map((d) => [
            <span key="id" className="font-mono text-xs text-slate-500">{d.id}</span>,
            d.type, d.method,
            <span key="name" className="font-mono text-xs">{d.name}</span>,
            <StatusBadge key="s" status={d.status} />,
            <span key="t" className="font-mono text-xs">{d.lastLoaded}</span>,
            <div key="actions" className="flex gap-1">
              <GhostBtn><Eye size={12} /> 상세</GhostBtn>
              <GhostBtn><Edit size={12} /> 수정</GhostBtn>
              <GhostBtn onClick={() => openModal("MOD-006")}><Zap size={12} /> 연결 테스트</GhostBtn>
              <GhostBtn onClick={() => openModal("MOD-005")}><Trash2 size={12} className="text-red-500" /> 삭제</GhostBtn>
            </div>,
          ])}
        />
      </div>
    </div>
  );
}

function SCR003({ addToast }: AppActions) {
  return (
    <div>
      <PageHeader breadcrumb={["데이터 관리", "데이터 매핑 설정"]} title="데이터 매핑 설정" sub="원천 데이터 컬럼을 THERMOps 표준 스키마 컬럼에 매핑합니다." />
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 mb-4">
        <FormField label="데이터 소스 선택">
          <SelectBox options={["DS-001 열수요 실적", "DS-002 기상", "DS-003 달력"]} />
        </FormField>
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="bg-white border border-slate-200 rounded-lg overflow-hidden">
          <div className="px-4 py-2.5 border-b border-slate-100 bg-slate-50">
            <span className="text-xs font-semibold text-slate-600 uppercase tracking-wide">원천 컬럼</span>
          </div>
          <Table
            headers={["원천 컬럼명", "타입", "샘플값"]}
            rows={[
              ["measured_datetime", "TIMESTAMP", "2026-06-24 00:00"],
              ["site_code", "VARCHAR", "SITE-001"],
              ["demand_kwh", "FLOAT", "142.3"],
              ["temp_celsius", "FLOAT", "18.2"],
              ["humi_pct", "FLOAT", "65.0"],
            ].map((r) => r.map((c, i) => (
              <span key={i} className="font-mono text-xs">{c}</span>
            )))}
          />
        </div>
        <div className="bg-white border border-slate-200 rounded-lg overflow-hidden">
          <div className="px-4 py-2.5 border-b border-slate-100 bg-slate-50">
            <span className="text-xs font-semibold text-slate-600 uppercase tracking-wide">표준 컬럼 매핑</span>
          </div>
          <Table
            headers={["표준 컬럼", "원천 컬럼", "필수", "변환 규칙"]}
            rows={[
              ["measured_at", "measured_datetime", "Y", "-"],
              ["site_id", "site_code", "Y", "-"],
              ["heat_demand", "demand_kwh", "Y", "× 0.86"],
              ["temperature", "temp_celsius", "N", "-"],
              ["humidity", "humi_pct", "N", "-"],
            ].map((r) => [
              <span key="0" className="font-mono text-xs text-blue-700">{r[0]}</span>,
              <span key="1" className="font-mono text-xs">{r[1]}</span>,
              <span key="2" className={`text-xs font-bold ${r[2] === "Y" ? "text-red-500" : "text-slate-400"}`}>{r[2]}</span>,
              <span key="3" className="font-mono text-xs text-slate-500">{r[3]}</span>,
            ])}
          />
        </div>
      </div>
      <div className="flex gap-2 mt-4">
        <PrimaryBtn onClick={() => addToast("success", "매핑 설정이 저장되었습니다.")}>저장</PrimaryBtn>
        <SecondaryBtn onClick={() => addToast("info", "자동 매핑 결과를 표시합니다.")}>자동 매핑</SecondaryBtn>
        <SecondaryBtn onClick={() => addToast("info", "매핑 검증 결과를 표시합니다.")}>매핑 검증</SecondaryBtn>
        <SecondaryBtn onClick={() => addToast("info", "변환 데이터 미리보기를 표시합니다.")}>미리보기</SecondaryBtn>
        <SecondaryBtn>취소</SecondaryBtn>
      </div>
    </div>
  );
}

function SCR004({ addToast }: AppActions) {
  return (
    <div>
      <PageHeader breadcrumb={["데이터 관리", "데이터 품질 점검"]} title="데이터 품질 점검" sub="적재 데이터의 결측, 중복, 이상치, 시간 누락 여부를 점검합니다." />
      <SearchPanel onSearch={() => addToast("info", "품질 점검을 조회합니다.")}>
        <FormField label="데이터셋"><SelectBox options={["DS-001 열수요 실적", "DS-002 기상"]} /></FormField>
        <FormField label="점검 기간"><TextInput placeholder="2026-06-01 ~ 2026-06-24" /></FormField>
        <FormField label="점검 유형"><SelectBox options={["전체", "결측", "중복", "이상치", "시간 누락"]} /></FormField>
        <FormField label="지사/권역"><SelectBox options={["전체", "중앙지사", "강남지사", "분당지사"]} /></FormField>
      </SearchPanel>
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-4">
        <MetricCard label="품질 총점" value="91.2" unit="점" color="text-emerald-600" />
        <MetricCard label="결측률" value="1.3" unit="%" />
        <MetricCard label="중복률" value="0.2" unit="%" />
        <MetricCard label="이상치 건수" value="47" unit="건" color="text-amber-600" />
      </div>
      <div className="bg-white border border-slate-200 rounded-lg overflow-hidden">
        <div className="flex items-center justify-between px-4 py-3 border-b border-slate-100">
          <span className="text-sm font-medium text-slate-700">품질 점검 결과</span>
          <div className="flex gap-2">
            <PrimaryBtn onClick={() => addToast("success", "품질 점검을 실행합니다.")} icon={<Play size={13} />}>품질 점검 실행</PrimaryBtn>
            <SecondaryBtn><Download size={13} /> 결과 다운로드</SecondaryBtn>
          </div>
        </div>
        <Table
          headers={["점검 항목", "결과", "영향도", "건수", "조치 상태", "작업"]}
          rows={[
            ["결측값 점검", "WARNING", "중간", "312건", "검토중"],
            ["중복 레코드", "SUCCESS", "낮음", "48건", "조치완료"],
            ["이상치 탐지", "WARNING", "높음", "47건", "검토중"],
            ["시간 연속성", "SUCCESS", "낮음", "0건", "해당없음"],
          ].map((r) => [
            r[0],
            <StatusBadge key="s" status={r[1]} />,
            <span key="e" className={`text-xs font-medium ${r[2] === "높음" ? "text-red-600" : r[2] === "중간" ? "text-amber-600" : "text-slate-500"}`}>{r[2]}</span>,
            <span key="c" className="font-mono text-xs">{r[3]}</span>,
            r[4],
            <GhostBtn key="act"><Eye size={12} /> 상세보기</GhostBtn>,
          ])}
        />
      </div>
    </div>
  );
}

function SCR005({ openModal, addToast }: AppActions) {
  return (
    <div>
      <PageHeader breadcrumb={["Feature 관리", "Feature 목록"]} title="Feature 목록" sub="모델 학습에 사용할 수 있는 원천 Feature와 파생 Feature를 관리합니다." />
      <SearchPanel onSearch={() => addToast("info", "Feature를 조회합니다.")}>
        <FormField label="Feature 그룹"><SelectBox options={["전체", "열수요 이력", "기상", "달력", "운영", "지역", "파생"]} /></FormField>
        <FormField label="사용 여부"><SelectBox options={["전체", "사용", "미사용"]} /></FormField>
        <FormField label="파생 여부"><SelectBox options={["전체", "원천", "파생"]} /></FormField>
        <FormField label="키워드"><TextInput placeholder="Feature명 검색" /></FormField>
      </SearchPanel>
      <div className="bg-white border border-slate-200 rounded-lg overflow-hidden">
        <div className="flex items-center justify-between px-4 py-3 border-b border-slate-100">
          <span className="text-sm font-medium text-slate-700">총 {featureList.length}건</span>
          <PrimaryBtn onClick={() => addToast("info", "Feature 등록 창을 표시합니다.")} icon={<Plus size={13} />}>신규 등록</PrimaryBtn>
        </div>
        <Table
          headers={["Feature ID", "Feature 명", "그룹", "파생 여부", "계산 방식", "사용 여부", "중요도", "작업"]}
          rows={featureList.map((f) => [
            <span key="id" className="font-mono text-xs text-slate-500">{f.id}</span>,
            <span key="name" className="font-mono text-xs text-blue-700">{f.name}</span>,
            f.group, f.derived, f.calc,
            <StatusBadge key="s" status={f.active === "사용" ? "READY" : "DISABLED"} />,
            <span key="i" className="font-mono text-xs">{f.importance.toFixed(3)}</span>,
            <div key="a" className="flex gap-1">
              <GhostBtn><Eye size={12} /> 상세</GhostBtn>
              <GhostBtn><Edit size={12} /> 수정</GhostBtn>
              <GhostBtn onClick={() => addToast("warning", "비활성 처리하겠습니까?")}><StopCircle size={12} /> 비활성</GhostBtn>
            </div>,
          ])}
        />
      </div>
    </div>
  );
}

function SCR006({ navigate, openModal, addToast }: AppActions) {
  return (
    <div>
      <PageHeader breadcrumb={["Feature 관리", "Feature Set 관리"]} title="Feature Set 관리" sub="모델 학습에 사용할 Feature 조합을 Feature Set으로 관리합니다." />
      <div className="bg-white border border-slate-200 rounded-lg overflow-hidden">
        <div className="flex items-center justify-between px-4 py-3 border-b border-slate-100">
          <span className="text-sm font-medium text-slate-700">Feature Set 목록</span>
          <PrimaryBtn icon={<Plus size={13} />} onClick={() => addToast("info", "Feature Set 등록 영역을 표시합니다.")}>신규 Feature Set</PrimaryBtn>
        </div>
        <Table
          headers={["Feature Set명", "설명", "Feature 수", "사용 모델", "생성일", "작업"]}
          rows={[
            ["기본_시간별_열수요_v1", "기본 시간별 예측 Feature Set", "12", "heat-demand-lgbm v12", "2026-05-10"],
            ["기상_강화_Feature_v2", "기상 Feature 강화 버전", "16", "-", "2026-06-01"],
            ["경량_예측_v1", "빠른 배치 예측용 경량 Feature", "8", "heat-demand-baseline v03", "2026-04-20"],
          ].map((r) => [
            <span key="name" className="font-medium text-sm text-blue-700">{r[0]}</span>,
            <span key="desc" className="text-xs text-slate-500">{r[1]}</span>,
            <span key="cnt" className="font-mono text-xs">{r[2]}</span>,
            <span key="model" className="text-xs">{r[3]}</span>,
            <span key="date" className="font-mono text-xs">{r[4]}</span>,
            <div key="a" className="flex gap-1">
              <GhostBtn onClick={() => navigate("SCR-007")}><Eye size={12} /> 상세</GhostBtn>
              <GhostBtn onClick={() => addToast("info", "복사 후 이름을 입력해주세요.")}><FileText size={12} /> 복사</GhostBtn>
              <GhostBtn onClick={() => openModal("MOD-005")}><Trash2 size={12} className="text-red-500" /> 삭제</GhostBtn>
            </div>,
          ])}
        />
      </div>
    </div>
  );
}

function SCR007({ navigate, addToast }: AppActions) {
  return (
    <div>
      <PageHeader breadcrumb={["Feature 관리", "Feature Set 관리", "Feature 설정 상세"]} title="Feature 설정 상세" sub="선택한 Feature Set의 상세 구성, 적용 대상, 결측 처리, 변환 규칙을 설정합니다." />
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-4">
        <div className="bg-white border border-slate-200 rounded-lg p-4">
          <h3 className="text-sm font-semibold text-slate-700 mb-3">기본 정보</h3>
          <div className="flex flex-col gap-3">
            <FormField label="Feature Set 명"><TextInput placeholder="기본_시간별_열수요_v1" /></FormField>
            <FormField label="설명"><TextInput placeholder="Feature Set 설명을 입력하세요." /></FormField>
            <FormField label="적용 대상"><SelectBox options={["전체", "중앙지사", "강남지사", "분당지사"]} /></FormField>
            <FormField label="결측 처리"><SelectBox options={["직전값", "평균값", "0", "제외"]} /></FormField>
            <FormField label="정규화 여부"><SelectBox options={["사용", "미사용"]} /></FormField>
          </div>
        </div>
        <div className="bg-white border border-slate-200 rounded-lg overflow-hidden">
          <div className="px-4 py-2.5 border-b border-slate-100 bg-slate-50 flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-600 uppercase tracking-wide">Feature 목록</span>
            <GhostBtn onClick={() => addToast("info", "Feature 선택 창을 표시합니다.")}><Plus size={12} /> Feature 추가</GhostBtn>
          </div>
          <Table
            headers={["Feature 명", "그룹", "사용 여부"]}
            rows={featureList.map((f) => [
              <span key="name" className="font-mono text-xs text-blue-700">{f.name}</span>,
              f.group,
              <input key="cb" type="checkbox" defaultChecked={f.active === "사용"} className="accent-blue-600" />,
            ])}
          />
        </div>
      </div>
      <div className="flex gap-2">
        <PrimaryBtn onClick={() => addToast("success", "저장이 완료되었습니다.")}>저장</PrimaryBtn>
        <SecondaryBtn onClick={() => navigate("SCR-008")}>모델 학습 설정으로 이동</SecondaryBtn>
        <SecondaryBtn onClick={() => navigate("SCR-006")}>목록</SecondaryBtn>
      </div>
    </div>
  );
}

function SCR008({ openModal, addToast }: AppActions) {
  return (
    <div>
      <PageHeader breadcrumb={["모델 관리", "모델 학습 설정"]} title="모델 학습 설정" sub="모델 학습 조건을 정의하고 저장합니다." />
      <SearchPanel onSearch={() => addToast("info", "설정 목록을 조회합니다.")}>
        <FormField label="학습 설정명"><TextInput placeholder="설정명 검색" /></FormField>
        <FormField label="알고리즘"><SelectBox options={["전체", "LightGBM", "XGBoost", "RandomForest", "Baseline"]} /></FormField>
        <FormField label="예측 단위"><SelectBox options={["전체", "시간별", "일별"]} /></FormField>
        <FormField label="상태"><SelectBox options={["전체", "사용", "미사용"]} /></FormField>
      </SearchPanel>
      <div className="grid grid-cols-1 lg:grid-cols-5 gap-4">
        <div className="lg:col-span-2 bg-white border border-slate-200 rounded-lg overflow-hidden">
          <div className="px-4 py-2.5 border-b border-slate-100 bg-slate-50 flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-600">설정 목록</span>
            <PrimaryBtn icon={<Plus size={12} />} onClick={() => addToast("info", "신규 입력 상태를 표시합니다.")}>신규</PrimaryBtn>
          </div>
          <div className="divide-y divide-slate-100">
            {["시간별_LGBM_기본설정", "일별_XGB_강남특화", "시간별_RF_경량"].map((name, i) => (
              <div key={name} className={`px-4 py-3 cursor-pointer hover:bg-blue-50 flex items-center justify-between ${i === 0 ? "bg-blue-50 border-l-2 border-blue-600" : ""}`}>
                <span className="text-sm font-medium text-slate-800">{name}</span>
                <StatusBadge status={i === 2 ? "DISABLED" : "READY"} />
              </div>
            ))}
          </div>
        </div>
        <div className="lg:col-span-3 bg-white border border-slate-200 rounded-lg p-4">
          <h3 className="text-sm font-semibold text-slate-700 mb-4">학습 설정 상세</h3>
          <div className="grid grid-cols-2 gap-3">
            {[
              ["학습 설정명", "시간별_LGBM_기본설정"],
              ["학습 대상", "전체 지사"],
              ["학습 기간", "최근 2년"],
              ["검증 기간", "최근 3개월"],
              ["예측 단위", "시간별"],
              ["예측 기간", "D+1, D+7"],
              ["알고리즘", "LightGBM"],
              ["평가 지표", "MAE, RMSE, MAPE"],
            ].map(([label, value]) => (
              <FormField key={label} label={label}>
                <TextInput placeholder={value} />
              </FormField>
            ))}
            <div className="col-span-2">
              <FormField label="Feature Set">
                <div className="flex gap-2">
                  <input className="h-8 px-2 text-sm border border-slate-300 rounded flex-1 font-mono" defaultValue="기본_시간별_열수요_v1" readOnly />
                  <SecondaryBtn onClick={() => addToast("info", "Feature Set 선택 창을 표시합니다.")}>Feature 선택</SecondaryBtn>
                </div>
              </FormField>
            </div>
          </div>
          <div className="flex gap-2 mt-4">
            <PrimaryBtn onClick={() => addToast("success", "저장이 완료되었습니다.")}>저장</PrimaryBtn>
            <PrimaryBtn onClick={() => openModal("MOD-001")} icon={<Play size={13} />}>학습 실행</PrimaryBtn>
            <SecondaryBtn>취소</SecondaryBtn>
            <DangerBtn onClick={() => openModal("MOD-005")}><Trash2 size={13} /> 삭제</DangerBtn>
          </div>
        </div>
      </div>
    </div>
  );
}

function SCR009({ navigate, openModal, addToast }: AppActions) {
  const [running, setRunning] = useState(false);
  return (
    <div>
      <PageHeader breadcrumb={["모델 관리", "모델 학습 실행"]} title="모델 학습 실행" sub="저장된 학습 설정을 기반으로 모델 학습 파이프라인을 실행하고 이력을 확인합니다." />
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 mb-4">
        <div className="lg:col-span-1 bg-white border border-slate-200 rounded-lg p-4">
          <h3 className="text-sm font-semibold text-slate-700 mb-3">학습 실행 조건</h3>
          <div className="flex flex-col gap-3">
            <FormField label="학습 설정"><SelectBox options={["시간별_LGBM_기본설정", "일별_XGB_강남특화"]} /></FormField>
            <FormField label="대상 지사"><SelectBox options={["전체 지사", "중앙지사", "강남지사"]} /></FormField>
            <FormField label="실행 방식"><SelectBox options={["즉시 실행", "예약 실행"]} /></FormField>
          </div>
          <div className="flex gap-2 mt-4">
            <PrimaryBtn onClick={() => openModal("MOD-001")} icon={<Play size={13} />}>학습 실행</PrimaryBtn>
            <SecondaryBtn onClick={() => navigate("SCR-010")}><BarChart2 size={13} /> 성능 비교</SecondaryBtn>
          </div>
          {running && (
            <div className="mt-4 flex flex-col gap-2">
              {["데이터 준비", "Feature 생성", "모델 학습", "성능 평가", "Registry 등록"].map((step, i) => (
                <div key={step} className="flex items-center gap-2 text-xs">
                  <span className={`w-4 h-4 rounded-full flex items-center justify-center ${i < 2 ? "bg-emerald-500 text-white" : i === 2 ? "bg-blue-500 text-white" : "bg-slate-200"}`}>
                    {i < 2 ? "✓" : i === 2 ? "…" : ""}
                  </span>
                  <span className={i < 2 ? "text-emerald-700" : i === 2 ? "text-blue-700 font-medium" : "text-slate-400"}>{step}</span>
                </div>
              ))}
            </div>
          )}
        </div>
        <div className="lg:col-span-2 bg-white border border-slate-200 rounded-lg overflow-hidden">
          <div className="px-4 py-2.5 border-b border-slate-100 bg-slate-50">
            <span className="text-xs font-semibold text-slate-600 uppercase tracking-wide">실행 이력</span>
          </div>
          <Table
            headers={["실행ID", "설정명", "상태", "시작시각", "종료시각", "MAPE", "작업"]}
            rows={[
              ["TRN-20260624-001", "시간별_LGBM_기본설정", "SUCCESS", "2026-06-24 01:00", "2026-06-24 02:15", "4.8%"],
              ["TRN-20260623-003", "일별_XGB_강남특화", "RUNNING", "2026-06-23 22:00", "-", "-"],
              ["TRN-20260622-002", "시간별_LGBM_기본설정", "SUCCESS", "2026-06-22 01:00", "2026-06-22 02:10", "4.9%"],
            ].map((r) => [
              <span key="id" className="font-mono text-xs text-slate-500">{r[0]}</span>,
              <span key="name" className="text-xs">{r[1]}</span>,
              <StatusBadge key="s" status={r[2]} />,
              <span key="st" className="font-mono text-xs">{r[3]}</span>,
              <span key="et" className="font-mono text-xs">{r[4]}</span>,
              <span key="mape" className="font-mono text-xs">{r[5]}</span>,
              <div key="a" className="flex gap-1">
                <GhostBtn onClick={() => openModal("MOD-009")}><Eye size={12} /> 로그</GhostBtn>
                <GhostBtn onClick={() => addToast("warning", "중단하시겠습니까?")}><StopCircle size={12} /> 중단</GhostBtn>
              </div>,
            ])}
          />
        </div>
      </div>
    </div>
  );
}

function SCR010({ navigate, openModal, addToast }: AppActions) {
  return (
    <div>
      <PageHeader breadcrumb={["모델 관리", "모델 성능 비교"]} title="모델 성능 비교" sub="모델별/버전별 성능지표를 비교하고 운영 후보 모델을 검토합니다." />
      <SearchPanel onSearch={() => addToast("info", "성능 데이터를 조회합니다.")}>
        <FormField label="모델명"><SelectBox options={["전체", "heat-demand-lgbm", "heat-demand-xgb"]} /></FormField>
        <FormField label="평가 기간"><TextInput placeholder="2026-06-01 ~ 2026-06-24" /></FormField>
        <FormField label="지사/권역"><SelectBox options={["전체", "중앙지사", "강남지사"]} /></FormField>
        <FormField label="평가 지표"><SelectBox options={["MAPE", "MAE", "RMSE"]} /></FormField>
      </SearchPanel>
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 mb-4">
        <div className="bg-emerald-50 border border-emerald-200 rounded-lg p-4">
          <div className="text-xs font-medium text-emerald-600 mb-1">Champion 모델</div>
          <div className="text-base font-bold text-slate-900">heat-demand-lgbm v12</div>
          <div className="font-mono text-sm text-emerald-700 mt-1">MAPE 4.8%</div>
        </div>
        <div className="bg-purple-50 border border-purple-200 rounded-lg p-4">
          <div className="text-xs font-medium text-purple-600 mb-1">후보 모델</div>
          <div className="text-base font-bold text-slate-900">heat-demand-xgb v07</div>
          <div className="font-mono text-sm text-purple-700 mt-1">MAPE 5.6%</div>
        </div>
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
          <div className="text-xs font-medium text-blue-600 mb-1">최고 성능 (이번 주)</div>
          <div className="text-base font-bold text-slate-900">heat-demand-lgbm v12</div>
          <div className="font-mono text-sm text-blue-700 mt-1">MAE 12.4</div>
        </div>
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-4">
        <div className="bg-white border border-slate-200 rounded-lg p-4">
          <h3 className="text-sm font-semibold text-slate-700 mb-3">모델별 성능 비교 (MAPE)</h3>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={modelPerfComp} layout="vertical">
              <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
              <XAxis type="number" tick={{ fontSize: 11 }} unit="%" />
              <YAxis dataKey="model" type="category" tick={{ fontSize: 11 }} width={90} />
              <Tooltip formatter={(v) => [`${v}%`, "MAPE"]} />
              <Bar dataKey="mape" fill="#3b82f6" radius={[0, 3, 3, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
        <div className="bg-white border border-slate-200 rounded-lg p-4">
          <h3 className="text-sm font-semibold text-slate-700 mb-3">Feature 중요도 (Top 8)</h3>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={featureImportance} layout="vertical">
              <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
              <XAxis type="number" tick={{ fontSize: 11 }} />
              <YAxis dataKey="feature" type="category" tick={{ fontSize: 10 }} width={110} />
              <Tooltip />
              <Bar dataKey="importance" fill="#10b981" radius={[0, 3, 3, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>
      <div className="bg-white border border-slate-200 rounded-lg overflow-hidden">
        <div className="flex items-center justify-between px-4 py-3 border-b border-slate-100">
          <span className="text-sm font-medium text-slate-700">성능 목록</span>
          <SecondaryBtn><Download size={13} /> 결과 다운로드</SecondaryBtn>
        </div>
        <Table
          headers={["모델명", "버전", "알고리즘", "상태", "MAE", "RMSE", "MAPE", "작업"]}
          rows={modelPerfComp.map((m, i) => [
            m.model.split("-")[0] + "-demand-" + m.model.split("-")[1],
            ["v12", "v07", "v05", "v03"][i],
            m.model.includes("LGBM") ? "LightGBM" : m.model.includes("XGB") ? "XGBoost" : m.model.includes("RF") ? "RandomForest" : "Baseline",
            <StatusBadge key="s" status={["CHAMPION", "CANDIDATE", "REGISTERED", "REGISTERED"][i]} />,
            <span key="mae" className="font-mono text-xs">{m.mae}</span>,
            <span key="rmse" className="font-mono text-xs">{m.rmse}</span>,
            <span key="mape" className="font-mono text-xs">{m.mape}%</span>,
            <div key="a" className="flex gap-1">
              <GhostBtn onClick={() => openModal("MOD-008")}><Eye size={12} /> 상세</GhostBtn>
              <GhostBtn onClick={() => openModal("MOD-003")}><Star size={12} /> Champion</GhostBtn>
              <GhostBtn onClick={() => navigate("SCR-011")}><ArrowRight size={12} /> Registry</GhostBtn>
            </div>,
          ])}
        />
      </div>
    </div>
  );
}

function SCR011({ openModal, addToast, navigate }: AppActions) {
  return (
    <div>
      <PageHeader breadcrumb={["모델 관리", "모델 Registry 관리"]} title="모델 Registry 관리" sub="MLflow Registry와 연계되는 모델 버전, 상태, Champion 모델을 관리합니다." />
      <div className="bg-white border border-slate-200 rounded-lg overflow-hidden">
        <div className="flex items-center justify-between px-4 py-3 border-b border-slate-100">
          <span className="text-sm font-medium text-slate-700">총 {modelRegistry.length}건</span>
          <div className="flex gap-2">
            <SecondaryBtn onClick={() => navigate("SCR-010")}><BarChart2 size={13} /> 성능 비교</SecondaryBtn>
            <SecondaryBtn><Download size={13} /> 다운로드</SecondaryBtn>
          </div>
        </div>
        <Table
          headers={["모델명", "버전", "알고리즘", "상태", "MAPE", "등록일", "생성 실행ID", "작업"]}
          rows={modelRegistry.map((m) => [
            <span key="name" className="font-mono text-xs text-blue-700">{m.name}</span>,
            <span key="ver" className="font-mono text-xs font-bold">{m.version}</span>,
            m.algo,
            <StatusBadge key="s" status={m.status} />,
            <span key="mape" className="font-mono text-xs">{m.mape}</span>,
            <span key="date" className="font-mono text-xs">{m.registered}</span>,
            <span key="run" className="font-mono text-xs text-slate-400">{m.runId}</span>,
            <div key="a" className="flex gap-1">
              <GhostBtn onClick={() => openModal("MOD-008")}><Eye size={12} /> 상세</GhostBtn>
              {m.status !== "CHAMPION" && (
                <GhostBtn onClick={() => openModal("MOD-003")}><Star size={12} /> Champion 지정</GhostBtn>
              )}
              <GhostBtn onClick={() => addToast("warning", "비활성 처리하겠습니까?")}><StopCircle size={12} /> 비활성</GhostBtn>
            </div>,
          ])}
        />
      </div>
    </div>
  );
}

function SCR012({ navigate, openModal, addToast }: AppActions) {
  return (
    <div>
      <PageHeader breadcrumb={["예측 관리", "배치 예측 실행"]} title="배치 예측 실행" sub="Champion 모델 또는 선택 모델을 기준으로 D+1/D+7 열수요 예측 배치를 실행합니다." />
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="bg-white border border-slate-200 rounded-lg p-4">
          <h3 className="text-sm font-semibold text-slate-700 mb-4">배치 예측 설정</h3>
          <div className="flex flex-col gap-3">
            <FormField label="예측 대상"><SelectBox options={["전체 지사", "중앙지사", "강남지사", "분당지사", "고양지사", "대전지사"]} /></FormField>
            <FormField label="예측 기간"><SelectBox options={["D+1", "D+7", "D+1 + D+7"]} /></FormField>
            <FormField label="예측 단위"><SelectBox options={["시간별", "일별"]} /></FormField>
            <FormField label="모델 선택"><SelectBox options={["Champion (heat-demand-lgbm v12)", "heat-demand-xgb v07", "특정 버전 지정"]} /></FormField>
            <FormField label="실행 방식"><SelectBox options={["즉시 실행", "예약 실행"]} /></FormField>
          </div>
          <div className="flex gap-2 mt-4">
            <PrimaryBtn onClick={() => openModal("MOD-002")} icon={<Play size={13} />}>예측 실행</PrimaryBtn>
            <SecondaryBtn onClick={() => addToast("info", "입력값을 초기화합니다.")}><RotateCcw size={13} /> 초기화</SecondaryBtn>
          </div>
        </div>
        <div className="bg-white border border-slate-200 rounded-lg overflow-hidden">
          <div className="px-4 py-2.5 border-b border-slate-100 bg-slate-50 flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-600 uppercase tracking-wide">최근 실행 이력</span>
            <GhostBtn onClick={() => navigate("SCR-015")}>전체 이력 <ChevronRight size={12} /></GhostBtn>
          </div>
          <Table
            headers={["실행ID", "대상", "예측기간", "상태", "시작시각"]}
            rows={[
              ["PRD-20260624-001", "전체 지사", "D+1", "SUCCESS", "2026-06-24 02:00"],
              ["PRD-20260624-002", "강남지사", "D+7", "RUNNING", "2026-06-24 06:00"],
              ["PRD-20260623-008", "전체 지사", "D+1", "SUCCESS", "2026-06-23 02:00"],
            ].map((r) => [
              <span key="id" className="font-mono text-xs text-slate-500">{r[0]}</span>,
              r[1], r[2],
              <StatusBadge key="s" status={r[3]} />,
              <span key="t" className="font-mono text-xs">{r[4]}</span>,
            ])}
          />
          <div className="flex gap-2 p-3 border-t border-slate-100">
            <GhostBtn onClick={() => navigate("SCR-013")}>결과 보기 <ChevronRight size={12} /></GhostBtn>
          </div>
        </div>
      </div>
    </div>
  );
}

function SCR013({ navigate, addToast }: AppActions) {
  return (
    <div>
      <PageHeader breadcrumb={["예측 관리", "예측 결과 조회"]} title="예측 결과 조회" sub="생성된 열수요 예측 결과를 조회하고 실제값과 비교합니다." />
      <SearchPanel onSearch={() => addToast("info", "예측 결과를 조회합니다.")}>
        <FormField label="예측 대상 기간"><TextInput placeholder="2026-06-24 ~ 2026-06-25" /></FormField>
        <FormField label="지사/권역"><SelectBox options={["전체", "중앙지사", "강남지사"]} /></FormField>
        <FormField label="모델명/버전"><SelectBox options={["heat-demand-lgbm v12", "heat-demand-xgb v07"]} /></FormField>
        <FormField label="예측 기간"><SelectBox options={["D+1", "D+7"]} /></FormField>
      </SearchPanel>
      <div className="bg-white border border-slate-200 rounded-lg p-4 mb-4">
        <h3 className="text-sm font-semibold text-slate-700 mb-3">예측값 vs 실제값</h3>
        <ResponsiveContainer width="100%" height={220}>
          <LineChart data={forecastVsActual}>
            <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
            <XAxis dataKey="time" tick={{ fontSize: 11 }} />
            <YAxis tick={{ fontSize: 11 }} unit="GJ" />
            <Tooltip />
            <Legend wrapperStyle={{ fontSize: 11 }} />
            <Line type="monotone" dataKey="예측" stroke="#3b82f6" strokeWidth={2} dot={false} />
            <Line type="monotone" dataKey="실제" stroke="#10b981" strokeWidth={2} dot={false} strokeDasharray="5 5" />
          </LineChart>
        </ResponsiveContainer>
      </div>
      <div className="bg-white border border-slate-200 rounded-lg overflow-hidden">
        <div className="flex items-center justify-between px-4 py-3 border-b border-slate-100">
          <span className="text-sm font-medium text-slate-700">예측 결과 목록</span>
          <div className="flex gap-2">
            <SecondaryBtn onClick={() => navigate("SCR-014")}><ArrowRight size={13} /> 실제값 매칭</SecondaryBtn>
            <SecondaryBtn><Download size={13} /> 다운로드</SecondaryBtn>
          </div>
        </div>
        <Table
          headers={["target_at", "predicted_demand", "actual_demand", "error_rate", "지사"]}
          rows={predictionResults.map((r) => [
            <span key="t" className="font-mono text-xs">{r.targetAt}</span>,
            <span key="p" className="font-mono text-xs text-blue-700">{r.predicted}</span>,
            <span key="a" className="font-mono text-xs text-emerald-700">{r.actual}</span>,
            <span key="e" className={`font-mono text-xs ${r.errorRate === "-" ? "text-slate-400" : "text-amber-700"}`}>{r.errorRate}</span>,
            r.site,
          ])}
        />
      </div>
    </div>
  );
}

function SCR014({ addToast }: AppActions) {
  return (
    <div>
      <PageHeader breadcrumb={["예측 관리", "실제값 매칭 및 오차 분석"]} title="실제값 매칭 및 오차 분석" sub="예측값과 실제 열수요 실적값을 매칭하고 오차를 분석합니다." />
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-4">
        <MetricCard label="총 건수" value="5,928" unit="건" />
        <MetricCard label="매칭 성공" value="5,881" unit="건" color="text-emerald-600" />
        <MetricCard label="미매칭" value="47" unit="건" color="text-red-600" />
        <MetricCard label="평균 오차" value="4.8" unit="%" />
      </div>
      <div className="bg-white border border-slate-200 rounded-lg p-4 mb-4">
        <h3 className="text-sm font-semibold text-slate-700 mb-3">시간대별/지사별 오차</h3>
        <ResponsiveContainer width="100%" height={200}>
          <BarChart data={branchError}>
            <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
            <XAxis dataKey="name" tick={{ fontSize: 11 }} />
            <YAxis tick={{ fontSize: 11 }} unit="%" />
            <Tooltip formatter={(v) => [`${v}%`, "오차율"]} />
            <Bar dataKey="mape" fill="#f59e0b" radius={[3, 3, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>
      <div className="flex gap-2 mb-4">
        <PrimaryBtn onClick={() => addToast("info", "매칭을 실행합니다.")} icon={<Play size={13} />}>실제값 매칭 실행</PrimaryBtn>
        <SecondaryBtn onClick={() => addToast("info", "오차를 재계산합니다.")}>오차 재계산</SecondaryBtn>
        <SecondaryBtn><Download size={13} /> 결과 다운로드</SecondaryBtn>
      </div>
    </div>
  );
}

function SCR015({ openModal, addToast }: AppActions) {
  const [filtered, setFiltered] = useState(false);
  const rows = filtered ? pipelineRuns.filter((r) => r.status === "FAILED") : pipelineRuns;
  return (
    <div>
      <PageHeader breadcrumb={["운영 관리", "파이프라인 실행 이력"]} title="파이프라인 실행 이력" sub="Airflow/Dagster 기반 파이프라인 실행 상태를 확인합니다." />
      <SearchPanel onSearch={() => addToast("info", "실행 이력을 조회합니다.")}>
        <FormField label="파이프라인 유형"><SelectBox options={["전체", "데이터 적재", "Feature 생성", "학습", "예측", "모니터링"]} /></FormField>
        <FormField label="실행 상태"><SelectBox options={["전체", "대기", "실행중", "성공", "실패"]} /></FormField>
        <FormField label="기간"><TextInput placeholder="2026-06-24" /></FormField>
        <FormField label="실행ID"><TextInput placeholder="RUN- 검색" /></FormField>
      </SearchPanel>
      <div className="bg-white border border-slate-200 rounded-lg overflow-hidden">
        <div className="flex items-center justify-between px-4 py-3 border-b border-slate-100">
          <div className="flex items-center gap-3">
            <span className="text-sm font-medium text-slate-700">총 {rows.length}건</span>
            <button
              onClick={() => setFiltered(!filtered)}
              className={`text-xs px-2 py-1 rounded border transition-colors ${filtered ? "bg-red-50 border-red-300 text-red-700" : "bg-white border-slate-300 text-slate-600 hover:bg-slate-50"}`}
            >
              <Filter size={11} className="inline mr-1" />실패만 보기
            </button>
          </div>
          <SecondaryBtn><Download size={13} /> 다운로드</SecondaryBtn>
        </div>
        <Table
          headers={["실행ID", "파이프라인명", "유형", "상태", "시작시각", "종료시각", "소요시간", "작업"]}
          rows={rows.map((r) => [
            <span key="id" className="font-mono text-xs text-slate-500">{r.id}</span>,
            <span key="name" className="font-mono text-xs">{r.name}</span>,
            r.type,
            <StatusBadge key="s" status={r.status} />,
            <span key="st" className="font-mono text-xs">{r.start}</span>,
            <span key="et" className="font-mono text-xs">{r.end}</span>,
            <span key="dur" className="font-mono text-xs">{r.duration}</span>,
            <div key="a" className="flex gap-1">
              <GhostBtn onClick={() => openModal("MOD-009")}><Eye size={12} /> 상세</GhostBtn>
              <GhostBtn onClick={() => addToast("info", "로그 패널을 표시합니다.")}><FileText size={12} /> 로그</GhostBtn>
              <GhostBtn onClick={() => addToast("success", "재실행을 요청합니다.")}><RefreshCw size={12} /> 재실행</GhostBtn>
            </div>,
          ])}
        />
      </div>
    </div>
  );
}

function SCR016({ navigate, openModal, addToast }: AppActions) {
  return (
    <div>
      <PageHeader breadcrumb={["운영 관리", "성능 모니터링"]} title="성능 모니터링" sub="운영 모델의 예측 성능 추이를 모니터링합니다." />
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-4">
        <MetricCard label="MAE" value="12.4" color="text-emerald-600" icon={<TrendingDown size={16} />} />
        <MetricCard label="RMSE" value="18.7" color="text-slate-700" />
        <MetricCard label="MAPE" value="4.8" unit="%" color="text-emerald-600" icon={<TrendingDown size={16} />} />
        <MetricCard label="성능 저하" value="없음" color="text-emerald-600" sub="임계치: MAPE 6.0%" />
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-4">
        <div className="bg-white border border-slate-200 rounded-lg p-4">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-semibold text-slate-700">MAPE 추이 (최근 7일)</h3>
            <GhostBtn onClick={() => navigate("SCR-017")}>드리프트 리포트 <ChevronRight size={12} /></GhostBtn>
          </div>
          <ResponsiveContainer width="100%" height={200}>
            <AreaChart data={perfTrend}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
              <XAxis dataKey="date" tick={{ fontSize: 11 }} />
              <YAxis tick={{ fontSize: 11 }} unit="%" domain={[3, 7]} />
              <Tooltip formatter={(v) => [`${v}%`, "MAPE"]} />
              <Area type="monotone" dataKey="mape" stroke="#3b82f6" fill="#eff6ff" strokeWidth={2} />
            </AreaChart>
          </ResponsiveContainer>
        </div>
        <div className="bg-white border border-slate-200 rounded-lg p-4">
          <h3 className="text-sm font-semibold text-slate-700 mb-3">Champion vs Candidate</h3>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={[
              { date: "06-20", LGBM: 4.9, XGB: 5.8 },
              { date: "06-21", LGBM: 4.7, XGB: 5.5 },
              { date: "06-22", LGBM: 4.5, XGB: 5.6 },
              { date: "06-23", LGBM: 4.8, XGB: 5.9 },
              { date: "06-24", LGBM: 4.6, XGB: 5.7 },
            ]}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
              <XAxis dataKey="date" tick={{ fontSize: 11 }} />
              <YAxis tick={{ fontSize: 11 }} unit="%" />
              <Tooltip />
              <Legend wrapperStyle={{ fontSize: 11 }} />
              <Bar dataKey="LGBM" fill="#3b82f6" radius={[2, 2, 0, 0]} />
              <Bar dataKey="XGB" fill="#8b5cf6" radius={[2, 2, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>
      <div className="bg-white border border-slate-200 rounded-lg overflow-hidden">
        <div className="px-4 py-2.5 border-b border-slate-100 bg-slate-50 flex items-center justify-between">
          <span className="text-xs font-semibold text-slate-600 uppercase tracking-wide">알림 목록</span>
          <div className="flex gap-2">
            <GhostBtn onClick={() => openModal("MOD-004")}><AlertTriangle size={12} /> 재학습 후보 등록</GhostBtn>
            <SecondaryBtn><Download size={13} /> 리포트 다운로드</SecondaryBtn>
          </div>
        </div>
        <Table
          headers={["유형", "내용", "발생시각", "상태"]}
          rows={[
            ["드리프트 감지", "temperature Feature 분포 이상 (Score: 0.412)", "2026-06-24 04:00", "DRIFT_DETECTED"],
            ["성능 저하 경고", "강남지사 MAPE 6.2% (임계치 초과)", "2026-06-24 06:00", "WARNING"],
            ["재학습 후보", "MAPE 임계치 초과 — heat-demand-lgbm v12", "2026-06-24 07:00", "RETRAIN_REQUIRED"],
          ].map((r) => [r[0], <span key="c" className="text-xs">{r[1]}</span>, <span key="t" className="font-mono text-xs">{r[2]}</span>, <StatusBadge key="s" status={r[3]} />])}
        />
      </div>
    </div>
  );
}

function SCR017({ openModal, addToast }: AppActions) {
  return (
    <div>
      <PageHeader breadcrumb={["운영 관리", "드리프트 리포트"]} title="드리프트 리포트" sub="최근 입력 데이터와 학습 기준 데이터의 분포 차이를 점검합니다." />
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 mb-4">
        <MetricCard label="드리프트 감지 Feature" value="2" unit="개" color="text-amber-600" icon={<AlertTriangle size={16} />} />
        <MetricCard label="전체 Feature 수" value="12" unit="개" />
        <MetricCard label="위험도" value="중간" color="text-amber-600" sub="기준 Score > 0.3" />
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-4">
        <div className="bg-white border border-slate-200 rounded-lg overflow-hidden">
          <div className="px-4 py-2.5 border-b border-slate-100 bg-slate-50 flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-600 uppercase tracking-wide">Feature별 Drift Score</span>
          </div>
          <Table
            headers={["Feature 명", "Drift Score", "상태"]}
            rows={driftScores.map((d) => [
              <span key="name" className="font-mono text-xs text-blue-700">{d.feature}</span>,
              <span key="score" className={`font-mono text-xs font-bold ${d.score > 0.3 ? "text-red-600" : "text-slate-600"}`}>{d.score.toFixed(3)}</span>,
              <StatusBadge key="s" status={d.status} />,
            ])}
          />
        </div>
        <div className="bg-white border border-slate-200 rounded-lg p-4">
          <h3 className="text-sm font-semibold text-slate-700 mb-3">기준분포 vs 최근분포 (temperature)</h3>
          <ResponsiveContainer width="100%" height={180}>
            <AreaChart data={[
              { x: "0°C", base: 2, recent: 0 }, { x: "5°C", base: 8, recent: 2 },
              { x: "10°C", base: 18, recent: 8 }, { x: "15°C", base: 28, recent: 15 },
              { x: "20°C", base: 22, recent: 28 }, { x: "25°C", base: 12, recent: 32 },
              { x: "30°C", base: 7, recent: 12 }, { x: "35°C", base: 3, recent: 3 },
            ]}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
              <XAxis dataKey="x" tick={{ fontSize: 10 }} />
              <YAxis tick={{ fontSize: 10 }} />
              <Tooltip />
              <Legend wrapperStyle={{ fontSize: 10 }} />
              <Area type="monotone" dataKey="base" stroke="#3b82f6" fill="#eff6ff" fillOpacity={0.6} strokeWidth={1.5} name="기준분포" />
              <Area type="monotone" dataKey="recent" stroke="#f59e0b" fill="#fffbeb" fillOpacity={0.6} strokeWidth={1.5} name="최근분포" />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </div>
      <div className="flex gap-2">
        <PrimaryBtn onClick={() => addToast("success", "드리프트 리포트를 생성합니다.")} icon={<Play size={13} />}>리포트 생성</PrimaryBtn>
        <SecondaryBtn onClick={() => openModal("MOD-004")}><AlertTriangle size={13} /> 재학습 요청</SecondaryBtn>
        <SecondaryBtn><Download size={13} /> 다운로드</SecondaryBtn>
      </div>
    </div>
  );
}

function SCR018({ openModal, addToast }: AppActions) {
  const [candidates, setCandidates] = useState(retrainingCandidates);
  return (
    <div>
      <PageHeader breadcrumb={["운영 관리", "재학습 후보 관리"]} title="재학습 후보 관리" sub="성능 저하, 드리프트 감지, 운영자 판단으로 발생한 재학습 후보를 관리합니다." />
      <div className="bg-white border border-slate-200 rounded-lg overflow-hidden">
        <div className="flex items-center justify-between px-4 py-3 border-b border-slate-100">
          <span className="text-sm font-medium text-slate-700">총 {candidates.length}건</span>
        </div>
        <Table
          headers={["후보ID", "발생 사유", "모델명/버전", "지사/권역", "위험도", "상태", "생성일", "작업"]}
          rows={candidates.map((r, i) => [
            <span key="id" className="font-mono text-xs text-slate-500">{r.id}</span>,
            <span key="reason" className="text-xs">{r.reason}</span>,
            <span key="model" className="font-mono text-xs">{r.model}</span>,
            r.site,
            <span key="risk" className={`text-xs font-bold ${r.risk === "높음" ? "text-red-600" : "text-amber-600"}`}>{r.risk}</span>,
            <StatusBadge key="s" status={r.status} />,
            <span key="date" className="font-mono text-xs">{r.created}</span>,
            <div key="a" className="flex gap-1">
              <GhostBtn><Eye size={12} /> 상세</GhostBtn>
              {r.status === "검토중" && (
                <>
                  <GhostBtn onClick={() => openModal("MOD-004")}><Play size={12} /> 재학습 요청</GhostBtn>
                  <GhostBtn onClick={() => {
                    const next = [...candidates];
                    next[i] = { ...next[i], status: "보류" };
                    setCandidates(next);
                    addToast("info", "보류 처리되었습니다.");
                  }}><Pause size={12} /> 보류</GhostBtn>
                </>
              )}
              <GhostBtn onClick={() => openModal("MOD-005")}><Trash2 size={12} className="text-red-500" /> 제외</GhostBtn>
            </div>,
          ])}
        />
      </div>
    </div>
  );
}

// ─── Modal Contents ───────────────────────────────────────────────────────────

interface AppActions {
  navigate: (s: Screen) => void;
  openModal: (m: Modal) => void;
  closeModal: () => void;
  addToast: (type: ToastType, message: string) => void;
}

function Modals({ modal, actions }: { modal: Modal; actions: AppActions }) {
  const { closeModal, navigate, addToast } = actions;
  if (!modal) return null;

  const confirm = (msg: string, screen?: Screen) => {
    closeModal();
    addToast("success", msg);
    if (screen) setTimeout(() => navigate(screen), 300);
  };

  if (modal === "MOD-001") return (
    <ModalShell title="모델 학습을 실행하시겠습니까?" onClose={closeModal}
      footer={<><PrimaryBtn onClick={() => confirm("학습 실행을 요청했습니다.", "SCR-015")} icon={<Play size={13} />}>실행</PrimaryBtn><SecondaryBtn onClick={closeModal}>취소</SecondaryBtn></>}>
      <div className="text-sm text-slate-600 flex flex-col gap-2">
        {[["학습 설정명", "시간별_LGBM_기본설정"], ["학습 대상", "전체 지사"], ["학습 기간", "최근 2년"], ["알고리즘", "LightGBM"], ["Feature Set", "기본_시간별_열수요_v1"], ["Registry 등록 여부", "학습 후 자동 등록"]].map(([k, v]) => (
          <div key={k} className="flex gap-2"><span className="w-36 text-slate-400 shrink-0">{k}</span><span className="font-medium text-slate-800">{v}</span></div>
        ))}
      </div>
    </ModalShell>
  );

  if (modal === "MOD-002") return (
    <ModalShell title="배치 예측을 실행하시겠습니까?" onClose={closeModal}
      footer={<><PrimaryBtn onClick={() => confirm("예측 실행을 요청했습니다.", "SCR-015")} icon={<Play size={13} />}>실행</PrimaryBtn><SecondaryBtn onClick={closeModal}>취소</SecondaryBtn></>}>
      <div className="text-sm text-slate-600 flex flex-col gap-2">
        {[["예측 대상", "전체 지사"], ["예측 기간", "D+1"], ["모델 버전", "heat-demand-lgbm v12 (Champion)"], ["실행 방식", "즉시 실행"]].map(([k, v]) => (
          <div key={k} className="flex gap-2"><span className="w-28 text-slate-400 shrink-0">{k}</span><span className="font-medium text-slate-800">{v}</span></div>
        ))}
      </div>
    </ModalShell>
  );

  if (modal === "MOD-003") return (
    <ModalShell title="Champion 모델로 지정하시겠습니까?" onClose={closeModal}
      footer={<><PrimaryBtn onClick={() => confirm("Champion 모델로 지정되었습니다.")} icon={<Star size={13} />}>지정</PrimaryBtn><SecondaryBtn onClick={closeModal}>취소</SecondaryBtn></>}>
      <div className="grid grid-cols-2 gap-4 text-sm">
        <div className="bg-slate-50 rounded-lg p-3">
          <div className="text-xs text-slate-400 mb-1">현재 Champion</div>
          <div className="font-semibold">heat-demand-lgbm v12</div>
          <div className="font-mono text-emerald-600 text-sm mt-1">MAPE 4.8%</div>
        </div>
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-3">
          <div className="text-xs text-blue-500 mb-1">신규 Champion 후보</div>
          <div className="font-semibold">heat-demand-lgbm v13</div>
          <div className="font-mono text-blue-700 text-sm mt-1">MAPE 4.5%</div>
        </div>
      </div>
    </ModalShell>
  );

  if (modal === "MOD-004") return (
    <ModalShell title="재학습을 요청하시겠습니까?" onClose={closeModal}
      footer={<><PrimaryBtn onClick={() => confirm("재학습 요청이 완료되었습니다.")} icon={<Play size={13} />}>요청</PrimaryBtn><SecondaryBtn onClick={closeModal}>취소</SecondaryBtn></>}>
      <div className="text-sm text-slate-600 flex flex-col gap-2">
        {[["발생 사유", "MAPE 임계치 초과 (6.2%)"], ["대상 모델", "heat-demand-lgbm v12"], ["대상 기간", "2026-06-18 ~ 2026-06-24"], ["권장 조치", "학습 데이터 확장 후 재학습"]].map(([k, v]) => (
          <div key={k} className="flex gap-2"><span className="w-28 text-slate-400 shrink-0">{k}</span><span className="font-medium text-slate-800">{v}</span></div>
        ))}
      </div>
    </ModalShell>
  );

  if (modal === "MOD-005") return (
    <ModalShell title="삭제하시겠습니까?" onClose={closeModal}
      footer={<><DangerBtn onClick={() => confirm("삭제가 완료되었습니다.")}><Trash2 size={13} /> 삭제</DangerBtn><SecondaryBtn onClick={closeModal}>취소</SecondaryBtn></>}>
      <div className="flex items-start gap-3">
        <AlertTriangle size={20} className="text-red-500 mt-0.5 shrink-0" />
        <div className="text-sm text-slate-600">
          <p className="font-medium text-slate-800 mb-1">선택한 항목을 삭제합니다.</p>
          <p className="text-red-600 text-xs">삭제 후 복구가 불가능합니다. 신중하게 확인하세요.</p>
        </div>
      </div>
    </ModalShell>
  );

  if (modal === "MOD-006") return (
    <ModalShell title="데이터 소스 연결 테스트 결과" onClose={closeModal}
      footer={<SecondaryBtn onClick={closeModal}>닫기</SecondaryBtn>}>
      <div className="flex flex-col gap-3 text-sm">
        <div className="flex items-center gap-2"><CheckCircle size={16} className="text-emerald-600" /><span className="font-medium text-emerald-800">연결 성공</span></div>
        <div className="bg-slate-50 rounded-lg p-3 font-mono text-xs flex flex-col gap-1.5">
          <div className="flex justify-between"><span className="text-slate-500">응답 시간</span><span>128ms</span></div>
          <div className="flex justify-between"><span className="text-slate-500">샘플 데이터 수</span><span>24건</span></div>
          <div className="flex justify-between"><span className="text-slate-500">호스트</span><span>db-prod.thermops.internal:5432</span></div>
          <div className="flex justify-between"><span className="text-slate-500">DB명</span><span>thermops_prod</span></div>
        </div>
      </div>
    </ModalShell>
  );

  if (modal === "MOD-007") return (
    <ModalShell title="Feature Set 선택" onClose={closeModal}
      footer={<><PrimaryBtn onClick={() => { closeModal(); addToast("success", "Feature Set이 선택되었습니다."); }}>선택</PrimaryBtn><SecondaryBtn onClick={closeModal}>취소</SecondaryBtn></>}>
      <div className="flex flex-col gap-2">
        {["기본_시간별_열수요_v1", "기상_강화_Feature_v2", "경량_예측_v1"].map((name, i) => (
          <label key={name} className="flex items-start gap-3 p-3 border border-slate-200 rounded-lg cursor-pointer hover:bg-blue-50 hover:border-blue-300 transition-colors">
            <input type="radio" name="featureset" defaultChecked={i === 0} className="mt-0.5 accent-blue-600" />
            <div>
              <div className="text-sm font-medium text-slate-800">{name}</div>
              <div className="text-xs text-slate-400 mt-0.5">{["12개 Feature • 최근 사용", "16개 Feature", "8개 Feature"][i]}</div>
            </div>
          </label>
        ))}
      </div>
    </ModalShell>
  );

  if (modal === "MOD-008") return (
    <ModalShell title="모델 상세 정보" onClose={closeModal}
      footer={<><SecondaryBtn onClick={() => { closeModal(); actions.navigate("SCR-011"); }}>Registry 보기</SecondaryBtn><SecondaryBtn onClick={closeModal}>닫기</SecondaryBtn></>}>
      <div className="text-sm text-slate-600 flex flex-col gap-2">
        {[["모델명", "heat-demand-lgbm"], ["버전", "v12"], ["알고리즘", "LightGBM"], ["MAE", "12.4"], ["RMSE", "18.7"], ["MAPE", "4.8%"], ["Feature Set", "기본_시간별_열수요_v1"], ["학습 실행ID", "TRN-20260620-001"], ["등록일", "2026-06-20"]].map(([k, v]) => (
          <div key={k} className="flex gap-2 py-1 border-b border-slate-100 last:border-0">
            <span className="w-28 text-slate-400 shrink-0">{k}</span>
            <span className="font-medium text-slate-800 font-mono text-xs">{v}</span>
          </div>
        ))}
      </div>
    </ModalShell>
  );

  if (modal === "MOD-009") return (
    <ModalShell title="파이프라인 실행 상세" onClose={closeModal}
      footer={<><SecondaryBtn onClick={() => addToast("success", "로그를 다운로드합니다.")}><Download size={13} /> 로그 다운로드</SecondaryBtn><SecondaryBtn onClick={closeModal}>닫기</SecondaryBtn></>}>
      <div className="flex flex-col gap-3 text-sm">
        <div className="flex flex-col gap-1.5 text-sm bg-slate-50 rounded-lg p-3">
          {[["실행ID", "RUN-20260624-001"], ["DAG명", "daily_prediction_dag"], ["시작시각", "2026-06-24 02:00:00"], ["종료시각", "2026-06-24 02:15:22"]].map(([k, v]) => (
            <div key={k} className="flex gap-2"><span className="w-24 text-slate-400 shrink-0">{k}</span><span className="font-mono text-xs">{v}</span></div>
          ))}
        </div>
        <div>
          <div className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-2">Task 실행 현황</div>
          {[["data_load_task", "SUCCESS", "02:00"], ["feature_gen_task", "SUCCESS", "02:04"], ["predict_task", "SUCCESS", "02:10"], ["output_write_task", "SUCCESS", "02:14"]].map(([task, status, t]) => (
            <div key={task as string} className="flex items-center justify-between py-1.5 border-b border-slate-100 last:border-0">
              <span className="font-mono text-xs text-slate-600">{task as string}</span>
              <div className="flex items-center gap-3">
                <span className="font-mono text-xs text-slate-400">{t as string}</span>
                <StatusBadge status={status as string} />
              </div>
            </div>
          ))}
        </div>
      </div>
    </ModalShell>
  );

  if (modal === "MOD-010") return (
    <ModalShell title="권한이 없습니다" onClose={closeModal}
      footer={<PrimaryBtn onClick={closeModal}>확인</PrimaryBtn>}>
      <div className="flex items-start gap-3">
        <XCircle size={20} className="text-red-500 mt-0.5 shrink-0" />
        <div className="text-sm text-slate-600">
          <p className="font-medium text-slate-800 mb-1">해당 기능을 실행할 권한이 없습니다.</p>
          <p className="text-slate-500 text-xs">관리자(시스템 담당자)에게 권한을 요청하세요.</p>
        </div>
      </div>
    </ModalShell>
  );

  return null;
}

// ─── Header ───────────────────────────────────────────────────────────────────

function Header({ notifCount, openModal }: { notifCount: number; openModal: (m: Modal) => void }) {
  return (
    <div className="h-12 bg-[#0f172a] border-b border-white/10 flex items-center justify-between px-4 shrink-0 z-10">
      <div className="flex items-center gap-3">
        <div className="flex items-center gap-2">
          <div className="w-6 h-6 bg-blue-500 rounded flex items-center justify-center">
            <Zap size={13} className="text-white" />
          </div>
          <span className="text-white font-bold text-sm tracking-tight">THERMOps</span>
        </div>
        <span className="text-slate-500 text-xs hidden lg:block">열수요 예측 모델 운영 자동화 플랫폼</span>
        <span className="text-xs px-1.5 py-0.5 bg-amber-500/20 text-amber-400 rounded font-mono font-medium">DEV</span>
      </div>
      <div className="flex items-center gap-3">
        <button className="relative text-slate-400 hover:text-white transition-colors">
          <Bell size={16} />
          {notifCount > 0 && (
            <span className="absolute -top-1 -right-1 w-3.5 h-3.5 bg-red-500 rounded-full flex items-center justify-center text-[9px] text-white font-bold">{notifCount}</span>
          )}
        </button>
        <div className="flex items-center gap-2 cursor-pointer group">
          <div className="w-6 h-6 rounded-full bg-blue-600 flex items-center justify-center text-white text-xs font-bold">홍</div>
          <div className="hidden lg:block">
            <div className="text-white text-xs font-medium">관리자 홍길동</div>
          </div>
          <span className="text-xs px-1.5 py-0.5 bg-blue-600/30 text-blue-300 rounded font-mono">ADMIN</span>
        </div>
        <button className="text-slate-400 hover:text-white transition-colors"><LogOut size={14} /></button>
      </div>
    </div>
  );
}

// ─── Sidebar ──────────────────────────────────────────────────────────────────

function Sidebar({ current, navigate }: { current: Screen; navigate: (s: Screen) => void }) {
  const [open, setOpen] = useState<Record<string, boolean>>({
    "대시보드": true, "데이터 관리": false, "Feature 관리": false,
    "모델 관리": true, "예측 관리": false, "운영 관리": true,
  });

  return (
    <div className="w-56 bg-[#0f172a] border-r border-white/6 flex flex-col shrink-0 overflow-y-auto">
      <nav className="flex-1 py-3">
        {MENU.map((group) => {
          const isOpen = open[group.label];
          const hasActive = group.children.some((c) => c.screen === current);
          return (
            <div key={group.label} className="mb-0.5">
              <button
                onClick={() => setOpen((p) => ({ ...p, [group.label]: !p[group.label] }))}
                className={`w-full flex items-center justify-between px-3 py-2 text-xs font-semibold uppercase tracking-wider transition-colors ${hasActive ? "text-blue-400" : "text-slate-400 hover:text-slate-200"}`}
              >
                <span className="flex items-center gap-2">{group.icon}{group.label}</span>
                {isOpen ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
              </button>
              {isOpen && (
                <div className="ml-2">
                  {group.children.map((child) => {
                    const active = child.screen === current;
                    return (
                      <button
                        key={child.screen}
                        onClick={() => navigate(child.screen)}
                        className={`w-full text-left px-3 py-1.5 text-xs rounded-md transition-colors flex items-center gap-1.5 ${active ? "bg-blue-600/20 text-blue-300 font-medium" : "text-slate-400 hover:text-slate-200 hover:bg-white/5"}`}
                      >
                        {active && <div className="w-1 h-1 bg-blue-400 rounded-full shrink-0" />}
                        {child.label}
                      </button>
                    );
                  })}
                </div>
              )}
            </div>
          );
        })}
      </nav>
      <div className="px-3 py-3 border-t border-white/6 text-xs text-slate-500 font-mono">
        v2.4.1 • 2026-06-24
      </div>
    </div>
  );
}

// ─── Main App ─────────────────────────────────────────────────────────────────

export default function App() {
  const [current, setCurrent] = useState<Screen>("SCR-001");
  const [modal, setModal] = useState<Modal>(null);
  const [toasts, setToasts] = useState<Toast[]>([]);
  const toastIdRef = useRef(0);

  const navigate = useCallback((s: Screen) => setCurrent(s), []);
  const openModal = useCallback((m: Modal) => setModal(m), []);
  const closeModal = useCallback(() => setModal(null), []);
  const addToast = useCallback((type: ToastType, message: string) => {
    const id = ++toastIdRef.current;
    setToasts((p) => [...p, { id, type, message }]);
    setTimeout(() => setToasts((p) => p.filter((t) => t.id !== id)), 3500);
  }, []);
  const removeToast = useCallback((id: number) => setToasts((p) => p.filter((t) => t.id !== id)), []);

  const actions: AppActions = { navigate, openModal, closeModal, addToast };

  const screenMap: Record<Screen, React.ReactNode> = {
    "SCR-001": <SCR001 {...actions} />,
    "SCR-002": <SCR002 {...actions} />,
    "SCR-003": <SCR003 {...actions} />,
    "SCR-004": <SCR004 {...actions} />,
    "SCR-005": <SCR005 {...actions} />,
    "SCR-006": <SCR006 {...actions} />,
    "SCR-007": <SCR007 {...actions} />,
    "SCR-008": <SCR008 {...actions} />,
    "SCR-009": <SCR009 {...actions} />,
    "SCR-010": <SCR010 {...actions} />,
    "SCR-011": <SCR011 {...actions} />,
    "SCR-012": <SCR012 {...actions} />,
    "SCR-013": <SCR013 {...actions} />,
    "SCR-014": <SCR014 {...actions} />,
    "SCR-015": <SCR015 {...actions} />,
    "SCR-016": <SCR016 {...actions} />,
    "SCR-017": <SCR017 {...actions} />,
    "SCR-018": <SCR018 {...actions} />,
  };

  return (
    <div className="h-screen flex flex-col bg-background overflow-hidden" style={{ fontFamily: "Inter, ui-sans-serif, system-ui, sans-serif" }}>
      <Header notifCount={3} openModal={openModal} />
      <div className="flex flex-1 overflow-hidden">
        <Sidebar current={current} navigate={navigate} />
        <main className="flex-1 overflow-y-auto p-5 bg-slate-100">
          <div className="max-w-6xl">
            {screenMap[current]}
          </div>
        </main>
      </div>
      <Modals modal={modal} actions={actions} />
      <ToastContainer toasts={toasts} onRemove={removeToast} />
    </div>
  );
}
