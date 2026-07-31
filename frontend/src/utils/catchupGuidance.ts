/** R11-S8-9-19 / B4 — Catch-up operator guidance copy (FE-only).
 *
 * Does not enqueue catch-up, change window policy, or auto-recover.
 */

export const CATCHUP_SUMMARY =
  "Catch-up은 스케줄 시간에 실행되지 못한 누락 후보를 운영자가 확인한 뒤 보정 실행하는 기능입니다. 자동 복구가 아니며, 실행 전 대상 시간과 기존 실행 상태를 확인해야 합니다.";

export const CATCHUP_NOT_AUTO_RECOVERY = "자동 복구가 아닙니다.";

export interface CatchupTermDefinition {
  id: "missed" | "candidate" | "window" | "skip_reason";
  label: string;
  description: string;
}

/** Conceptual definitions only — window hours are server-configured and not hard-coded here. */
export const CATCHUP_TERM_DEFINITIONS: CatchupTermDefinition[] = [
  {
    id: "missed",
    label: "missed",
    description: "스케줄상 실행됐어야 하지만 실제 run이 생성되지 않은 시간입니다.",
  },
  {
    id: "candidate",
    label: "candidate",
    description: "Catch-up으로 보정 실행할 수 있는 누락 후보입니다.",
  },
  {
    id: "window",
    label: "window",
    description:
      "Catch-up 후보를 찾는 조회 범위입니다. 너무 오래된 누락은 후보에서 제외될 수 있습니다. (서버 설정에 따라 범위가 달라질 수 있습니다)",
  },
  {
    id: "skip_reason",
    label: "skip reason",
    description: "스케줄 worker가 실행 생성을 건너뛴 이유입니다.",
  },
];

/** Non-persistent operator checklist — display only, never stored. */
export const CATCHUP_PRE_RUN_CHECKLIST: string[] = [
  "대상 scheduled_at이 맞는지 확인",
  "같은 시간대 run이 이미 존재하지 않는지 확인",
  "현재 ACTIVE/RUNNING 실행이 없는지 확인",
  "target table과 conflict key 설정이 최신인지 확인",
  "실행 후 PARTIAL/FAILED가 발생하면 Run Detail 실패 요약을 확인",
];

/** Short Ops-side bridge copy for B9 skip history panel. */
export const CATCHUP_OPS_SKIP_BRIDGE =
  "Skip 이력은 원인 확인용입니다. Catch-up 실행 전 대상 시간과 기존 실행 상태를 확인해야 하며, 자동 복구가 아닙니다. Catch-up은 Studio Schedule Activation의 「누락 실행 보정」에서 운영자가 수동으로 생성합니다.";
