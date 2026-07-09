#!/usr/bin/env python3
"""R10-S9 알림 / 장애 통보 테스트."""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from test_fixtures import psql_scalar

API_BASE = os.environ.get("THERMOOPS_API_BASE", "http://localhost:8000/api/v1")
SECRET_PROBE = "TEST_SECRET_R10S9_SHOULD_NOT_LEAK"
SEED_PATH = _SCRIPTS.parent / "db" / "init" / "02_seed_clean.sql"


def api(method: str, path: str, body: dict | None = None) -> dict | list:
    req = urllib.request.Request(
        f"{API_BASE}{path}",
        method=method,
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Content-Type": "application/json"} if body is not None else {},
    )
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            payload = json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"HTTP {exc.code} {path}: {exc.read().decode()}") from exc
    if not payload.get("success"):
        raise RuntimeError(payload)
    return payload.get("data")


def assert_no_secret(blob: str) -> None:
    if SECRET_PROBE in blob:
        raise AssertionError("secret probe leaked in response")


def setup_fixture_rule() -> tuple[str, str, str]:
    channel = api("POST", "/notifications/channels", {
        "channel_name": "TEST MOCK channel",
        "channel_type": "MOCK",
        "secret_value": SECRET_PROBE,
    })
    assert_no_secret(json.dumps(channel))
    recipient = api("POST", "/notifications/recipients", {
        "recipient_name": "TEST ops",
        "recipient_type": "EMAIL",
        "address": f"ops+{SECRET_PROBE}@example.com",
    })
    assert_no_secret(json.dumps(recipient))
    rule = api("POST", "/notifications/alert-rules", {
        "rule_name": "TEST schedule fail",
        "event_source": "DATA_LOAD_SCHEDULE_RUN",
        "event_type": "SCHEDULE_RUN_FAILED",
        "min_severity": "WARNING",
        "condition_json": {"field": "run_status", "operator": "eq", "value": "FAILED"},
        "dedup_window_minutes": 30,
        "channel_ids_json": [channel["channel_id"]],
        "recipient_ids_json": [recipient["recipient_id"]],
    })
    return channel["channel_id"], recipient["recipient_id"], rule["alert_rule_id"]


def main() -> int:
    try:
        if os.environ.get("THERMOOPS_CLEAN_VERIFY") == "1":
            for tbl in (
                "tb_notification_channel",
                "tb_notification_recipient",
                "tb_alert_rule",
                "tb_notification_event",
                "tb_incident",
                "tb_notification_delivery",
            ):
                assert int(psql_scalar(f"SELECT COUNT(*) FROM {tbl}") or "0") == 0, tbl
            seed = SEED_PATH.read_text(encoding="utf-8").lower()
            assert "tb_notification_channel" not in seed or "insert into tb_notification_channel" not in seed
            print("PASS")
            return 0

        summary = api("GET", "/notifications/summary")
        assert "open_incident_count" in summary

        channel, recipient, rule_id = setup_fixture_rule()
        print(f"  [ok] fixture channel={channel} recipient={recipient} rule={rule_id}")

        fetched = api("GET", f"/notifications/channels/{channel}")
        assert fetched["channel_type"] == "MOCK"
        updated = api("PUT", f"/notifications/channels/{channel}", {"channel_name": "TEST MOCK updated"})
        assert updated["channel_name"] == "TEST MOCK updated"
        api("POST", f"/notifications/channels/{channel}/deactivate")
        api("POST", f"/notifications/channels/{channel}/activate")
        test_send = api("POST", f"/notifications/channels/{channel}/test")
        assert test_send.get("delivery_status") == "SENT"
        print("  [ok] channel CRUD + test")

        rec = api("GET", f"/notifications/recipients/{recipient}")
        assert rec["address_masked"]
        assert SECRET_PROBE not in json.dumps(rec)
        api("POST", f"/notifications/recipients/{recipient}/deactivate")
        api("POST", f"/notifications/recipients/{recipient}/activate")
        print("  [ok] recipient CRUD + masking")

        rule = api("GET", f"/notifications/alert-rules/{rule_id}")
        assert rule["event_type"] == "SCHEDULE_RUN_FAILED"
        match = api("POST", f"/notifications/alert-rules/{rule_id}/test-match", {
            "severity": "ERROR",
            "event_payload_json": {"run_status": "FAILED"},
        })
        assert match["severity_ok"] and match["condition_ok"]
        print("  [ok] alert rule + test-match")

        low_match = api("POST", f"/notifications/alert-rules/{rule_id}/test-match", {"severity": "INFO"})
        assert low_match["severity_ok"] is False

        evt = api("POST", "/notifications/events/test", {
            "event_source": "DATA_LOAD_SCHEDULE_RUN",
            "event_type": "SCHEDULE_RUN_FAILED",
            "severity": "ERROR",
            "title": "TEST schedule failed",
            "message": "run failed",
            "dedup_key": "sched-test:SCHEDULE_RUN_FAILED",
            "event_payload_json": {"run_status": "FAILED", "error_count": 1},
        })
        assert evt["event"]["event_id"]
        assert evt["incidents"]
        assert evt["deliveries"]
        assert any(d.get("delivery_status") == "SENT" for d in evt["deliveries"])
        incident_id = evt["incidents"][0]["incident_id"]
        print("  [ok] event -> incident -> MOCK delivery")

        evt2 = api("POST", "/notifications/events/test", {
            "event_source": "DATA_LOAD_SCHEDULE_RUN",
            "event_type": "SCHEDULE_RUN_FAILED",
            "severity": "ERROR",
            "title": "TEST schedule failed again",
            "dedup_key": "sched-test:SCHEDULE_RUN_FAILED",
            "event_payload_json": {"run_status": "FAILED"},
        })
        inc2 = api("GET", f"/notifications/incidents/{incident_id}")
        assert int(inc2["occurrence_count"]) >= 2
        print("  [ok] dedup incident occurrence_count")

        api("POST", f"/notifications/incidents/{incident_id}/acknowledge", {"acknowledged_by": "tester"})
        resolved = api("POST", f"/notifications/incidents/{incident_id}/resolve", {
            "resolved_by": "tester",
            "resolution_note": "fixed",
        })
        assert resolved["status"] == "RESOLVED"
        print("  [ok] incident acknowledge/resolve")

        deliveries = api("GET", "/notifications/deliveries")
        assert isinstance(deliveries, list) and deliveries
        failed = next((d for d in deliveries if d.get("delivery_status") == "FAILED"), None)
        if failed:
            retried = api("POST", f"/notifications/deliveries/{failed['delivery_id']}/retry")
            assert retried["delivery_id"] == failed["delivery_id"]
            print("  [ok] delivery retry")
        else:
            print("  [ok] delivery retry skipped (no FAILED)")

        api("POST", f"/notifications/channels/{channel}/deactivate")
        skipped_evt = api("POST", "/notifications/events/test", {
            "event_source": "DATA_LOAD_SCHEDULE_RUN",
            "event_type": "SCHEDULE_RUN_FAILED",
            "severity": "ERROR",
            "title": "disabled channel test",
            "dedup_key": "disabled-channel-test",
            "event_payload_json": {"run_status": "FAILED"},
        })
        api("POST", f"/notifications/channels/{channel}/activate")
        assert any(d.get("delivery_status") == "SKIPPED" for d in skipped_evt.get("deliveries", []))
        print("  [ok] disabled channel handling")

        events = api("GET", "/notifications/events")
        assert isinstance(events, list)
        assert_no_secret(json.dumps(events))
        print("  [ok] secret masking on responses")

        # OpenAPI route exposure
        with urllib.request.urlopen(f"{API_BASE.replace('/api/v1', '')}/openapi.json", timeout=30) as resp:
            spec = json.loads(resp.read().decode())
        paths = spec.get("paths", {})
        assert "/api/v1/notifications/summary" in paths
        assert "/api/v1/notifications/events/test" in paths
        print("  [ok] OpenAPI routes")

        print("PASS")
        return 0
    except Exception as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
