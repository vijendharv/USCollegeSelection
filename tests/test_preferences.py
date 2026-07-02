from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.models import BudgetType, StudentPreferences


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
