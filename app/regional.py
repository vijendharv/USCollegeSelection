"""Transparent state-aware baseline schools evaluated alongside generated recommendations."""

from __future__ import annotations

_BASELINES: dict[str, set[str]] = {
    "WA": {
        "University of Washington-Seattle Campus",
        "Washington State University",
        "Western Washington University",
        "Central Washington University",
        "Eastern Washington University",
    }
}


def is_regional_baseline(residence_state: str | None, institution_name: str) -> bool:
    return institution_name in _BASELINES.get(residence_state or "", set())
