#!/usr/bin/env python3
"""THERMOps 전체 회귀 테스트 일괄 실행 Runner."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
FRONTEND_DIR = PROJECT_ROOT / "frontend"
DEFAULT_BACKEND_HEALTH = "http://localhost:8000/health"
DEFAULT_AIRFLOW_HEALTH = "http://localhost:8080/health"

GROUP_NAMES = ("quick", "connector", "model", "retraining", "airflow", "frontend", "full")


@dataclass
class TestCase:
    name: str
    command: list[str]
    groups: list[str]
    description: str
    timeout_seconds: int
    required: bool = True
    cwd: Path | None = None


@dataclass
class TestResult:
    name: str
    groups: list[str]
    description: str
    command: list[str]
    required: bool
    status: str  # PASSED | FAILED | SKIPPED
    elapsed_seconds: float
    log_file: str
    reason: str | None = None


def _python_test(
    script: str,
    *,
    groups: list[str],
    description: str,
    timeout_seconds: int,
    required: bool = True,
) -> TestCase:
    return TestCase(
        name=script,
        command=[sys.executable, str(SCRIPTS_DIR / script)],
        groups=groups,
        description=description,
        timeout_seconds=timeout_seconds,
        required=required,
        cwd=PROJECT_ROOT,
    )


def _build_registry() -> list[TestCase]:
    return [
        _python_test(
            "test_system_config.py",
            groups=["quick", "full"],
            description="시스템 설정 API",
            timeout_seconds=120,
        ),
        _python_test(
            "test_performance_eval_type.py",
            groups=["quick", "full"],
            description="성능 지표 eval_type",
            timeout_seconds=120,
        ),
        _python_test(
            "test_prediction_trend.py",
            groups=["quick", "full"],
            description="예측 추이 API",
            timeout_seconds=120,
        ),
        _python_test(
            "test_csv_ingestion.py",
            groups=["quick", "full"],
            description="CSV 적재",
            timeout_seconds=120,
        ),
        _python_test(
            "test_data_quality.py",
            groups=["quick", "full"],
            description="데이터 품질 점검",
            timeout_seconds=120,
        ),
        _python_test(
            "smoke_test_api.py",
            groups=["quick", "full"],
            description="API 스모크 테스트",
            timeout_seconds=120,
        ),
        _python_test(
            "test_db_connector.py",
            groups=["connector", "full"],
            description="DB Connector 적재",
            timeout_seconds=120,
        ),
        _python_test(
            "test_api_connector.py",
            groups=["connector", "full"],
            description="API Connector 적재",
            timeout_seconds=120,
        ),
        _python_test(
            "test_connector_error_handling.py",
            groups=["connector", "full"],
            description="Connector 오류 처리",
            timeout_seconds=120,
        ),
        _python_test(
            "test_feature_build.py",
            groups=["model", "full"],
            description="Feature 생성",
            timeout_seconds=180,
        ),
        _python_test(
            "test_model_training.py",
            groups=["model", "full"],
            description="LightGBM 학습",
            timeout_seconds=300,
        ),
        _python_test(
            "test_catboost_training.py",
            groups=["model", "full"],
            description="CatBoost 학습·예측",
            timeout_seconds=600,
        ),
        _python_test(
            "test_two_stage_catboost.py",
            groups=["model", "full"],
            description="2-Stage CatBoost 학습·예측",
            timeout_seconds=600,
        ),
        _python_test(
            "test_batch_prediction.py",
            groups=["model", "full"],
            description="배치 예측",
            timeout_seconds=300,
        ),
        _python_test(
            "test_prediction_evaluation.py",
            groups=["model", "full"],
            description="예측-실적 평가",
            timeout_seconds=180,
        ),
        _python_test(
            "test_drift_retraining.py",
            groups=["retraining", "full"],
            description="Drift 감지·재학습 후보",
            timeout_seconds=300,
        ),
        _python_test(
            "test_retraining_candidate_train.py",
            groups=["retraining", "full"],
            description="재학습 후보 학습",
            timeout_seconds=300,
        ),
        _python_test(
            "test_retraining_airflow.py",
            groups=["retraining", "full"],
            description="재학습 Airflow DAG",
            timeout_seconds=900,
        ),
        _python_test(
            "test_airflow_pipeline.py",
            groups=["airflow", "full"],
            description="Airflow 짧은 DAG",
            timeout_seconds=300,
        ),
        _python_test(
            "test_full_pipeline_airflow.py",
            groups=["airflow", "full"],
            description="Airflow Full Pipeline",
            timeout_seconds=1200,
        ),
        TestCase(
            name="frontend_build",
            command=[],  # resolved at runtime
            groups=["frontend", "full"],
            description="Frontend production build",
            timeout_seconds=300,
            cwd=FRONTEND_DIR,
        ),
        TestCase(
            name="frontend_check_pages",
            command=[],  # resolved at runtime
            groups=["frontend", "full"],
            description="Frontend 페이지 체크",
            timeout_seconds=300,
            cwd=FRONTEND_DIR,
        ),
    ]


REGISTRY = _build_registry()
FULL_ORDER = [tc.name for tc in REGISTRY]


def resolve_executable(name: str) -> str:
    if sys.platform == "win32":
        candidates = [f"{name}.cmd", f"{name}.exe", name]
    else:
        candidates = [name]
    for candidate in candidates:
        path = shutil.which(candidate)
        if path:
            return path
    return name


def resolve_frontend_commands(test: TestCase) -> list[str]:
    if test.name == "frontend_build":
        return [resolve_executable("npm"), "run", "build"]
    if test.name == "frontend_check_pages":
        return [resolve_executable("node"), "scripts/check-pages.mjs"]
    return test.command


def select_tests(
    group: str,
    *,
    skip_airflow: bool,
    skip_frontend: bool,
) -> list[TestCase]:
    if group == "full":
        selected_names = list(FULL_ORDER)
    else:
        selected_names = [tc.name for tc in REGISTRY if group in tc.groups]

    if skip_airflow:
        airflow_names = {tc.name for tc in REGISTRY if "airflow" in tc.groups}
        selected_names = [name for name in selected_names if name not in airflow_names]

    if skip_frontend:
        frontend_names = {tc.name for tc in REGISTRY if "frontend" in tc.groups}
        selected_names = [name for name in selected_names if name not in frontend_names]

    by_name = {tc.name: tc for tc in REGISTRY}
    return [by_name[name] for name in selected_names if name in by_name]


def http_reachable(url: str, timeout: float = 3.0) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return 200 <= resp.status < 500
    except (urllib.error.URLError, TimeoutError, OSError):
        return False


def run_preflight_checks(group: str, tests: list[TestCase]) -> list[str]:
    warnings: list[str] = []
    print(f"Python: {sys.executable}")

    needs_backend = any(tc.name != "frontend_build" and tc.name != "frontend_check_pages" for tc in tests)
    if needs_backend and not http_reachable(DEFAULT_BACKEND_HEALTH):
        warnings.append(
            f"Backend health check failed ({DEFAULT_BACKEND_HEALTH}). "
            "테스트는 계속 실행되며, 개별 테스트에서 실패할 수 있습니다."
        )

    needs_airflow = group in ("airflow", "full", "retraining") or any(
        "airflow" in tc.groups and tc.name in {t.name for t in tests} for tc in REGISTRY
    )
    airflow_tests = {tc.name for tc in tests if "airflow" in tc.name or tc.name.startswith("test_retraining_airflow")}
    if airflow_tests and not http_reachable(DEFAULT_AIRFLOW_HEALTH):
        warnings.append(
            f"Airflow health check failed ({DEFAULT_AIRFLOW_HEALTH}). "
            "Airflow 관련 테스트가 실패할 수 있습니다."
        )

    needs_frontend = any(tc.name.startswith("frontend_") for tc in tests)
    if needs_frontend and not FRONTEND_DIR.is_dir():
        warnings.append(f"Frontend directory not found: {FRONTEND_DIR}")

    for warning in warnings:
        print(f"[WARN] {warning}")
    if not warnings:
        print("[OK] Preflight checks passed (or non-blocking).")
    return warnings


def log_filename(index: int, test_name: str) -> str:
    safe = test_name.replace(".py", "").replace("/", "_")
    return f"{index:02d}_{safe}.log"


def run_single_test(
    test: TestCase,
    *,
    log_path: Path,
    timeout_seconds: float,
) -> TestResult:
    command = resolve_frontend_commands(test) if test.name.startswith("frontend_") else test.command
    cwd = test.cwd or PROJECT_ROOT

    started = time.perf_counter()
    reason: str | None = None
    status = "FAILED"

    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("w", encoding="utf-8") as log_file:
        log_file.write(f"# command: {' '.join(command)}\n")
        log_file.write(f"# cwd: {cwd}\n")
        log_file.write(f"# timeout: {timeout_seconds}s\n\n")
        log_file.flush()

        try:
            completed = subprocess.run(
                command,
                cwd=str(cwd),
                stdout=log_file,
                stderr=subprocess.STDOUT,
                timeout=timeout_seconds,
                check=False,
            )
            if completed.returncode == 0:
                status = "PASSED"
            else:
                reason = f"EXIT_{completed.returncode}"
        except subprocess.TimeoutExpired as exc:
            log_file.write(f"\n\n[TIMEOUT] exceeded {timeout_seconds}s\n")
            if exc.stdout:
                if isinstance(exc.stdout, bytes):
                    log_file.write(exc.stdout.decode("utf-8", errors="replace"))
                else:
                    log_file.write(str(exc.stdout))
            reason = "TIMEOUT"
        except FileNotFoundError as exc:
            log_file.write(f"\n\n[ERROR] executable not found: {exc}\n")
            reason = "NOT_FOUND"
        except OSError as exc:
            log_file.write(f"\n\n[ERROR] {exc}\n")
            reason = "OS_ERROR"

    elapsed = time.perf_counter() - started
    return TestResult(
        name=test.name,
        groups=test.groups,
        description=test.description,
        command=command,
        required=test.required,
        status=status,
        elapsed_seconds=elapsed,
        log_file=str(log_path),
        reason=reason,
    )


def format_duration(seconds: float) -> str:
    total = int(round(seconds))
    hours, rem = divmod(total, 3600)
    minutes, secs = divmod(rem, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def write_summary_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def write_summary_md(path: Path, payload: dict[str, Any]) -> None:
    lines = [
        "# THERMOps Regression Test Summary",
        "",
        f"- Started: {payload['started_at']}",
        f"- Finished: {payload['finished_at']}",
        f"- Duration: {payload['duration_human']}",
        f"- Group: `{payload['group']}`",
        f"- Result: **{payload['overall_status']}**",
        "",
        "## Counts",
        "",
        f"- Total: {payload['total']}",
        f"- Passed: {payload['passed']}",
        f"- Failed: {payload['failed']}",
        f"- Skipped: {payload['skipped']}",
        "",
        "## Options",
        "",
        f"- fail_fast: {payload['options']['fail_fast']}",
        f"- skip_airflow: {payload['options']['skip_airflow']}",
        f"- skip_frontend: {payload['options']['skip_frontend']}",
        f"- timeout_scale: {payload['options']['timeout_scale']}",
        "",
    ]

    if payload.get("preflight_warnings"):
        lines.extend(["## Preflight Warnings", ""])
        for warning in payload["preflight_warnings"]:
            lines.append(f"- {warning}")
        lines.append("")

    lines.extend(["## Results by Group", ""])
    for group_name, group_results in payload["by_group"].items():
        passed = sum(1 for item in group_results if item["status"] == "PASSED")
        failed = sum(1 for item in group_results if item["status"] == "FAILED")
        lines.append(f"- **{group_name}**: passed={passed}, failed={failed}")

    lines.extend(["", "## Test Results", "", "| # | Test | Status | Time | Log |", "|---|------|--------|------|-----|"])
    for idx, item in enumerate(payload["results"], start=1):
        status = item["status"]
        elapsed = f"{item['elapsed_seconds']:.1f}s"
        log_name = Path(item["log_file"]).name
        reason = f" ({item['reason']})" if item.get("reason") else ""
        lines.append(f"| {idx} | {item['name']} | {status}{reason} | {elapsed} | {log_name} |")

    failed_items = [item for item in payload["results"] if item["status"] == "FAILED"]
    if failed_items:
        lines.extend(["", "## Failed Test Logs", ""])
        for item in failed_items:
            lines.append(f"- `{item['name']}` -> `{item['log_file']}`")

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="THERMOps regression test runner")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--group", choices=GROUP_NAMES, help="실행할 테스트 그룹")
    group.add_argument("--all", action="store_true", help="--group full 과 동일")

    parser.add_argument(
        "--fail-fast",
        action="store_true",
        help="첫 실패 시 즉시 중단 (기본: 실패해도 계속 실행)",
    )
    parser.add_argument(
        "--continue-on-fail",
        action="store_true",
        default=True,
        help="실패해도 나머지 계속 실행 (기본값)",
    )
    parser.add_argument("--skip-airflow", action="store_true", help="Airflow 관련 테스트 제외")
    parser.add_argument("--skip-frontend", action="store_true", help="Frontend build/check 제외")
    parser.add_argument(
        "--timeout-scale",
        type=float,
        default=1.0,
        help="timeout 배율 (예: 2 → 2배)",
    )
    parser.add_argument(
        "--log-dir",
        type=str,
        default="",
        help="로그 디렉터리 (기본: logs/regression/YYYYMMDD_HHMMSS)",
    )
    parser.add_argument(
        "--no-build-check",
        action="store_true",
        help="Docker build 사전 검사 생략 (기본: Docker build는 실행하지 않음)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    selected_group = "full" if args.all else args.group

    if args.log_dir:
        log_dir = Path(args.log_dir)
        if not log_dir.is_absolute():
            log_dir = PROJECT_ROOT / log_dir
    else:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_dir = PROJECT_ROOT / "logs" / "regression" / stamp

    tests = select_tests(
        selected_group,
        skip_airflow=args.skip_airflow,
        skip_frontend=args.skip_frontend,
    )
    if not tests:
        print("실행할 테스트가 없습니다.")
        return 1

    print(f"THERMOps regression tests - group={selected_group}")
    print(f"Log directory: {log_dir}")
    if args.no_build_check:
        print("[info] Docker build check skipped (runner does not run docker build).")

    preflight_warnings = run_preflight_checks(selected_group, tests)
    print(f"Selected tests: {len(tests)}")
    print("")

    started_at = datetime.now(timezone.utc)
    run_started = time.perf_counter()
    results: list[TestResult] = []

    for index, test in enumerate(tests, start=1):
        timeout = max(1.0, test.timeout_seconds * args.timeout_scale)
        log_path = log_dir / log_filename(index, test.name)
        print(f"[RUN ] {test.name} (timeout={int(timeout)}s)")

        result = run_single_test(test, log_path=log_path, timeout_seconds=timeout)
        results.append(result)

        if result.status == "PASSED":
            print(f"[PASS] {test.name} ({result.elapsed_seconds:.1f}s)")
        else:
            suffix = f" -> {result.log_file}"
            if result.reason:
                suffix = f" ({result.reason}){suffix}"
            print(f"[FAIL] {test.name} ({result.elapsed_seconds:.1f}s){suffix}")
            if args.fail_fast:
                print("[STOP] fail-fast enabled")
                break

    finished_at = datetime.now(timezone.utc)
    total_elapsed = time.perf_counter() - run_started

    passed = sum(1 for r in results if r.status == "PASSED")
    failed = sum(1 for r in results if r.status == "FAILED")
    skipped = sum(1 for r in results if r.status == "SKIPPED")
    overall_status = "PASSED" if failed == 0 else "FAILED"

    by_group: dict[str, list[dict[str, Any]]] = {}
    for result in results:
        for group_name in result.groups:
            by_group.setdefault(group_name, []).append(asdict(result))

    payload: dict[str, Any] = {
        "started_at": started_at.isoformat(),
        "finished_at": finished_at.isoformat(),
        "duration_seconds": total_elapsed,
        "duration_human": format_duration(total_elapsed),
        "group": selected_group,
        "overall_status": overall_status,
        "total": len(results),
        "passed": passed,
        "failed": failed,
        "skipped": skipped,
        "options": {
            "fail_fast": args.fail_fast,
            "skip_airflow": args.skip_airflow,
            "skip_frontend": args.skip_frontend,
            "timeout_scale": args.timeout_scale,
            "no_build_check": args.no_build_check,
        },
        "preflight_warnings": preflight_warnings,
        "log_dir": str(log_dir),
        "results": [asdict(r) for r in results],
        "by_group": by_group,
    }

    log_dir.mkdir(parents=True, exist_ok=True)
    summary_json = log_dir / "summary.json"
    summary_md = log_dir / "summary.md"
    write_summary_json(summary_json, payload)
    write_summary_md(summary_md, payload)

    print("")
    print("=" * 60)
    print(f"Total:   {len(results)}")
    print(f"Passed:  {passed}")
    print(f"Failed:  {failed}")
    print(f"Skipped: {skipped}")
    print(f"Duration: {format_duration(total_elapsed)}")
    print(f"Summary: {summary_md}")
    print("=" * 60)

    return 1 if failed > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
