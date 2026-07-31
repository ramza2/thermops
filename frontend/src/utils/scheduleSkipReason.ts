/** R11-S8-9-18 / B9 — schedule skip reason → operator-facing copy.
 * R11-S8-9-19 / B4 — next-check guidance per reason (FE-only).
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

const NEXT_CHECKS: Record<string, string[]> = {
  [SCHEDULE_SKIP_REASON_ACTIVE_RUN]: [
    "이전 실행이 아직 진행 중일 수 있습니다.",
    "Run History에서 해당 RUNNING 실행이 정상 진행 중인지 확인하세요.",
    "장시간 RUNNING이면 조치 필요 카드 또는 Run Detail에서 soft-cancel 가능 여부를 검토하세요.",
  ],
  [SCHEDULE_SKIP_REASON_DUPLICATE]: [
    "같은 scheduled_at 실행이 이미 존재할 수 있습니다.",
    "중복 실행을 피하기 위한 skip일 수 있습니다.",
    "Run History에서 동일 scheduled_at run이 있는지 확인하세요.",
  ],
  [SCHEDULE_SKIP_REASON_STALE]: [
    "스케줄 설정 또는 compile 상태가 유효하지 않을 수 있습니다.",
    "Studio에서 Graph 검증과 Compile 상태를 확인한 뒤 실행 설정을 다시 반영하세요.",
  ],
};

const UNKNOWN_NEXT_CHECKS: string[] = [
  "skip 사유 정보가 없습니다.",
  "Skip 이력 또는 상세 이벤트를 확인하세요.",
];

export function normalizeScheduleSkipReasonCode(code: string | null | undefined): string {
  return String(code || "").trim().toUpperCase();
}

export function describeScheduleSkipReason(code: string | null | undefined): string {
  const normalized = normalizeScheduleSkipReasonCode(code);
  if (!normalized) return UNKNOWN_MESSAGE;
  return REASON_MESSAGES[normalized] ?? "알 수 없는 skip 사유입니다. 상세 이벤트를 확인하세요.";
}

/** Operator next-check hints for a skip reason. Never implies automatic recovery. */
export function nextChecksForScheduleSkipReason(code: string | null | undefined): string[] {
  const normalized = normalizeScheduleSkipReasonCode(code);
  if (!normalized) return [...UNKNOWN_NEXT_CHECKS];
  return NEXT_CHECKS[normalized] ? [...NEXT_CHECKS[normalized]] : [...UNKNOWN_NEXT_CHECKS];
}
