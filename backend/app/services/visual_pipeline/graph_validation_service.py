"""R11-S4-1 Visual Pipeline graph validation (read-only, no DB write)."""

from __future__ import annotations

from collections import defaultdict, deque
from typing import Any

from app.services.visual_pipeline.component_catalog_service import (
    list_components,
    list_connection_rules,
)
from app.services.visual_pipeline.config_validation_service import validate_node_configs
from app.services.visual_pipeline.graph_schema_service import (
    VisualPipelineGraphError,
    empty_graph,
    normalize_graph,
)

SOURCE_TYPES = frozenset({"VP_REST_API_SOURCE", "VP_DB_SOURCE", "VP_CSV_SOURCE"})
LOAD_TYPES = frozenset({"VP_UPSERT_LOAD"})
TRANSFORM_TYPES = frozenset({"VP_TRANSFORM"})


def _issue(
    *,
    severity: str,
    code: str,
    message: str,
    hint: str | None = None,
    phase: str | None = None,
    field_key: str | None = None,
    component_type: str | None = None,
    node_id: str | None = None,
    edge_id: str | None = None,
    source_node_id: str | None = None,
    target_node_id: str | None = None,
    source_component_type: str | None = None,
    target_component_type: str | None = None,
    source_port: str | None = None,
    target_port: str | None = None,
    source_handle: str | None = None,
    target_handle: str | None = None,
    source_data_type: str | None = None,
    target_data_type: str | None = None,
    data_type: str | None = None,
) -> dict[str, Any]:
    item: dict[str, Any] = {
        "severity": severity,
        "code": code,
        "message": message,
    }
    if hint:
        item["hint"] = hint
    if phase:
        item["phase"] = phase
    if field_key:
        item["field_key"] = field_key
    if component_type:
        item["component_type"] = component_type
    if node_id:
        item["node_id"] = node_id
    if edge_id:
        item["edge_id"] = edge_id
    if source_node_id:
        item["source_node_id"] = source_node_id
    if target_node_id:
        item["target_node_id"] = target_node_id
    if source_component_type:
        item["source_component_type"] = source_component_type
    if target_component_type:
        item["target_component_type"] = target_component_type
    if source_port:
        item["source_port"] = source_port
    if target_port:
        item["target_port"] = target_port
    if source_handle:
        item["source_handle"] = source_handle
    if target_handle:
        item["target_handle"] = target_handle
    if source_data_type:
        item["source_data_type"] = source_data_type
    if target_data_type:
        item["target_data_type"] = target_data_type
    if data_type:
        item["data_type"] = data_type
    return item


def _node_component_type(node: dict[str, Any]) -> str:
    data = node.get("data") if isinstance(node.get("data"), dict) else {}
    raw = node.get("type") or data.get("component_type") or ""
    return str(raw).strip().upper()


def _parse_handle(handle: Any, *, expect_direction: str | None = None) -> dict[str, Any]:
    """Parse output:{port} / input:{port} or legacy bare port_id."""
    if handle is None or str(handle).strip() == "":
        return {}
    raw = str(handle).strip()
    if ":" in raw:
        direction, port = raw.split(":", 1)
        direction = direction.strip().lower()
        port = port.strip()
        if direction not in {"input", "output"} or not port:
            return {"raw": raw, "malformed": True}
        result: dict[str, Any] = {"raw": raw, "direction": direction, "port": port}
        if expect_direction and direction != expect_direction:
            result["direction_mismatch"] = True
        return result
    return {"raw": raw, "port": raw, "legacy_bare": True}


def _resolve_edge_ports(
    edge: dict[str, Any],
    source_comp: dict[str, Any] | None,
    target_comp: dict[str, Any] | None,
) -> dict[str, Any]:
    """Resolve ports with handle-first priority.

    Returns dict with source_port, target_port, source_handle, target_handle,
    unspecified (True only for component-pair fallback), handle_errors (list of issue dicts partial).
    """
    data = edge.get("data") if isinstance(edge.get("data"), dict) else {}
    source_handle_raw = edge.get("sourceHandle") or edge.get("source_handle")
    target_handle_raw = edge.get("targetHandle") or edge.get("target_handle")

    src_h = _parse_handle(source_handle_raw, expect_direction="output")
    tgt_h = _parse_handle(target_handle_raw, expect_direction="input")

    handle_errors: list[dict[str, Any]] = []
    if src_h.get("malformed"):
        handle_errors.append(
            {
                "code": "EDGE_SOURCE_PORT_INVALID",
                "message": f"sourceHandle 형식이 올바르지 않습니다: {src_h.get('raw')}",
                "hint": "expected format: output:{port_name}",
                "source_handle": src_h.get("raw"),
            }
        )
    elif src_h.get("direction_mismatch"):
        handle_errors.append(
            {
                "code": "EDGE_SOURCE_PORT_INVALID",
                "message": f"sourceHandle은 output:{{port}} 이어야 합니다: {src_h.get('raw')}",
                "hint": "expected format: output:{port_name}",
                "source_handle": src_h.get("raw"),
            }
        )
    if tgt_h.get("malformed"):
        handle_errors.append(
            {
                "code": "EDGE_TARGET_PORT_INVALID",
                "message": f"targetHandle 형식이 올바르지 않습니다: {tgt_h.get('raw')}",
                "hint": "expected format: input:{port_name}",
                "target_handle": tgt_h.get("raw"),
            }
        )
    elif tgt_h.get("direction_mismatch"):
        handle_errors.append(
            {
                "code": "EDGE_TARGET_PORT_INVALID",
                "message": f"targetHandle은 input:{{port}} 이어야 합니다: {tgt_h.get('raw')}",
                "hint": "expected format: input:{port_name}",
                "target_handle": tgt_h.get("raw"),
            }
        )

    source_port = src_h.get("port")
    target_port = tgt_h.get("port")

    if not source_port:
        source_port = data.get("source_port") or data.get("from_port_id")
    if not target_port:
        target_port = data.get("target_port") or data.get("to_port_id")

    label = edge.get("label")
    if isinstance(label, str) and label.strip():
        label = label.strip()
        # support "raw_rows → input_rows"
        if "→" in label:
            left, right = [p.strip() for p in label.split("→", 1)]
            if not source_port:
                source_port = left or None
            if not target_port:
                target_port = right or None
        else:
            label_simple = label
    else:
        label_simple = None

    if not source_port and label_simple and source_comp:
        out_ids = {p.get("port_id") for p in (source_comp.get("output_ports") or [])}
        if label_simple in out_ids:
            source_port = label_simple

    if not target_port and target_comp:
        inputs = list(target_comp.get("input_ports") or [])
        if len(inputs) == 1:
            target_port = inputs[0].get("port_id")
        elif source_port and source_comp:
            out_ports = {p.get("port_id"): p for p in (source_comp.get("output_ports") or [])}
            out = out_ports.get(source_port) or {}
            out_type = out.get("data_type")
            for inp in inputs:
                accepted = inp.get("accepted_data_types") or [inp.get("data_type")]
                if out_type in accepted or inp.get("data_type") == out_type:
                    target_port = inp.get("port_id")
                    break

    unspecified = False
    if not source_port or not target_port:
        if not source_port and source_comp:
            outs = list(source_comp.get("output_ports") or [])
            if len(outs) == 1:
                source_port = outs[0].get("port_id")
        if not target_port and target_comp:
            ins = list(target_comp.get("input_ports") or [])
            if len(ins) == 1:
                target_port = ins[0].get("port_id")

    has_handles = bool(source_handle_raw) and bool(target_handle_raw) and not handle_errors
    has_data_ports = bool(data.get("source_port")) and bool(data.get("target_port"))
    # EDGE_PORT_UNSPECIFIED only when falling back (no handles / data ports)
    unspecified = not has_handles and not has_data_ports

    return {
        "source_port": str(source_port) if source_port else None,
        "target_port": str(target_port) if target_port else None,
        "source_handle": str(source_handle_raw) if source_handle_raw else None,
        "target_handle": str(target_handle_raw) if target_handle_raw else None,
        "unspecified": unspecified,
        "handle_errors": handle_errors,
    }


def _has_cycle(node_ids: set[str], edges: list[dict[str, Any]]) -> bool:
    adj: dict[str, list[str]] = defaultdict(list)
    indeg: dict[str, int] = defaultdict(int)
    involved: set[str] = set()
    for e in edges:
        s, t = e.get("source"), e.get("target")
        if s in node_ids and t in node_ids and s != t:
            adj[str(s)].append(str(t))
            indeg[str(t)] += 1
            involved.add(str(s))
            involved.add(str(t))
    if not involved:
        return False
    for n in involved:
        indeg.setdefault(n, 0)
    q = deque([n for n in involved if indeg[n] == 0])
    seen = 0
    while q:
        u = q.popleft()
        seen += 1
        for v in adj.get(u, []):
            indeg[v] -= 1
            if indeg[v] == 0:
                q.append(v)
    return seen < len(involved)


def validate_visual_pipeline_graph(
    graph: Any,
    *,
    validation_level: str = "BASIC",
    pipeline_id: str | None = None,
) -> dict[str, Any]:
    level = str(validation_level or "BASIC").strip().upper()
    if level not in {"BASIC", "STRICT"}:
        level = "BASIC"

    issues: list[dict[str, Any]] = []
    normalized: dict[str, Any]

    try:
        normalized = normalize_graph(graph)
    except VisualPipelineGraphError as exc:
        issues.append(
            _issue(
                severity="ERROR",
                code="GRAPH_INVALID_SHAPE",
                message=str(exc),
                hint="nodes/edges/viewport 형태를 확인하세요.",
            )
        )
        return _finalize(issues, empty_graph(), level, pipeline_id)

    nodes: list[dict[str, Any]] = list(normalized.get("nodes") or [])
    edges: list[dict[str, Any]] = list(normalized.get("edges") or [])
    node_ids = {n["id"] for n in nodes}
    node_by_id = {n["id"]: n for n in nodes}

    catalog = {c["component_type"]: c for c in list_components()["items"]}
    rules = list_connection_rules()["items"]
    allow_rules = [r for r in rules if r.get("allowed")]
    deny_rules = [r for r in rules if not r.get("allowed")]

    # Empty graph
    if not nodes and not edges:
        sev = "ERROR" if level == "STRICT" else "WARNING"
        issues.append(
            _issue(
                severity=sev,
                code="GRAPH_EMPTY",
                message="Graph가 비어 있습니다.",
                hint="Palette에서 노드를 추가하세요.",
            )
        )
        return _finalize(issues, normalized, level, pipeline_id)

    # Node validation
    for node in nodes:
        nid = node["id"]
        ctype = _node_component_type(node)
        if not ctype:
            issues.append(
                _issue(
                    severity="ERROR",
                    code="NODE_COMPONENT_TYPE_MISSING",
                    message=f"노드 {nid}에 component_type이 없습니다.",
                    node_id=nid,
                )
            )
            continue
        pos = node.get("position") or {}
        if not isinstance(pos, dict) or not isinstance(pos.get("x"), (int, float)) or not isinstance(pos.get("y"), (int, float)):
            issues.append(
                _issue(
                    severity="ERROR",
                    code="NODE_POSITION_INVALID",
                    message=f"노드 {nid}의 position이 유효하지 않습니다.",
                    node_id=nid,
                )
            )
        comp = catalog.get(ctype)
        if not comp:
            issues.append(
                _issue(
                    severity="ERROR",
                    code="NODE_COMPONENT_UNKNOWN",
                    message=f"알 수 없는 component_type입니다: {ctype}",
                    node_id=nid,
                    source_component_type=ctype,
                )
            )
            continue
        if comp.get("status") == "DISABLED":
            issues.append(
                _issue(
                    severity="ERROR",
                    code="NODE_COMPONENT_DISABLED",
                    message=f"DISABLED 컴포넌트는 사용할 수 없습니다: {ctype}",
                    node_id=nid,
                    source_component_type=ctype,
                    hint=comp.get("disabled_reason"),
                )
            )

    # Edge id duplicates
    edge_ids: set[str] = set()
    edge_keys: set[tuple[str, str, str | None]] = set()
    for edge in edges:
        eid = str(edge.get("id") or "")
        if eid:
            if eid in edge_ids:
                issues.append(
                    _issue(
                        severity="WARNING",
                        code="EDGE_ID_DUPLICATED",
                        message=f"중복된 edge id입니다: {eid}",
                        edge_id=eid,
                    )
                )
            edge_ids.add(eid)

        source = edge.get("source")
        target = edge.get("target")
        if source == target:
            issues.append(
                _issue(
                    severity="ERROR",
                    code="EDGE_SELF_LOOP",
                    message=f"자기 자신으로의 연결은 허용되지 않습니다 ({source}).",
                    edge_id=eid or None,
                    source_node_id=str(source) if source else None,
                    target_node_id=str(target) if target else None,
                )
            )
            continue
        if source not in node_ids:
            issues.append(
                _issue(
                    severity="ERROR",
                    code="EDGE_DANGLING_SOURCE",
                    message=f"edge source 노드가 없습니다: {source}",
                    edge_id=eid or None,
                    source_node_id=str(source) if source else None,
                    target_node_id=str(target) if target else None,
                )
            )
            continue
        if target not in node_ids:
            issues.append(
                _issue(
                    severity="ERROR",
                    code="EDGE_DANGLING_TARGET",
                    message=f"edge target 노드가 없습니다: {target}",
                    edge_id=eid or None,
                    source_node_id=str(source) if source else None,
                    target_node_id=str(target) if target else None,
                )
            )
            continue

        src_node = node_by_id[source]
        tgt_node = node_by_id[target]
        src_type = _node_component_type(src_node)
        tgt_type = _node_component_type(tgt_node)
        src_comp = catalog.get(src_type)
        tgt_comp = catalog.get(tgt_type)

        resolved = _resolve_edge_ports(edge, src_comp, tgt_comp)
        source_port = resolved["source_port"]
        target_port = resolved["target_port"]
        unspecified = resolved["unspecified"]
        source_handle = resolved["source_handle"]
        target_handle = resolved["target_handle"]

        for herr in resolved.get("handle_errors") or []:
            issues.append(
                _issue(
                    severity="ERROR",
                    code=herr["code"],
                    message=herr["message"],
                    hint=herr.get("hint"),
                    edge_id=eid or None,
                    source_node_id=str(source),
                    target_node_id=str(target),
                    source_component_type=src_type,
                    target_component_type=tgt_type,
                    source_handle=herr.get("source_handle") or source_handle,
                    target_handle=herr.get("target_handle") or target_handle,
                )
            )

        src_port_meta = None
        tgt_port_meta = None
        if src_comp and source_port:
            src_port_meta = next(
                (p for p in (src_comp.get("output_ports") or []) if p.get("port_id") == source_port),
                None,
            )
        if tgt_comp and target_port:
            tgt_port_meta = next(
                (p for p in (tgt_comp.get("input_ports") or []) if p.get("port_id") == target_port),
                None,
            )
        source_data_type = (src_port_meta or {}).get("data_type")
        target_data_type = (tgt_port_meta or {}).get("data_type")
        accepted = (tgt_port_meta or {}).get("accepted_data_types") or (
            [target_data_type] if target_data_type else []
        )

        key = (str(source), str(target), source_port)
        if key in edge_keys:
            issues.append(
                _issue(
                    severity="WARNING",
                    code="EDGE_DUPLICATED",
                    message=f"중복 연결입니다: {source} → {target}",
                    edge_id=eid or None,
                    source_node_id=str(source),
                    target_node_id=str(target),
                    source_port=source_port,
                    target_port=target_port,
                    source_handle=source_handle,
                    target_handle=target_handle,
                )
            )
        edge_keys.add(key)

        if unspecified:
            issues.append(
                _issue(
                    severity="WARNING",
                    code="EDGE_PORT_UNSPECIFIED",
                    message="연결 포트가 명시되지 않아 component pair 기준으로만 검증했습니다.",
                    edge_id=eid or None,
                    source_node_id=str(source),
                    target_node_id=str(target),
                    source_component_type=src_type,
                    target_component_type=tgt_type,
                    source_port=source_port,
                    target_port=target_port,
                    source_handle=source_handle,
                    target_handle=target_handle,
                    hint="sourceHandle/targetHandle(output:{port} / input:{port})을 저장하면 포트 검증이 정확해집니다.",
                )
            )

        if src_comp and source_port and src_port_meta is None:
            issues.append(
                _issue(
                    severity="ERROR",
                    code="EDGE_SOURCE_PORT_INVALID",
                    message=f"{src_type}에 출력 포트 {source_port}가 없습니다.",
                    edge_id=eid or None,
                    source_node_id=str(source),
                    target_node_id=str(target),
                    source_component_type=src_type,
                    source_port=source_port,
                    source_handle=source_handle,
                    target_handle=target_handle,
                )
            )
        if tgt_comp and target_port and tgt_port_meta is None:
            issues.append(
                _issue(
                    severity="ERROR",
                    code="EDGE_TARGET_PORT_INVALID",
                    message=f"{tgt_type}에 입력 포트 {target_port}가 없습니다.",
                    edge_id=eid or None,
                    source_node_id=str(source),
                    target_node_id=str(target),
                    target_component_type=tgt_type,
                    target_port=target_port,
                    source_handle=source_handle,
                    target_handle=target_handle,
                )
            )

        # Connection rules
        matched_allow = None
        matched_deny = None
        for r in deny_rules:
            if r.get("from_component_type") == src_type and r.get("to_component_type") == tgt_type:
                if not source_port or not target_port or (
                    r.get("from_port_id") == source_port and r.get("to_port_id") == target_port
                ):
                    matched_deny = r
                    break
        for r in allow_rules:
            if r.get("from_component_type") == src_type and r.get("to_component_type") == tgt_type:
                if source_port and target_port:
                    if r.get("from_port_id") == source_port and r.get("to_port_id") == target_port:
                        matched_allow = r
                        break
                else:
                    matched_allow = r
                    break

        if (
            not matched_allow
            and source_data_type
            and accepted
            and source_data_type not in accepted
        ):
            issues.append(
                _issue(
                    severity="ERROR",
                    code="EDGE_PORT_TYPE_MISMATCH",
                    message=f"포트 data_type이 호환되지 않습니다: {source_data_type} → {accepted}",
                    edge_id=eid or None,
                    source_node_id=str(source),
                    target_node_id=str(target),
                    source_component_type=src_type,
                    target_component_type=tgt_type,
                    source_port=source_port,
                    target_port=target_port,
                    source_handle=source_handle,
                    target_handle=target_handle,
                    source_data_type=source_data_type,
                    target_data_type=target_data_type,
                    data_type=source_data_type,
                )
            )

        if matched_deny and not matched_allow:
            issues.append(
                _issue(
                    severity="ERROR",
                    code="EDGE_CONNECTION_DISALLOWED",
                    message=matched_deny.get("reason")
                    or f"허용되지 않는 연결입니다: {src_type} → {tgt_type}",
                    edge_id=eid or None,
                    source_node_id=str(source),
                    target_node_id=str(target),
                    source_component_type=src_type,
                    target_component_type=tgt_type,
                    source_port=source_port,
                    target_port=target_port,
                    source_handle=source_handle,
                    target_handle=target_handle,
                    source_data_type=source_data_type,
                    target_data_type=target_data_type,
                )
            )
        elif not matched_allow and not matched_deny:
            pair_exists = any(
                r.get("from_component_type") == src_type and r.get("to_component_type") == tgt_type
                for r in rules
            )
            if not pair_exists:
                issues.append(
                    _issue(
                        severity="ERROR",
                        code="EDGE_CONNECTION_RULE_NOT_FOUND",
                        message=f"연결 규칙에 없는 조합입니다: {src_type} → {tgt_type}",
                        edge_id=eid or None,
                        source_node_id=str(source),
                        target_node_id=str(target),
                        source_component_type=src_type,
                        target_component_type=tgt_type,
                        source_port=source_port,
                        target_port=target_port,
                        source_handle=source_handle,
                        target_handle=target_handle,
                    )
                )
            elif source_port and target_port:
                issues.append(
                    _issue(
                        severity="ERROR",
                        code="EDGE_PORT_TYPE_MISMATCH",
                        message=f"포트 조합이 허용되지 않습니다: {source_port} → {target_port}",
                        edge_id=eid or None,
                        source_node_id=str(source),
                        target_node_id=str(target),
                        source_component_type=src_type,
                        target_component_type=tgt_type,
                        source_port=source_port,
                        target_port=target_port,
                        source_handle=source_handle,
                        target_handle=target_handle,
                    )
                )

        # INFO: REST → UPSERT direct is allowed; recommend Transform
        if src_type == "VP_REST_API_SOURCE" and tgt_type == "VP_UPSERT_LOAD" and matched_allow:
            issues.append(
                _issue(
                    severity="INFO",
                    code="TRANSFORM_RECOMMENDED",
                    message="REST → Upsert 직접 연결이 허용됩니다. Transform 경유를 권장합니다.",
                    edge_id=eid or None,
                    source_node_id=str(source),
                    target_node_id=str(target),
                    source_component_type=src_type,
                    target_component_type=tgt_type,
                    source_port=source_port,
                    target_port=target_port,
                    source_handle=source_handle,
                    target_handle=target_handle,
                    hint="권장 흐름: REST → Transform → Upsert",
                )
            )

    # Topology
    if _has_cycle(node_ids, edges):
        issues.append(
            _issue(
                severity="ERROR",
                code="GRAPH_CYCLE_DETECTED",
                message="Graph에 cycle이 있습니다.",
                hint="순환 참조를 제거하세요.",
            )
        )

    types_present = {_node_component_type(n) for n in nodes}
    has_source = bool(types_present & SOURCE_TYPES)
    has_load = bool(types_present & LOAD_TYPES)

    if not has_source:
        sev = "ERROR" if level == "STRICT" else "WARNING"
        issues.append(
            _issue(
                severity=sev,
                code="SOURCE_NODE_MISSING",
                message="Source 계열 노드(VP_REST_API_SOURCE 등)가 없습니다.",
                hint="REST API Source를 추가하세요.",
            )
        )
    if not has_load:
        sev = "ERROR" if level == "STRICT" else "WARNING"
        issues.append(
            _issue(
                severity=sev,
                code="LOAD_NODE_MISSING",
                message="Load 노드(VP_UPSERT_LOAD)가 없습니다.",
                hint="Upsert Load 노드를 추가하세요.",
            )
        )

    incoming: dict[str, list[dict[str, Any]]] = defaultdict(list)
    outgoing: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for e in edges:
        if e.get("source") in node_ids and e.get("target") in node_ids:
            incoming[str(e["target"])].append(e)
            outgoing[str(e["source"])].append(e)

    for node in nodes:
        nid = node["id"]
        ctype = _node_component_type(node)
        if ctype in LOAD_TYPES and not incoming.get(nid):
            issues.append(
                _issue(
                    severity="ERROR",
                    code="LOAD_NODE_INPUT_MISSING",
                    message=f"Load 노드 {nid}에 입력 연결이 없습니다.",
                    node_id=nid,
                    source_component_type=ctype,
                )
            )
        if ctype in LOAD_TYPES and len(incoming.get(nid, [])) > 1:
            sev = "ERROR" if level == "STRICT" else "WARNING"
            issues.append(
                _issue(
                    severity=sev,
                    code="MULTIPLE_LOAD_INPUTS",
                    message=f"Load 노드 {nid}에 입력이 여러 개입니다.",
                    node_id=nid,
                    source_component_type=ctype,
                )
            )
        if ctype in SOURCE_TYPES and not outgoing.get(nid):
            issues.append(
                _issue(
                    severity="WARNING",
                    code="SOURCE_OUTPUT_UNUSED",
                    message=f"Source 노드 {nid}의 출력이 연결되지 않았습니다.",
                    node_id=nid,
                    source_component_type=ctype,
                )
            )
        if ctype in SOURCE_TYPES and len(outgoing.get(nid, [])) > 1:
            issues.append(
                _issue(
                    severity="INFO",
                    code="SOURCE_MULTIPLE_OUTPUTS",
                    message=f"Source 노드 {nid}에서 출력이 여러 갈래입니다.",
                    node_id=nid,
                    source_component_type=ctype,
                )
            )

    # Disconnected / orphan nodes
    if len(nodes) > 1:
        for nid in node_ids:
            if not incoming.get(nid) and not outgoing.get(nid):
                issues.append(
                    _issue(
                        severity="WARNING",
                        code="NODE_DISCONNECTED",
                        message=f"노드 {nid}가 다른 노드와 연결되지 않았습니다.",
                        node_id=nid,
                    )
                )

    # R11-S5-5 Node config validation (after topology / port / edge)
    issues.extend(validate_node_configs(nodes, catalog, validation_level=level))

    return _finalize(issues, normalized, level, pipeline_id)


def _finalize(
    issues: list[dict[str, Any]],
    normalized: dict[str, Any],
    level: str,
    pipeline_id: str | None,
) -> dict[str, Any]:
    # de-duplicate identical issues
    seen: set[tuple[Any, ...]] = set()
    unique: list[dict[str, Any]] = []
    for iss in issues:
        key = (
            iss.get("severity"),
            iss.get("code"),
            iss.get("message"),
            iss.get("phase"),
            iss.get("field_key"),
            iss.get("node_id"),
            iss.get("edge_id"),
            iss.get("source_node_id"),
            iss.get("target_node_id"),
        )
        if key in seen:
            continue
        seen.add(key)
        unique.append(iss)

    error_count = sum(1 for i in unique if i.get("severity") == "ERROR")
    warning_count = sum(1 for i in unique if i.get("severity") == "WARNING")
    info_count = sum(1 for i in unique if i.get("severity") == "INFO")
    valid = error_count == 0
    if error_count:
        severity = "ERROR"
    elif warning_count:
        severity = "WARNING"
    elif info_count:
        severity = "INFO"
    else:
        severity = "OK"

    nodes = normalized.get("nodes") or []
    edges = normalized.get("edges") or []
    result: dict[str, Any] = {
        "valid": valid,
        "severity": severity,
        "validation_level": level,
        "summary": {
            "node_count": len(nodes) if isinstance(nodes, list) else 0,
            "edge_count": len(edges) if isinstance(edges, list) else 0,
            "error_count": error_count,
            "warning_count": warning_count,
            "info_count": info_count,
        },
        "issues": unique,
        "normalized_graph": normalized,
    }
    if pipeline_id:
        result["pipeline_id"] = pipeline_id
    return result
