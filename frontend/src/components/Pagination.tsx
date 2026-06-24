import { ChevronLeft, ChevronRight } from "lucide-react";
import { Button } from "./Button";

export function Pagination({ page, totalPages, onChange }: { page: number; totalPages: number; onChange: (p: number) => void }) {
  return (
    <div className="flex items-center justify-center gap-2 mt-4">
      <Button variant="secondary" disabled={page <= 1} onClick={() => onChange(page - 1)} icon={<ChevronLeft className="w-4 h-4" />} />
      <span className="text-sm text-slate-600">{page} / {totalPages || 1}</span>
      <Button variant="secondary" disabled={page >= totalPages} onClick={() => onChange(page + 1)} icon={<ChevronRight className="w-4 h-4" />} />
    </div>
  );
}

export function EmptyState({ message = "데이터가 없습니다." }: { message?: string }) {
  return <div className="flex flex-col items-center justify-center py-16 text-slate-400"><p>{message}</p></div>;
}

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-red-500 gap-3">
      <p>{message}</p>
      {onRetry && <Button variant="secondary" onClick={onRetry}>다시 시도</Button>}
    </div>
  );
}

export function LoadingState() {
  return <div className="flex items-center justify-center py-16"><div className="w-8 h-8 border-2 border-blue-600 border-t-transparent rounded-full animate-spin" /></div>;
}
