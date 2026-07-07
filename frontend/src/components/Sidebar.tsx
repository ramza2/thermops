import { NavLink } from "react-router-dom";
import {
  LayoutDashboard, Database, Layers, Box, Activity, Settings,
  ChevronDown, ChevronRight,
} from "lucide-react";
import { useState } from "react";
import { APP_TAGLINE, MENU_GROUPS } from "@/constants/displayLabels";

const MENU = [
  { label: "대시보드", path: "/dashboard", icon: LayoutDashboard },
  {
    label: MENU_GROUPS.dataPrep, icon: Database, children: [
      { label: "표준 데이터셋", path: "/standard-datasets" },
      { label: "데이터 소스", path: "/data/sources" },
      { label: "예측 대상", path: "/prediction-entities" },
      { label: "외부 코드 매핑", path: "/external-code-mappings" },
      { label: "데이터 매핑", path: "/data/mappings" },
      { label: "데이터 품질", path: "/data/quality" },
    ],
  },
  {
    label: MENU_GROUPS.features, icon: Layers, children: [
      { label: "학습 변수", path: "/features" },
      { label: "변수 생성 규칙", path: "/feature-recipes" },
      { label: "변수 구성", path: "/feature-sets" },
      { label: "학습 데이터 버전", path: "/dataset-versions" },
    ],
  },
  {
    label: MENU_GROUPS.modelPredict, icon: Box, children: [
      { label: "학습 설정", path: "/models/training-configs" },
      { label: "모델 학습", path: "/models/training-jobs" },
      { label: "모델 성능 비교", path: "/models/performance" },
      { label: "모델 등록 목록", path: "/models/registry" },
      { label: "예측 작업", path: "/predictions/jobs" },
      { label: "예측 결과", path: "/predictions/results" },
      { label: "예측 오차 분석", path: "/predictions/errors" },
    ],
  },
  {
    label: MENU_GROUPS.operations, icon: Activity, children: [
      { label: "작업 흐름 구성", path: "/pipeline-builder" },
      { label: "작업 실행 이력", path: "/ops/pipeline-runs" },
      { label: "성능 모니터링", path: "/ops/model-monitoring" },
      { label: "데이터 변화 리포트", path: "/ops/drift-reports" },
      { label: "재학습 후보", path: "/ops/retraining-candidates" },
      { label: "데이터 적재 일정", path: "/data-load-schedules" },
    ],
  },
  {
    label: MENU_GROUPS.system, icon: Settings, children: [
      { label: "시스템 설정", path: "/system/configs" },
    ],
  },
];

export function Sidebar() {
  const [open, setOpen] = useState<Record<string, boolean>>({
    [MENU_GROUPS.dataPrep]: true,
    [MENU_GROUPS.modelPredict]: true,
  });

  return (
    <aside className="w-60 bg-sidebar text-sidebar-foreground flex flex-col shrink-0 min-h-screen">
      <div className="px-4 py-5 border-b border-white/10">
        <div className="text-lg font-bold text-white">THERMOps</div>
        <div className="text-xs text-slate-400 mt-0.5">{APP_TAGLINE}</div>
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
