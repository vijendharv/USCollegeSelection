"""Student college-search preferences."""

from __future__ import annotations

from decimal import Decimal
from enum import StrEnum
from typing import Annotated

from pydantic import Field, StringConstraints, field_validator, model_validator

from app.models.base import DomainModel

PreferenceText = Annotated[str, StringConstraints(min_length=1, max_length=120)]

_US_STATES = {
    "AL",
    "AK",
    "AZ",
    "AR",
    "CA",
    "CO",
    "CT",
    "DE",
    "FL",
    "GA",
    "HI",
    "ID",
    "IL",
    "IN",
    "IA",
    "KS",
    "KY",
    "LA",
    "ME",
    "MD",
    "MA",
    "MI",
    "MN",
    "MS",
    "MO",
    "MT",
    "NE",
    "NV",
    "NH",
    "NJ",
    "NM",
    "NY",
    "NC",
    "ND",
    "OH",
    "OK",
    "OR",
    "PA",
    "RI",
    "SC",
    "SD",
    "TN",
    "TX",
    "UT",
    "VT",
    "VA",
    "WA",
    "WV",
    "WI",
    "WY",
    "DC",
}


class EntryTerm(StrEnum):
    FALL = "fall"
    SPRING = "spring"
    SUMMER = "summer"
    OTHER = "other"


class BudgetType(StrEnum):
    NET_PRICE = "net_price"
    OUT_OF_POCKET = "out_of_pocket"
    PUBLISHED_COST = "published_cost"


class TestSubmissionPlan(StrEnum):
    SUBMIT = "submit"
    DO_NOT_SUBMIT = "do_not_submit"
    UNDECIDED = "undecided"


class StudentPreferences(DomainModel):
    """Preferences are partial while the user builds the profile."""

    residence_state: str | None = None
    intended_entry_year: int | None = Field(default=None, ge=2020, le=2200)
    intended_entry_term: EntryTerm | None = None
    intended_majors: list[PreferenceText] = Field(default_factory=list, max_length=3)
    annual_budget: Decimal | None = Field(default=None, ge=0)
    budget_type: BudgetType | None = None
    preferred_states: list[str] = Field(default_factory=list)
    excluded_states: list[str] = Field(default_factory=list)
    existing_schools: list[PreferenceText] = Field(default_factory=list)
    test_submission_plan: TestSubmissionPlan = TestSubmissionPlan.UNDECIDED

    @field_validator("residence_state")
    @classmethod
    def validate_optional_state(cls, value: str | None) -> str | None:
        return cls._validate_state(value) if value is not None else None

    @field_validator("preferred_states", "excluded_states")
    @classmethod
    def validate_state_lists(cls, values: list[str]) -> list[str]:
        return cls._unique([cls._validate_state(value) for value in values])

    @field_validator("intended_majors", "existing_schools")
    @classmethod
    def deduplicate_text_lists(cls, values: list[str]) -> list[str]:
        return cls._unique(values)

    @model_validator(mode="after")
    def validate_budget_and_geography(self) -> StudentPreferences:
        if self.annual_budget is not None and self.budget_type is None:
            raise ValueError("budget_type is required when annual_budget is provided")
        overlap = set(self.preferred_states) & set(self.excluded_states)
        if overlap:
            raise ValueError(f"states cannot be both preferred and excluded: {sorted(overlap)}")
        return self

    @staticmethod
    def _validate_state(value: str) -> str:
        state = value.strip().upper()
        if state not in _US_STATES:
            raise ValueError(f"unknown US state code: {value}")
        return state

    @staticmethod
    def _unique(values: list[str]) -> list[str]:
        seen: set[str] = set()
        result: list[str] = []
        for value in values:
            key = value.casefold()
            if key not in seen:
                seen.add(key)
                result.append(value)
        return result
