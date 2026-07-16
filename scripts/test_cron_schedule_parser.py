#!/usr/bin/env python3
"""R10-S11 CRON parser / next-run 계산 단위 테스트."""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent
_BACKEND = _SCRIPTS.parent / "backend"
for p in (str(_SCRIPTS), str(_BACKEND)):
    if p not in sys.path:
        sys.path.insert(0, p)

from app.services.cron_schedule_service import (
    CronParseError,
    compute_next_cron_run_at,
    explain_cron_expression,
    is_cron_due,
    normalize_day_of_week,
    parse_cron_expression,
    preview_cron_runs,
    validate_cron_expression,
)
from app.services.schedule_time_service import compute_next_run_at, is_schedule_due


def expect_error(expr: str, substring: str) -> None:
    try:
        parse_cron_expression(expr)
        raise AssertionError(f"expected error for {expr!r}")
    except CronParseError as exc:
        assert substring in str(exc), f"{expr}: got {exc}"


def main() -> int:
    print("THERMOps CRON schedule parser test")
    try:
        # 1) 5-field success
        parsed = parse_cron_expression("*/5 * * * *")
        assert 0 in parsed.minute and 5 in parsed.minute
        print("  [ok] 5-field parse")

        # 2) 6-field blocked
        expect_error("0 */5 * * * *", "6-field")
        print("  [ok] 6-field blocked")

        # 3) Quartz blocked
        for bad in ("0 0 L * *", "0 0 ? * *", "0 0 1W * *", "0 0 1 * 1#1"):
            expect_error(bad, "Quartz")
        print("  [ok] Quartz blocked")

        # 4-8) ranges
        expect_error("60 * * * *", "0~59")
        expect_error("0 24 * * *", "0~23")
        expect_error("0 0 32 * *", "1~31")
        expect_error("0 0 1 13 *", "1~12")
        assert normalize_day_of_week(7) == 0
        p_sun = parse_cron_expression("0 0 * * 0")
        p_sun7 = parse_cron_expression("0 0 * * 7")
        assert 0 in p_sun.day_of_week and 0 in p_sun7.day_of_week
        print("  [ok] field ranges + Sunday 0/7")

        ref = datetime(2026, 7, 16, 10, 0, 0)

        # 9) exact
        nxt = compute_next_cron_run_at("30 2 * * *", from_time=ref, timezone="Asia/Seoul")
        assert nxt == datetime(2026, 7, 17, 2, 30, 0)
        print("  [ok] exact next run")

        # 10) wildcard minute next
        nxt_w = compute_next_cron_run_at("* * * * *", from_time=ref, timezone="Asia/Seoul")
        assert nxt_w == datetime(2026, 7, 16, 10, 1, 0)
        print("  [ok] wildcard next run")

        # 11) step */5
        nxt5 = compute_next_cron_run_at("*/5 * * * *", from_time=datetime(2026, 7, 16, 10, 1, 0), timezone="Asia/Seoul")
        assert nxt5 == datetime(2026, 7, 16, 10, 5, 0)
        print("  [ok] step */5")

        # 12) range 1-5 weekdays at 09:00 — from Thu 2026-07-16 → Fri 09:00
        nxt_wd = compute_next_cron_run_at("0 9 * * 1-5", from_time=datetime(2026, 7, 16, 10, 0, 0), timezone="Asia/Seoul")
        assert nxt_wd == datetime(2026, 7, 17, 9, 0, 0)  # Friday
        print("  [ok] range 1-5")

        # 13) list
        nxt_list = compute_next_cron_run_at("0 9 * * 1,3,5", from_time=datetime(2026, 7, 16, 10, 0, 0), timezone="Asia/Seoul")
        assert nxt_list == datetime(2026, 7, 17, 9, 0, 0)
        print("  [ok] list 1,3,5")

        # 14) range step
        p_rs = parse_cron_expression("0 0 1-10/2 * *")
        assert p_rs.day_of_month == frozenset({1, 3, 5, 7, 9})
        print("  [ok] range step 1-10/2")

        # 15) month-end: Feb 31 → skip to Mar 31 when both allowed via day 31
        nxt_m = compute_next_cron_run_at("0 0 31 * *", from_time=datetime(2026, 1, 31, 0, 0, 0), timezone="Asia/Seoul")
        assert nxt_m == datetime(2026, 3, 31, 0, 0, 0)
        print("  [ok] month-end / nonexistent day")

        # 16) timezone Asia/Seoul
        assert compute_next_cron_run_at("0 0 * * *", from_time=datetime(2026, 7, 16, 0, 0, 0), timezone="Asia/Seoul") == datetime(
            2026, 7, 17, 0, 0, 0
        )
        print("  [ok] timezone Asia/Seoul")

        # 17) preview 10
        runs = preview_cron_runs("0 * * * *", from_time=datetime(2026, 7, 16, 10, 30, 0), count=10, timezone="Asia/Seoul")
        assert len(runs) == 10
        assert runs[0] == datetime(2026, 7, 16, 11, 0, 0)
        assert runs[1] == datetime(2026, 7, 16, 12, 0, 0)
        print("  [ok] preview next 10")

        # 18) invalid validation response
        invalid = validate_cron_expression("bad")
        assert invalid["valid"] is False and invalid["errors"]
        print("  [ok] invalid validation")

        # 19) search limit does not hang (far-future valid expr)
        far = compute_next_cron_run_at("0 0 29 2 *", from_time=datetime(2026, 3, 1, 0, 0, 0), timezone="Asia/Seoul")
        assert far.month == 2 and far.day == 29
        print("  [ok] leap-day / search completes")

        # schedule_time_service CRON integration
        cron_sched = {
            "schedule_type": "CRON",
            "cron_expression": "*/5 * * * *",
            "timezone": "Asia/Seoul",
            "active_yn": True,
            "next_run_at": datetime(2026, 7, 16, 9, 55, 0),
        }
        nxt_s = compute_next_run_at(cron_sched, from_time=ref)
        assert nxt_s == datetime(2026, 7, 16, 10, 5, 0)
        assert is_schedule_due(cron_sched, ref) is True
        manual = {"schedule_type": "MANUAL", "active_yn": True}
        assert is_schedule_due(manual, ref) is False
        assert is_cron_due("*/5 * * * *", datetime(2026, 7, 16, 9, 0, 0), now=ref) is True
        assert explain_cron_expression("0 9 * * 1-5")
        print("  [ok] schedule_time_service CRON due/next")

        # HOURLY regression untouched
        hourly = {"schedule_type": "HOURLY", "timezone": "Asia/Seoul", "start_at": datetime(2026, 1, 1, 0, 15, 0)}
        assert compute_next_run_at(hourly, from_time=datetime(2026, 7, 16, 10, 30, 0)) == datetime(2026, 7, 16, 11, 15, 0)
        print("  [ok] HOURLY regression")

        print("PASS")
        return 0
    except Exception as exc:
        print(f"FAIL: {exc}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
