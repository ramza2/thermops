"""Pipeline Definition 기반 Airflow 실행 연계 (Phase R9)."""

from __future__ import annotations

import re
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.time import utc_now
from app.models.entities import (
    PipelineDefinition,
    PipelineRun,
    PipelineRunLink,
    PipelineTemplate,
)
from app.services.airflow_client import AirflowClient, AirflowClientError, map_airflow_state
from app.services.pipeline_builder_service import (
    build_airflow_runtime_params,
    validate_pipeline_definition,
)
from app.services.pipeline_service import PIPELINE_IDS, PIPELINE_DEFINITIONS

RUNNABLE_STATUSES = frozenset({"ACTIVE", "VALIDATED"})
RUN_SOURCE_PIPELINE = "PIPELINE_DEFINITION"
RUN_SOURCE_DIRECT = "DIRECT_DAG"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _safe_dag_run_id(pipeline_id: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_.-]", "_", pipeline_id)[:40]
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    return f"pipeline__{safe}__{ts}"


def validate_pipeline_runnable(defn: PipelineDefinition, template: PipelineTemplate) -> list[dict[str, Any]]:
    errors: list[dict[str, Any]] = []
    if defn.active_yn != "Y" or defn.status == "ARCHIVED":
        errors.append({
            "code": "PIPELINE_ARCHIVED",
            "message": "보관된 Pipeline Definition은 실행할 수 없습니다.",
        })
    if template.status == "PLANNED":
        errors.append({
            "code": "TEMPLATE_NOT_ACTIVE",
            "message": "PLANNED 템플릿 Pipeline은 실행할 수 없습니다.",
        })
    elif template.status != "ACTIVE" or template.active_yn != "Y":
        errors.append({
            "code": "TEMPLATE_NOT_ACTIVE",
            "message": f"템플릿이 ACTIVE가 아닙니다: {template.status}",
        })
    dag_id = defn.airflow_dag_id or template.airflow_dag_id
    if not dag_id or dag_id not in PIPELINE_IDS:
        errors.append({
            "code": "AIRFLOW_DAG_NOT_MAPPED",
            "message": f"Airflow DAG 매핑이 없습니다: {dag_id}",
        })
    return errors


def build_airflow_conf(
    defn: PipelineDefinition,
    template: PipelineTemplate,
    *,
    validation: dict[str, Any],
    runtime_params: dict[str, Any],
    node_config: dict[str, Any],
    schedule_config: dict[str, Any] | None,
    pipeline_run_id: str,
    request: dict[str, Any],
) -> dict[str, Any]:
    now_iso = _utc_now().isoformat()
    thermops_context = {
        "run_source": RUN_SOURCE_PIPELINE,
        "pipeline_id": defn.pipeline_id,
        "template_id": defn.template_id,
        "template_code": template.template_code,
        "pipeline_name": defn.pipeline_name,
        "pipeline_type": defn.pipeline_type,
        "requested_by": request.get("requested_by"),
        "requested_at": now_iso,
        "run_label": request.get("run_label"),
    }
    validation_snapshot = {
        "valid": validation.get("valid"),
        "errors": validation.get("errors") or [],
        "warnings": validation.get("warnings") or [],
    }
    schedule = schedule_config or {"enabled": False, "schedule_type": "MANUAL"}

    conf: dict[str, Any] = {
        **runtime_params,
        "pipeline_run_id": pipeline_run_id,
        "pipeline_definition_id": defn.pipeline_id,
        "thermops_context": thermops_context,
        "node_config": node_config,
        "runtime_params": runtime_params,
        "schedule_config": schedule,
        "validation_snapshot": validation_snapshot,
    }
    return conf


def _link_dict(link: PipelineRunLink, *, defn: PipelineDefinition | None = None, template: PipelineTemplate | None = None) -> dict[str, Any]:
    duration = None
    if link.finished_at and link.started_at:
        duration = int((link.finished_at - link.started_at).total_seconds() / 60)
    item = {
        "link_id": link.link_id,
        "pipeline_id": link.pipeline_id,
        "template_id": link.template_id,
        "pipeline_run_id": link.pipeline_run_id,
        "airflow_dag_id": link.airflow_dag_id,
        "airflow_run_id": link.airflow_run_id,
        "run_source": link.run_source,
        "run_status": link.run_status,
        "runtime_params_snapshot": link.runtime_params_snapshot,
        "node_config_snapshot": link.node_config_snapshot,
        "validation_snapshot": link.validation_snapshot,
        "trigger_response_json": link.trigger_response_json,
        "error_message": link.error_message,
        "requested_by": link.requested_by,
        "requested_at": link.requested_at.isoformat() if link.requested_at else None,
        "started_at": link.started_at.isoformat() if link.started_at else None,
        "finished_at": link.finished_at.isoformat() if link.finished_at else None,
        "duration_minutes": duration,
    }
    if defn:
        item["pipeline_name"] = defn.pipeline_name
    if template:
        item["template_code"] = template.template_code
        item["template_name"] = template.template_name
    return item


async def _load_definition_bundle(
    db: AsyncSession, pipeline_id: str
) -> tuple[PipelineDefinition, PipelineTemplate]:
    defn = (
        await db.execute(select(PipelineDefinition).where(PipelineDefinition.pipeline_id == pipeline_id))
    ).scalar_one_or_none()
    if not defn:
        raise LookupError("PIPELINE_NOT_FOUND")
    template = (
        await db.execute(select(PipelineTemplate).where(PipelineTemplate.template_id == defn.template_id))
    ).scalar_one_or_none()
    if not template:
        raise LookupError("TEMPLATE_NOT_FOUND")
    return defn, template


async def run_pipeline_definition(
    db: AsyncSession,
    pipeline_id: str,
    request: dict[str, Any] | None = None,
) -> dict[str, Any]:
    request = request or {}
    dry_run = bool(request.get("dry_run"))
    defn, template = await _load_definition_bundle(db, pipeline_id)

    runnable_errors = validate_pipeline_runnable(defn, template)
    if runnable_errors:
        raise ValueError(runnable_errors[0]["message"])

    if defn.status == "DRAFT":
        raise ValueError("DRAFT 상태 Pipeline은 실행할 수 없습니다. 먼저 검증을 통과하세요.")

    validation = await validate_pipeline_definition(db, pipeline_id=pipeline_id)
    await db.refresh(defn)
    if not validation["valid"]:
        msg = validation["errors"][0]["message"] if validation["errors"] else "검증 실패"
        raise ValueError(msg)
    if defn.status not in RUNNABLE_STATUSES:
        raise ValueError(f"실행 가능 상태(ACTIVE/VALIDATED)가 아닙니다: {defn.status}")

    node_config = deepcopy(defn.node_config_json or {})
    schedule_config = deepcopy(defn.schedule_config_json or {"enabled": False, "schedule_type": "MANUAL"})
    runtime_params = build_airflow_runtime_params(template, node_config, pipeline_id=pipeline_id)
    override = request.get("runtime_params_override") or {}
    if override:
        runtime_params.update(override)

    airflow_dag_id = defn.airflow_dag_id or template.airflow_dag_id or ""
    pipeline_run_id = f"PIPE-RUN-{uuid4().hex[:6].upper()}"
    airflow_conf = build_airflow_conf(
        defn,
        template,
        validation=validation,
        runtime_params=runtime_params,
        node_config=node_config,
        schedule_config=schedule_config,
        pipeline_run_id=pipeline_run_id,
        request=request,
    )

    warnings = list(validation.get("warnings") or [])
    if schedule_config.get("enabled"):
        warnings.append({
            "code": "SCHEDULE_CONFIG_NOT_APPLIED",
            "message": "schedule_config.enabled=true 이지만 R9에서는 실제 Airflow 스케줄에 반영되지 않습니다.",
        })
    warnings.append({
        "code": "AIRFLOW_CONF_MAY_BE_IGNORED_BY_CURRENT_DAG",
        "message": "현재 Airflow DAG가 thermops_context를 읽지 않을 수 있으나 conf snapshot은 저장됩니다.",
    })

    if dry_run:
        return {
            "pipeline_id": pipeline_id,
            "pipeline_run_id": pipeline_run_id,
            "airflow_dag_id": airflow_dag_id,
            "airflow_run_id": None,
            "run_status": "DRY_RUN",
            "run_source": RUN_SOURCE_PIPELINE,
            "validation": validation,
            "warnings": warnings,
            "runtime_params_snapshot": runtime_params,
            "airflow_conf": airflow_conf,
            "dry_run": True,
            "message": "dry_run: Airflow trigger 없이 conf preview만 반환합니다.",
        }

    ptype = next(
        (p["type"] for p in PIPELINE_DEFINITIONS if p["pipeline_id"] == airflow_dag_id),
        defn.pipeline_type,
    )
    now = _utc_now()
    link_id = f"PLINK-{uuid4().hex[:6].upper()}"

    run = PipelineRun(
        pipeline_run_id=pipeline_run_id,
        pipeline_id=airflow_dag_id,
        pipeline_name=defn.pipeline_name,
        pipeline_type=ptype,
        orchestrator="AIRFLOW",
        run_status="QUEUED",
        started_at=now,
        message=f"Pipeline Definition 실행 요청: {defn.pipeline_name}",
        result_summary={
            "run_source": RUN_SOURCE_PIPELINE,
            "pipeline_definition_id": pipeline_id,
            "template_code": template.template_code,
            "conf": airflow_conf,
            "warnings": warnings,
        },
    )
    db.add(run)

    link = PipelineRunLink(
        link_id=link_id,
        pipeline_id=pipeline_id,
        template_id=template.template_id,
        pipeline_run_id=pipeline_run_id,
        airflow_dag_id=airflow_dag_id,
        run_source=RUN_SOURCE_PIPELINE,
        run_status="REQUESTED",
        runtime_params_snapshot=runtime_params,
        node_config_snapshot=node_config,
        validation_snapshot={
            "valid": validation.get("valid"),
            "errors": validation.get("errors"),
            "warnings": warnings,
        },
        requested_by=request.get("requested_by"),
        requested_at=now,
        started_at=now,
        created_at=now,
        updated_at=now,
    )
    db.add(link)
    await db.flush()

    client = AirflowClient()
    dag_run_id = _safe_dag_run_id(pipeline_id)
    try:
        dag_run = await client.trigger_dag(airflow_dag_id, airflow_conf, dag_run_id=dag_run_id)
    except AirflowClientError as exc:
        run.run_status = "FAILED"
        run.finished_at = _utc_now()
        run.message = f"Airflow 트리거 실패: {exc}"
        run.result_summary = {**(run.result_summary or {}), "error_message": str(exc)}
        link.run_status = "FAILED"
        link.error_message = str(exc)
        link.finished_at = _utc_now()
        link.updated_at = _utc_now()
        defn.last_run_id = pipeline_run_id
        defn.updated_at = utc_now()
        await db.flush()
        return {
            "pipeline_id": pipeline_id,
            "link_id": link_id,
            "pipeline_run_id": pipeline_run_id,
            "airflow_dag_id": airflow_dag_id,
            "airflow_run_id": None,
            "run_status": "FAILED",
            "run_source": RUN_SOURCE_PIPELINE,
            "validation": validation,
            "warnings": warnings,
            "runtime_params_snapshot": runtime_params,
            "airflow_conf": airflow_conf,
            "error_message": str(exc),
            "message": "Airflow trigger 실패. run link에 오류가 저장되었습니다.",
        }

    orchestrator_run_id = dag_run.get("dag_run_id") or dag_run_id
    mapped = map_airflow_state(dag_run.get("state")) or "QUEUED"
    run.orchestrator_run_id = orchestrator_run_id
    run.run_status = mapped
    run.message = f"Pipeline Definition → Airflow 트리거 (dag_run_id={orchestrator_run_id})"

    link.airflow_run_id = orchestrator_run_id
    link.run_status = mapped if mapped in ("QUEUED", "RUNNING") else mapped
    link.trigger_response_json = dag_run
    link.updated_at = _utc_now()

    defn.last_run_id = pipeline_run_id
    defn.runtime_params_json = runtime_params
    defn.updated_at = utc_now()
    await db.flush()

    return {
        "pipeline_id": pipeline_id,
        "link_id": link_id,
        "pipeline_run_id": pipeline_run_id,
        "airflow_dag_id": airflow_dag_id,
        "airflow_run_id": orchestrator_run_id,
        "run_status": mapped,
        "run_source": RUN_SOURCE_PIPELINE,
        "validation": validation,
        "warnings": warnings,
        "runtime_params_snapshot": runtime_params,
        "airflow_conf": airflow_conf,
        "message": "Pipeline Definition 실행 요청이 등록되었습니다.",
    }


async def list_pipeline_definition_runs(
    db: AsyncSession,
    pipeline_id: str,
    *,
    limit: int = 20,
    status: str | None = None,
) -> list[dict[str, Any]]:
    q = (
        select(PipelineRunLink)
        .where(PipelineRunLink.pipeline_id == pipeline_id)
        .order_by(PipelineRunLink.requested_at.desc())
        .limit(limit)
    )
    if status:
        q = q.where(PipelineRunLink.run_status == status)
    links = (await db.execute(q)).scalars().all()
    defn = (
        await db.execute(select(PipelineDefinition).where(PipelineDefinition.pipeline_id == pipeline_id))
    ).scalar_one_or_none()
    template = None
    if defn:
        template = (
            await db.execute(select(PipelineTemplate).where(PipelineTemplate.template_id == defn.template_id))
        ).scalar_one_or_none()
    return [_link_dict(link, defn=defn, template=template) for link in links]


async def list_pipeline_run_links(
    db: AsyncSession,
    *,
    pipeline_id: str | None = None,
    template_id: str | None = None,
    airflow_dag_id: str | None = None,
    run_status: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    q = select(PipelineRunLink).order_by(PipelineRunLink.requested_at.desc()).limit(limit)
    if pipeline_id:
        q = q.where(PipelineRunLink.pipeline_id == pipeline_id)
    if template_id:
        q = q.where(PipelineRunLink.template_id == template_id)
    if airflow_dag_id:
        q = q.where(PipelineRunLink.airflow_dag_id == airflow_dag_id)
    if run_status:
        q = q.where(PipelineRunLink.run_status == run_status)
    links = (await db.execute(q)).scalars().all()
    return [_link_dict(link) for link in links]


async def get_pipeline_run_link(db: AsyncSession, link_id: str) -> dict[str, Any]:
    link = (
        await db.execute(select(PipelineRunLink).where(PipelineRunLink.link_id == link_id))
    ).scalar_one_or_none()
    if not link:
        raise LookupError("LINK_NOT_FOUND")
    defn = (
        await db.execute(select(PipelineDefinition).where(PipelineDefinition.pipeline_id == link.pipeline_id))
    ).scalar_one_or_none()
    template = (
        await db.execute(select(PipelineTemplate).where(PipelineTemplate.template_id == link.template_id))
    ).scalar_one_or_none()
    return _link_dict(link, defn=defn, template=template)


async def sync_pipeline_run_link_status(db: AsyncSession, link_id: str) -> dict[str, Any]:
    link = (
        await db.execute(select(PipelineRunLink).where(PipelineRunLink.link_id == link_id))
    ).scalar_one_or_none()
    if not link:
        raise LookupError("LINK_NOT_FOUND")
    if not link.airflow_dag_id or not link.airflow_run_id:
        return _link_dict(link)

    client = AirflowClient()
    try:
        dag_run = await client.get_dag_run(link.airflow_dag_id, link.airflow_run_id)
    except AirflowClientError as exc:
        link.error_message = str(exc)
        link.updated_at = _utc_now()
        await db.flush()
        return _link_dict(link)

    mapped = map_airflow_state(dag_run.get("state"))
    if mapped:
        link.run_status = mapped
        if mapped in ("SUCCESS", "FAILED"):
            end_date = dag_run.get("end_date")
            if end_date:
                try:
                    link.finished_at = datetime.fromisoformat(end_date.replace("Z", "+00:00")).replace(tzinfo=None)
                except ValueError:
                    link.finished_at = link.finished_at or _utc_now()
            else:
                link.finished_at = link.finished_at or _utc_now()
        link.updated_at = _utc_now()

    run = (
        await db.execute(select(PipelineRun).where(PipelineRun.pipeline_run_id == link.pipeline_run_id))
    ).scalar_one_or_none()
    if run and mapped:
        run.run_status = mapped
        if mapped in ("SUCCESS", "FAILED") and link.finished_at:
            run.finished_at = link.finished_at
    await db.flush()
    return _link_dict(link)


async def attach_pipeline_metadata_to_runs(db: AsyncSession, runs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not runs:
        return runs
    run_ids = [r["pipeline_run_id"] for r in runs if r.get("pipeline_run_id")]
    if not run_ids:
        return runs

    links = (
        await db.execute(
            select(PipelineRunLink).where(PipelineRunLink.pipeline_run_id.in_(run_ids))
        )
    ).scalars().all()
    if not links:
        for r in runs:
            summary = r.get("result_summary") or {}
            if isinstance(summary, dict) and summary.get("run_source") == RUN_SOURCE_DIRECT:
                r["run_source"] = RUN_SOURCE_DIRECT
            else:
                r.setdefault("run_source", RUN_SOURCE_DIRECT)
        return runs

    pipeline_ids = {link.pipeline_id for link in links}
    defns = {
        d.pipeline_id: d
        for d in (await db.execute(select(PipelineDefinition).where(PipelineDefinition.pipeline_id.in_(pipeline_ids)))).scalars().all()
    }
    templates = {
        t.template_id: t
        for t in (
            await db.execute(
                select(PipelineTemplate).where(
                    PipelineTemplate.template_id.in_({link.template_id for link in links})
                )
            )
        ).scalars().all()
    }
    by_run_id = {link.pipeline_run_id: link for link in links}

    enriched = []
    for r in runs:
        row = dict(r)
        link = by_run_id.get(row.get("pipeline_run_id"))
        if link:
            defn = defns.get(link.pipeline_id)
            tpl = templates.get(link.template_id)
            row["run_source"] = link.run_source
            row["pipeline_definition_id"] = link.pipeline_id
            row["pipeline_name_from_definition"] = defn.pipeline_name if defn else None
            row["template_id"] = link.template_id
            row["template_code"] = tpl.template_code if tpl else None
            row["template_name"] = tpl.template_name if tpl else None
            row["runtime_params_snapshot"] = link.runtime_params_snapshot
            row["link_id"] = link.link_id
        else:
            summary = row.get("result_summary") or {}
            if isinstance(summary, dict) and summary.get("run_source"):
                row["run_source"] = summary["run_source"]
            else:
                row["run_source"] = RUN_SOURCE_DIRECT
        enriched.append(row)
    return enriched
