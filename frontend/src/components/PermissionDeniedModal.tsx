import { ShieldAlert } from "lucide-react";
import { Modal } from "./Modal";
import { Button } from "./Button";

interface PermissionDeniedModalProps {
  open: boolean;
  onClose: () => void;
  message?: string;
}

export function PermissionDeniedModal({
  open,
  onClose,
  message = "현재 권한(VIEWER)으로는 이 작업을 수행할 수 없습니다. 관리자에게 권한을 요청하세요.",
}: PermissionDeniedModalProps) {
  return (
    <Modal
      open={open}
      title="권한 없음"
      onClose={onClose}
      footer={<Button variant="secondary" onClick={onClose}>확인</Button>}
    >
      <div className="flex items-start gap-3">
        <ShieldAlert className="w-8 h-8 text-amber-500 shrink-0" />
        <p className="text-sm text-slate-600">{message}</p>
      </div>
    </Modal>
  );
}
