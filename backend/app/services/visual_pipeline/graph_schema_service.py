"""R11-S2 Visual Pipeline graph shape helpers (minimal validation only)."""

from __future__ import annotations

from typing import Any


class VisualPipelineGraphError(ValueError):
    def __init__(self, message: str, *, error_code: str = "INVALID_GRAPH") -> None:
        super().__init__(message)
        self.error_code = error_code


def empty_graph() -> dict[str, Any]:
    return {
        "nodes": [],
        "edges": [],
        "viewport": {"x": 0, "y": 0, "zoom": 1},
    }


def normalize_graph(graph: Any | None) -> dict[str, Any]:
    """Normalize and shape-validate graph. Does not run semantic validation."""
    if graph is None:
        return empty_graph()
    if not isinstance(graph, dict):
        raise VisualPipelineGraphError("graph는 object여야 합니다.")

    nodes = graph.get("nodes", [])
    edges = graph.get("edges", [])
    viewport = graph.get("viewport")

    if not isinstance(nodes, list):
        raise VisualPipelineGraphError("graph.nodes는 list여야 합니다.")
    if not isinstance(edges, list):
        raise VisualPipelineGraphError("graph.edges는 list여야 합니다.")
    if viewport is None:
        viewport = {"x": 0, "y": 0, "zoom": 1}
    elif not isinstance(viewport, dict):
        raise VisualPipelineGraphError("graph.viewport는 object여야 합니다.")

    normalized_nodes: list[dict[str, Any]] = []
    node_ids: set[str] = set()
    for idx, node in enumerate(nodes):
        if not isinstance(node, dict):
            raise VisualPipelineGraphError(f"graph.nodes[{idx}]는 object여야 합니다.")
        node_id = node.get("id")
        node_type = node.get("type")
        if not node_id or not isinstance(node_id, str):
            raise VisualPipelineGraphError(f"graph.nodes[{idx}].id가 필요합니다.")
        if not node_type or not isinstance(node_type, str):
            raise VisualPipelineGraphError(f"graph.nodes[{idx}].type이 필요합니다.")
        if node_id in node_ids:
            raise VisualPipelineGraphError(f"중복된 node id입니다: {node_id}")
        node_ids.add(node_id)
        position = node.get("position")
        if position is not None and not isinstance(position, dict):
            raise VisualPipelineGraphError(f"graph.nodes[{idx}].position은 object여야 합니다.")
        data = node.get("data")
        if data is not None and not isinstance(data, dict):
            raise VisualPipelineGraphError(f"graph.nodes[{idx}].data는 object여야 합니다.")
        # Keep extra React Flow fields for S3 compatibility
        item = dict(node)
        item["id"] = node_id
        item["type"] = str(node_type).strip().upper()
        if position is None:
            item["position"] = {"x": 0, "y": 0}
        if data is None:
            item["data"] = {}
        normalized_nodes.append(item)

    normalized_edges: list[dict[str, Any]] = []
    for idx, edge in enumerate(edges):
        if not isinstance(edge, dict):
            raise VisualPipelineGraphError(f"graph.edges[{idx}]는 object여야 합니다.")
        source = edge.get("source")
        target = edge.get("target")
        if not source or not isinstance(source, str):
            raise VisualPipelineGraphError(f"graph.edges[{idx}].source가 필요합니다.")
        if not target or not isinstance(target, str):
            raise VisualPipelineGraphError(f"graph.edges[{idx}].target가 필요합니다.")
        # Keep extra React Flow fields for S3+ compatibility (sourceHandle/targetHandle/data/label)
        item = dict(edge)
        if not item.get("id"):
            item["id"] = f"edge-{source}-{target}-{idx}"
        normalized_edges.append(item)

    return {
        "nodes": normalized_nodes,
        "edges": normalized_edges,
        "viewport": viewport,
    }


def graph_counts(graph: dict[str, Any] | None) -> tuple[int, int]:
    g = graph or empty_graph()
    nodes = g.get("nodes") if isinstance(g, dict) else []
    edges = g.get("edges") if isinstance(g, dict) else []
    return (len(nodes) if isinstance(nodes, list) else 0, len(edges) if isinstance(edges, list) else 0)
