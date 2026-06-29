"""Airflow REST API 클라이언트."""

from __future__ import annotations

from typing import Any

import httpx

from app.core.config import get_settings

AIRFLOW_STATE_MAP = {
    "queued": "QUEUED",
    "running": "RUNNING",
    "success": "SUCCESS",
    "failed": "FAILED",
}


class AirflowClientError(Exception):
    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


class AirflowClient:
    def __init__(
        self,
        base_url: str | None = None,
        username: str | None = None,
        password: str | None = None,
        timeout: float = 30.0,
    ):
        settings = get_settings()
        self.base_url = (base_url or settings.airflow_base_url).rstrip("/")
        self.auth = (username or settings.airflow_username, password or settings.airflow_password)
        self.timeout = timeout

    def _url(self, path: str) -> str:
        return f"{self.base_url}/api/v1{path}"

    async def _request(self, method: str, path: str, **kwargs) -> dict[str, Any]:
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.request(method, self._url(path), auth=self.auth, **kwargs)
        except httpx.RequestError as exc:
            raise AirflowClientError(f"Airflow 연결 실패: {exc}") from exc

        if resp.status_code >= 400:
            detail = resp.text[:500]
            raise AirflowClientError(
                f"Airflow API 오류 ({resp.status_code}): {detail}",
                status_code=resp.status_code,
            )
        return resp.json()

    async def health(self) -> dict[str, Any]:
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.get(f"{self.base_url}/health", auth=self.auth)
            return {"status": "healthy" if resp.status_code < 400 else "unhealthy", "code": resp.status_code}
        except httpx.RequestError as exc:
            raise AirflowClientError(f"Airflow health check 실패: {exc}") from exc

    async def list_dags(self, limit: int = 100) -> list[dict[str, Any]]:
        payload = await self._request("GET", "/dags", params={"limit": limit})
        return payload.get("dags") or []

    async def unpause_dag(self, dag_id: str) -> None:
        await self._request("PATCH", f"/dags/{dag_id}", json={"is_paused": False})

    async def trigger_dag(self, dag_id: str, conf: dict[str, Any] | None = None) -> dict[str, Any]:
        await self.unpause_dag(dag_id)
        body: dict[str, Any] = {"conf": conf or {}}
        payload = await self._request("POST", f"/dags/{dag_id}/dagRuns", json=body)
        return payload

    async def get_dag_run(self, dag_id: str, dag_run_id: str) -> dict[str, Any]:
        return await self._request("GET", f"/dags/{dag_id}/dagRuns/{dag_run_id}")

    async def list_dag_runs(self, dag_id: str, limit: int = 25) -> list[dict[str, Any]]:
        payload = await self._request("GET", f"/dags/{dag_id}/dagRuns", params={"limit": limit, "order_by": "-start_date"})
        return payload.get("dag_runs") or []


def map_airflow_state(state: str | None) -> str | None:
    if not state:
        return None
    return AIRFLOW_STATE_MAP.get(state.lower())
