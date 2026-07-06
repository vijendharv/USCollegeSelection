"""Shared comparable-cost selection for ranking and report generation."""

from __future__ import annotations

from dataclasses import dataclass

from app.models.college import Institution, Ownership
from app.models.preferences import BudgetType
from app.models.student import StudentProfile


@dataclass(frozen=True, slots=True)
class ComparableCost:
    amount: int | None
    label: str


def comparable_cost(
    student: StudentProfile,
    institution: Institution,
    budget_type: BudgetType | None = None,
) -> ComparableCost:
    """Choose one cost consistently, including resident tuition for public schools."""
    selected_type = budget_type or student.preferences.budget_type
    if selected_type is BudgetType.NET_PRICE:
        return ComparableCost(institution.average_net_price, "average net price")
    if selected_type is BudgetType.PUBLISHED_COST:
        if institution.cost_of_attendance is not None:
            return ComparableCost(institution.cost_of_attendance, "cost of attendance")
        in_state = (
            institution.ownership is Ownership.PUBLIC
            and student.preferences.residence_state == institution.state
        )
        tuition = institution.tuition_in_state if in_state else institution.tuition_out_of_state
        return ComparableCost(tuition, "published tuition")
    return ComparableCost(None, "")
