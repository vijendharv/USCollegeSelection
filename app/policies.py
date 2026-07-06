"""Apply small, reviewable institution-policy overrides to public data."""

from __future__ import annotations

import json
from pathlib import Path

from app.models.college import Institution

DEFAULT_POLICY_PATH = Path(__file__).with_name("data") / "institution_policies.json"


def apply_institution_policies(
    institutions: list[Institution], path: Path = DEFAULT_POLICY_PATH
) -> list[Institution]:
    """Return institutions enriched by explicitly sourced overrides.

    Unknown schools retain conservative ``unknown`` policy values. Invalid or stale
    configuration fails loudly instead of silently changing recommendations.
    """
    payload = json.loads(path.read_text(encoding="utf-8"))
    overrides = payload.get("institutions", [])
    by_unit_id = {item.get("unit_id"): item for item in overrides if item.get("unit_id")}
    by_name = {item["name"].casefold(): item for item in overrides if item.get("name")}
    enriched: list[Institution] = []
    for institution in institutions:
        override = by_unit_id.get(institution.unit_id) or by_name.get(institution.name.casefold())
        if override is None:
            enriched.append(institution)
            continue
        updates = {key: value for key, value in override.items() if key not in {"unit_id", "name"}}
        enriched.append(Institution.model_validate({**institution.model_dump(), **updates}))
    return enriched
