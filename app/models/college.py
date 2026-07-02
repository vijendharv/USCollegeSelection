"""Public college data returned by the storage layer."""

from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum

from pydantic import Field

from app.models.base import DomainModel


class Ownership(StrEnum):
    PUBLIC = "public"
    PRIVATE_NONPROFIT = "private_nonprofit"
    PRIVATE_FOR_PROFIT = "private_for_profit"
    UNKNOWN = "unknown"


class Institution(DomainModel):
    unit_id: int
    name: str
    city: str
    state: str
    postal_code: str | None = None
    website: str | None = None
    net_price_calculator_url: str | None = None
    ownership: Ownership = Ownership.UNKNOWN
    main_campus: bool
    predominant_degree: int | None = None
    highest_degree: int
    online_only: bool | None = None
    undergraduate_enrollment: int | None = None
    latitude: float | None = None
    longitude: float | None = None
    acceptance_rate: float | None = None
    sat_reading_25: int | None = None
    sat_reading_75: int | None = None
    sat_math_25: int | None = None
    sat_math_75: int | None = None
    sat_average: int | None = None
    act_composite_25: int | None = None
    act_composite_75: int | None = None
    tuition_in_state: int | None = None
    tuition_out_of_state: int | None = None
    cost_of_attendance: int | None = None
    average_net_price: int | None = None
    graduation_rate: float | None = None
    retention_rate: float | None = None
    median_earnings_10_years: int | None = None
    dataset_version_id: str


class ProgramOffering(DomainModel):
    """A broad two-digit CIP program family reported by College Scorecard."""

    unit_id: int
    cip_code: str
    cip_title: str
    share_of_awards: float = Field(ge=0, le=1)
    dataset_version_id: str


class InstitutionFilters(DomainModel):
    name_contains: str | None = None
    states: list[str] = Field(default_factory=list)
    ownership: list[Ownership] = Field(default_factory=list)
    maximum_tuition: int | None = Field(default=None, ge=0)
    minimum_acceptance_rate: float | None = Field(default=None, ge=0, le=1)
    limit: int = Field(default=25, ge=1, le=100)
    offset: int = Field(default=0, ge=0)


class DatasetVersion(DomainModel):
    version_id: str
    source_name: str
    source_url: str
    archive_member: str
    release_date: date | None = None
    retrieved_at: datetime
    sha256: str
    raw_row_count: int
    eligible_row_count: int
    schema_version: int


class RefreshReport(DomainModel):
    database_path: str
    dataset: DatasetVersion
