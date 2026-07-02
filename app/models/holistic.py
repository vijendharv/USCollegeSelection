"""Confirmed activity and résumé context supplied by the student."""

from __future__ import annotations

from decimal import Decimal

from pydantic import Field

from app.models.base import DomainModel


class Activity(DomainModel):
    """One confirmed activity; no impact or selectivity is inferred."""

    name: str
    organization: str | None = None
    role: str | None = None
    description: str | None = None
    duration: str | None = None
    hours_per_week: Decimal | None = Field(default=None, ge=0, le=168)
    honors: list[str] = Field(default_factory=list)
    themes: list[str] = Field(default_factory=list)


class HolisticProfile(DomainModel):
    """Reviewable themes and facts confirmed from a résumé or manual entry."""

    themes: list[str] = Field(default_factory=list)
    activities: list[Activity] = Field(default_factory=list)
