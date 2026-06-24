import { Bell, User } from "lucide-react";

export function Header() {
  return (
    <header className="h-14 bg-white border-b border-slate-200 flex items-center justify-between px-6 shrink-0">
      <div className="text-sm text-slate-500">한국지역난방공사 · 열수요 예측 모델 운영 자동화</div>
      <div className="flex items-center gap-4">
        <button className="relative text-slate-500 hover:text-slate-700">
          <Bell className="w-5 h-5" />
          <span className="absolute -top-1 -right-1 w-4 h-4 bg-red-500 text-white text-[10px] rounded-full flex items-center justify-center">2</span>
        </button>
        <div className="flex items-center gap-2 text-sm text-slate-700">
          <User className="w-4 h-4" />
          <span>관리자</span>
          <span className="text-xs text-slate-400">({import.meta.env.VITE_USER_ROLE || "VIEWER"})</span>
        </div>
      </div>
    </header>
  );
}
