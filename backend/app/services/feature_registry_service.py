"""Feature Registry 조회 (ml/feature_registry.py 래퍼)."""

from __future__ import annotations

from app.services.feature_lineage_service import get_registry_spec, list_registry_specs

__all__ = ["get_registry_spec", "list_registry_specs"]
