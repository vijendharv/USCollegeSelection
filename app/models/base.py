"""Shared configuration for domain models."""

from pydantic import BaseModel, ConfigDict


class DomainModel(BaseModel):
    """Strict model that rejects accidental fields and trims strings."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
    )
