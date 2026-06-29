const STATUS_MAP: Record<string, { label: string; className: string }> = {
  READY: { label: "대기", className: "bg-slate-100 text-slate-600" },
  QUEUED: { label: "대기열", className: "bg-slate-100 text-slate-600" },
  RUNNING: { label: "실행중", className: "bg-blue-100 text-blue-700" },
  SUCCESS: { label: "성공", className: "bg-emerald-100 text-emerald-700" },
  FAILED: { label: "실패", className: "bg-red-100 text-red-700" },
  CANCELED: { label: "취소", className: "bg-slate-100 text-slate-500" },
  CHAMPION: { label: "운영중", className: "bg-emerald-100 text-emerald-700" },
  CANDIDATE: { label: "후보", className: "bg-purple-100 text-purple-700" },
  ARCHIVED: { label: "보관", className: "bg-slate-100 text-slate-500" },
  ACTIVE: { label: "사용", className: "bg-emerald-100 text-emerald-700" },
  INACTIVE: { label: "미사용", className: "bg-slate-100 text-slate-500" },
  NORMAL: { label: "정상", className: "bg-emerald-100 text-emerald-700" },
  WARNING: { label: "주의", className: "bg-amber-100 text-amber-700" },
  DRIFT: { label: "드리프트", className: "bg-red-100 text-red-700" },
  REVIEW: { label: "검토중", className: "bg-amber-100 text-amber-700" },
  REQUESTED: { label: "요청완료", className: "bg-blue-100 text-blue-700" },
  HIGH: { label: "높음", className: "bg-red-100 text-red-700" },
  MEDIUM: { label: "중간", className: "bg-amber-100 text-amber-700" },
};

export function StatusBadge({ status }: { status: string }) {
  const cfg = STATUS_MAP[status] || { label: status, className: "bg-slate-100 text-slate-600" };
  return (
    <span className={`inline-flex px-2 py-0.5 rounded text-xs font-medium ${cfg.className}`}>
      {cfg.label}
    </span>
  );
}
