"""R11-S1 Visual Pipeline component catalog schemas (code-based, no DB)."""

from __future__ import annotations

from typing import Any, Literal, TypedDict


ComponentStatus = Literal["ACTIVE", "DISABLED", "EXPERIMENTAL"]
ComponentCategory = Literal[
    "DATA_INPUT",
    "TRANSFORM",
    "LOAD",
    "SCHEDULE",
    "OPERATION",
    "QUALITY",
    "FEATURE",
    "MODEL",
    "PREDICTION",
]


class PortDict(TypedDict, total=False):
    port_id: str
    data_type: str
    required: bool
    accepted_data_types: list[str]
    description: str


class ComponentContractDict(TypedDict, total=False):
    component_type: str
    display_name: str
    category: str
    status: str
    version: str
    description: str
    disabled_reason: str | None
    input_ports: list[PortDict]
    output_ports: list[PortDict]
    config_schema: list[dict[str, Any]]
    validation_rules: list[str]
    compile_role: str | None
    execution_adapter: str | None
    ui_hints: dict[str, Any]
    allowed_targets: list[dict[str, Any]]


class ConnectionRuleDict(TypedDict, total=False):
    rule_id: str
    from_component_type: str
    from_port_id: str
    to_component_type: str
    to_port_id: str
    allowed: bool
    reason: str


class CardinalityRuleDict(TypedDict, total=False):
    component_type: str
    min_count: int
    max_count: int
    required: bool
    note: str
