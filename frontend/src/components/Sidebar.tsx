import { NavLink } from "react-router-dom";
import {
  LayoutDashboard, Database, GitBranch, ShieldCheck, Layers, Box,
  Settings, Play, BarChart2, Award, Zap, LineChart, AlertTriangle,
  Activity, FileText, RefreshCw, ChevronDown, ChevronRight,
} from "lucide-react";
import { useState } from "react";

const MENU = [
  { label: "대시보드", path: "/dashboard", icon: LayoutDashboard },
  {
    label: "데이터 관리", icon: Database, children: [
      { label: "데이터 소스 관리", path: "/data/sources" },
      { label: "데이터 매핑 설정", path: "/data/mappings" },
      { label: "데이터 품질 점검", path: "/data/quality" },
    ],
  },
  {
    label: "Feature 관리", icon: Layers, children: [
      { label: "Feature 목록", path: "/features" },
      { label: "Feature Recipe", path: "/feature-recipes" },
      { label: "Feature Set 관리", path: "/feature-sets" },
    ],
  },
  {
    label: "모델 관리", icon: Box, children: [
      { label: "모델 학습 설정", path: "/models/training-configs" },
      { label: "모델 학습 실행", path: "/models/training-jobs" },
      { label: "모델 성능 비교", path: "/models/performance" },
      { label: "모델 Registry 관리", path: "/models/registry" },
    ],
  },
  {
    label: "예측 관리", icon: Zap, children: [
      { label: "배치 예측 실행", path: "/predictions/jobs" },
      { label: "예측 결과 조회", path: "/predictions/results" },
      { label: "실제값 매칭 및 오차 분석", path: "/predictions/errors" },
    ],
  },
  {
    label: "운영 관리", icon: Activity, children: [
      { label: "파이프라인 실행 이력", path: "/ops/pipeline-runs" },
      { label: "성능 모니터링", path: "/ops/model-monitoring" },
      { label: "드리프트 리포트", path: "/ops/drift-reports" },
      { label: "재학습 후보 관리", path: "/ops/retraining-candidates" },
      { label: "공통 코드/설정", path: "/system/configs" },
    ],
  },
];

export function Sidebar() {
  const [open, setOpen] = useState<Record<string, boolean>>({ "데이터 관리": true, "모델 관리": true });

  return (
    <aside className="w-60 bg-sidebar text-sidebar-foreground flex flex-col shrink-0 min-h-screen">
      <div className="px-4 py-5 border-b border-white/10">
        <div className="text-lg font-bold text-white">THERMOps</div>
        <div className="text-xs text-slate-400 mt-0.5">열수요 예측 MLOps</div>
      </div>
      <nav className="flex-1 py-3 overflow-y-auto">
        {MENU.map((item) => {
          if (!item.children) {
            const Icon = item.icon!;
            return (
              <NavLink key={item.path} to={item.path!} className={({ isActive }) =>
                `flex items-center gap-2 px-4 py-2 text-sm ${isActive ? "bg-sidebar-accent text-white" : "text-slate-400 hover:text-white hover:bg-sidebar-accent/50"}`
              }>
                <Icon className="w-4 h-4" />{item.label}
              </NavLink>
            );
          }
          const Icon = item.icon;
          const isOpen = open[item.label];
          return (
            <div key={item.label}>
              <button onClick={() => setOpen((o) => ({ ...o, [item.label]: !o[item.label] }))}
                className="flex items-center gap-2 px-4 py-2 w-full text-sm text-slate-400 hover:text-white">
                <Icon className="w-4 h-4" />
                <span className="flex-1 text-left">{item.label}</span>
                {isOpen ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
              </button>
              {isOpen && item.children.map((c) => (
                <NavLink key={c.path} to={c.path} className={({ isActive }) =>
                  `block pl-10 pr-4 py-1.5 text-xs ${isActive ? "text-blue-400 bg-sidebar-accent/50" : "text-slate-500 hover:text-slate-300"}`
                }>{c.label}</NavLink>
              ))}
            </div>
          );
        })}
      </nav>
    </aside>
  );
}
