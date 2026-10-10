"""Contrats HTTP des opérations 2D ; la logique métier vit dans pipeline."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator

_BRIEF_MAX_LEN = 4000
_IMAGE_B64_MAX_LEN = 16 * 1024 * 1024


class PipelineRequest(BaseModel):
    brief: str = Field(max_length=_BRIEF_MAX_LEN)
    constraints: dict[str, Any] = Field(default_factory=dict)
    job_id: str | None = None

    @field_validator("constraints", mode="before")
    @classmethod
    def _constraints_none_as_empty(cls, value: Any) -> Any:
        return {} if value is None else value


class AdaptRequest(BaseModel):
    plan_document: dict[str, Any]
    parcel: dict[str, Any] = Field(default_factory=dict)
    rules: dict[str, Any] = Field(default_factory=dict)


class DevisRequest(BaseModel):
    brief: str = Field(default="", max_length=_BRIEF_MAX_LEN)
    building_spec: dict[str, Any] = Field(default_factory=dict)
    plan_document: dict[str, Any] = Field(default_factory=dict)
    constraints: dict[str, Any] = Field(default_factory=dict)

    @field_validator("building_spec", "plan_document", "constraints", mode="before")
    @classmethod
    def _none_as_empty(cls, value: Any) -> Any:
        return {} if value is None else value


class EditRequest(BaseModel):
    instruction: str = Field(max_length=_BRIEF_MAX_LEN)
    brief: str = Field(default="", max_length=_BRIEF_MAX_LEN)
    constraints: dict[str, Any] = Field(default_factory=dict)
    building_spec: dict[str, Any] = Field(default_factory=dict)
    plan_document: dict[str, Any] = Field(default_factory=dict)
    image_png_b64: str = Field(default="", max_length=_IMAGE_B64_MAX_LEN)
    job_id: str | None = None

    @field_validator("constraints", "building_spec", "plan_document", mode="before")
    @classmethod
    def _edit_none_as_empty(cls, value: Any) -> Any:
        return {} if value is None else value
