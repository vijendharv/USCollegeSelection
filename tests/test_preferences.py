from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.models import (
    BudgetType,
    HolisticProfile,
    HolisticReviewStatus,
    RecommendationSettings,
    StudentPreferences,
    ThresholdMode,
)


def test_preferences_normalize_states_and_remove_duplicates() -> None:
    preferences = StudentPreferences(
        residence_state="ca",
        intended_majors=["Computer Science", "computer science", "Mathematics"],
        preferred_states=["ca", "WA", "ca"],
    )

    assert preferences.residence_state == "CA"
    assert preferences.intended_majors == ["Computer Science", "Mathematics"]
    assert preferences.preferred_states == ["CA", "WA"]


def test_budget_requires_a_budget_type() -> None:
    with pytest.raises(ValidationError, match="budget_type"):
        StudentPreferences(annual_budget=50_000)


def test_budget_with_type_is_valid() -> None:
    preferences = StudentPreferences(annual_budget=50_000, budget_type=BudgetType.NET_PRICE)

    assert preferences.annual_budget == 50_000


def test_state_cannot_be_preferred_and_excluded() -> None:
    with pytest.raises(ValidationError, match="both preferred and excluded"):
        StudentPreferences(preferred_states=["CA"], excluded_states=["ca"])


def test_no_more_than_three_intended_majors_are_accepted() -> None:
    with pytest.raises(ValueError, match="at most 3 items"):
        StudentPreferences(intended_majors=["Biology", "Chemistry", "Physics", "Mathematics"])


def test_recommendation_settings_default_to_adaptive_80_to_70() -> None:
    settings = StudentPreferences().recommendation_settings

    assert settings.threshold_mode is ThresholdMode.ADAPTIVE
    assert settings.initial_fit_threshold == 80
    assert settings.adaptive_floor == 70
    assert settings.minimum_results_per_category == 5
    assert settings.maximum_results_per_category == 10


def test_holistic_evidence_defaults_to_needs_review() -> None:
    assert HolisticProfile().review_status is HolisticReviewStatus.NEEDS_REVIEW


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"initial_fit_threshold": 70, "adaptive_floor": 80}, "adaptive_floor"),
        (
            {"minimum_results_per_category": 8, "maximum_results_per_category": 5},
            "minimum_results_per_category",
        ),
    ],
)
def test_recommendation_settings_reject_invalid_ranges(
    overrides: dict[str, int], message: str
) -> None:
    with pytest.raises(ValidationError, match=message):
        RecommendationSettings(**overrides)
