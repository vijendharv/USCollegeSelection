from __future__ import annotations

from app.costs import comparable_cost
from app.models import BudgetType, Ownership
from tests.test_reporting import school, student


def test_public_in_state_cost_uses_resident_tuition_when_total_cost_is_missing() -> None:
    base = student()
    profile = base.model_copy(
        update={
            "preferences": base.preferences.model_copy(
                update={"budget_type": BudgetType.PUBLISHED_COST, "residence_state": "CA"}
            )
        }
    )
    institution = school(99, "California Public").model_copy(
        update={
            "ownership": Ownership.PUBLIC,
            "state": "CA",
            "cost_of_attendance": None,
            "tuition_in_state": 15_000,
            "tuition_out_of_state": 45_000,
        }
    )

    selected = comparable_cost(profile, institution)

    assert selected.amount == 15_000
    assert selected.label == "published tuition"
