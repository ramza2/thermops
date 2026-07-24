#!/usr/bin/env python3
"""R11-S7-10 Visual Pipeline ops CLI — summary / stuck-runs / mark-failed.

Default mark-failed mode is dry-run. Use --apply to mutate eligible stuck runs.
Does not call run_load or change activations.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent
_ROOT = _SCRIPTS.parent
_BACKEND = _ROOT / "backend"
for p in (str(_SCRIPTS), str(_BACKEND)):
    if p not in sys.path:
        sys.path.insert(0, p)

os.environ.setdefault("POSTGRES_HOST", "localhost")
os.environ.setdefault(
    "DATABASE_URL",
    os.environ.get(
        "DATABASE_URL",
        "postgresql+asyncpg://thermops:thermops@localhost:5432/thermops",
    ),
)


def _async_run(coro):
    async def _wrapped():
        from app.core.database import engine

        try:
            return await coro
        finally:
            await engine.dispose()

    return asyncio.run(_wrapped())


def _print_json(payload: object) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))


def cmd_summary(args: argparse.Namespace) -> int:
    async def _run():
        from app.core.database import async_session
        from app.services.visual_pipeline.ops_service import get_ops_summary

        async with async_session() as db:
            return await get_ops_summary(
                db,
                pending_age_seconds=args.pending_age_seconds,
                running_lock_grace_seconds=args.running_lock_grace_seconds,
            )

    _print_json(_async_run(_run()))
    return 0


def cmd_stuck_runs(args: argparse.Namespace) -> int:
    async def _run():
        from app.core.database import async_session
        from app.services.visual_pipeline.ops_service import list_stuck_runs

        async with async_session() as db:
            return await list_stuck_runs(
                db,
                pending_age_seconds=args.pending_age_seconds,
                running_lock_grace_seconds=args.running_lock_grace_seconds,
                limit=args.limit,
            )

    _print_json(_async_run(_run()))
    return 0


def cmd_mark_failed(args: argparse.Namespace) -> int:
    apply = bool(getattr(args, "apply", False))

    async def _run():
        from app.core.database import async_session
        from app.services.visual_pipeline.ops_service import mark_stuck_runs_failed

        async with async_session() as db:
            return await mark_stuck_runs_failed(
                db,
                apply=apply,
                pending_age_seconds=args.pending_age_seconds,
                running_lock_grace_seconds=args.running_lock_grace_seconds,
                limit=args.limit,
                reason=args.reason,
            )

    result = _async_run(_run())
    _print_json(result)
    mode = "APPLY" if result.get("apply") else "DRY-RUN"
    print(
        f"\n[{mode}] candidates={len(result.get('candidates') or [])} "
        f"updated={result.get('updated_count', 0)} "
        f"audit_failed={result.get('audit_failed_count', 0)}",
        file=sys.stderr,
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="THERMOps Visual Pipeline ops (R11-S7-10)",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    def add_stuck_args(p: argparse.ArgumentParser) -> None:
        p.add_argument(
            "--pending-age-seconds",
            type=int,
            default=600,
            help="PENDING older than this many seconds is stuck (default 600)",
        )
        p.add_argument(
            "--running-lock-grace-seconds",
            type=int,
            default=0,
            help="RUNNING locked_until must be older than now-grace (default 0)",
        )
        p.add_argument(
            "--limit",
            type=int,
            default=50,
            help="Max stuck rows to list/update (default 50)",
        )

    p_summary = sub.add_parser("summary", help="Print ops summary JSON")
    add_stuck_args(p_summary)
    p_summary.set_defaults(func=cmd_summary)

    p_stuck = sub.add_parser("stuck-runs", help="List stuck runs JSON")
    add_stuck_args(p_stuck)
    p_stuck.set_defaults(func=cmd_stuck_runs)

    p_mark = sub.add_parser(
        "mark-failed",
        help="Mark eligible stuck runs FAILED (default dry-run)",
    )
    add_stuck_args(p_mark)
    mode = p_mark.add_mutually_exclusive_group()
    mode.add_argument(
        "--dry-run",
        dest="apply",
        action="store_false",
        help="List candidates only (default)",
    )
    mode.add_argument(
        "--apply",
        dest="apply",
        action="store_true",
        help="Apply FAILED update to eligible stuck runs",
    )
    p_mark.set_defaults(apply=False, func=cmd_mark_failed)
    p_mark.add_argument(
        "--reason",
        default="manual ops cleanup",
        help="Ops cleanup reason recorded on FAILED runs",
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
