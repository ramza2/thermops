/** R11-S8-9-18 / B9 — schedule skip reason → operator-facing copy.
 *
 * Codes align with backend schedule_worker_service skip constants.
 * Does not enqueue catch-up / retry / cancel.
 */

export const SCHEDULE_SKIP_REASON_ACTIVE_RUN = "ACTIVE_RUN_EXISTS";
export const SCHEDULE_SKIP_REASON_STALE = "STALE_OR_INVALID";
export const SCHEDULE_SKIP_REASON_DUPLICATE = "DUPLICATE_DEDUP_KEY";

const REASON_MESSAGES: Record<string, string> = {
  [SCHEDULE_SKIP_REASON_ACTIVE_RUN]:
    "이전 실행이 아직 진행 중이어서 이번 스케줄 실행을 건너뛰었습니다.",
  [SCHEDULE_SKIP_REASON_STALE]:
    "스케줄/실행 설정이 동기화되지 않았거나 유효하지 않아 실행하지 않았습니다.",
  [SCHEDULE_SKIP_REASON_DUPLICATE]:
    "동일 scheduled_at 실행이 이미 존재해 중복 생성을 건너뛰었습니다.",
};

const UNKNOWN_MESSAGE =
  "skip 사유 정보가 없습니다. 상세 이벤트를 확인하세요.";

export function normalizeScheduleSkipReasonCode(code: string | null | undefined): string {
  return String(code || "").trim().toUpperCase();
}

export function describeScheduleSkipReason(code: string | null | undefined): string {
  const normalized = normalizeScheduleSkipReasonCode(code);
  if (!normalized) return UNKNOWN_MESSAGE;
  return REASON_MESSAGES[normalized] ?? "알 수 없는 skip 사유입니다. 상세 이벤트를 확인하세요.";
}
