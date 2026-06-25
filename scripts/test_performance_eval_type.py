#!/usr/bin/env python3
"""성능 지표 eval_type 필터 API 통합 테스트."""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

API_BASE = os.environ.get("THERMOOPS_API_BASE", "http://localhost:8000/api/v1")

EVAL_PREDICTION = "PREDICTION_ACTUAL_MATCH"
EVAL_TRAINING = "TRAINING_VALIDATION"


def api(method: str, path: str, body: dict | None = None, timeout: int = 120) -> dict:
    url = f"{API_BASE}{path}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={"Content-Type": "application/json"} if data else {},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        payload = json.loads(resp.read().decode())
    if not payload.get("success"):
        raise RuntimeError(f"API failed {path}: {payload}")
    return payload["data"]


def api_raw(method: str, path: str, timeout: int = 120) -> tuple[int, dict]:
    url = f"{API_BASE}{path}"
    req = urllib.request.Request(url, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode())


def assert_eval_type(metrics: list, expected: str) -> None:
    if not metrics:
        return
    for m in metrics:
        et = m.get("eval_type")
        if expected == EVAL_PREDICTION and et != EVAL_PREDICTION:
            raise RuntimeError(f"unexpected eval_type in prediction response: {et}")
        if expected == EVAL_TRAINING and et not in (EVAL_TRAINING, "UNCLASSIFIED"):
            raise RuntimeError(f"unexpected eval_type in training response: {et}")


def main() -> int:
    print(f"THERMOps performance eval_type test ({API_BASE})")
    try:
        training = api("GET", f"/performance-metrics?eval_type={EVAL_TRAINING}")
        if training.get("eval_type") != EVAL_TRAINING:
            raise RuntimeError(f"training eval_type mismatch: {training.get('eval_type')}")
        assert_eval_type(training.get("metrics") or [], EVAL_TRAINING)
        print(f"  [training] metrics={len(training.get('metrics', []))}")

        prediction = api("GET", f"/performance-metrics?eval_type={EVAL_PREDICTION}")
        if prediction.get("eval_type") != EVAL_PREDICTION:
            raise RuntimeError(f"prediction eval_type mismatch: {prediction.get('eval_type')}")
        assert_eval_type(prediction.get("metrics") or [], EVAL_PREDICTION)
        pred_metrics = prediction.get("metrics") or []
        if not pred_metrics:
            print("  [WARN] no PREDICTION_ACTUAL_MATCH metrics - run test_prediction_evaluation.py first")
        else:
            sample = pred_metrics[0]
            for key in ("mape", "mae", "rmse", "sample_count"):
                if sample.get(key) is None:
                    raise RuntimeError(f"prediction metric missing {key}: {sample}")
            print(f"  [prediction] metrics={len(pred_metrics)} mape={sample.get('mape')}")

        status, _ = api_raw("GET", "/performance-metrics?eval_type=INVALID_TYPE")
        if status != 400:
            raise RuntimeError(f"expected 400 for invalid eval_type, got {status}")

        health = api("GET", "/dashboard/model-health")
        if not isinstance(health, list):
            raise RuntimeError("model-health response is not a list")
        if health:
            row = health[0]
            if "mape_source" not in row:
                raise RuntimeError("model-health missing mape_source")
            print(f"  [health] models={len(health)} first_source={row.get('mape_source')}")

        print("\nPASSED: performance eval_type flow")
        return 0
    except (urllib.error.URLError, RuntimeError, KeyError) as exc:
        print(f"\nFAILED: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
