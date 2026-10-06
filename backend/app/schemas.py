from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class LoginRequest(_Strict):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=128)

    @field_validator("email")
    @classmethod
    def _lower(cls, value: str) -> str:
        return value.lower()


class CondonationCreate(_Strict):
    reason: str = Field(min_length=20, max_length=2000)
    subject_id: int | None = Field(default=None, gt=0)


class CondonationDecision(_Strict):
    decision: Literal["APPROVED", "REJECTED"]
    comment: str | None = Field(default=None, max_length=1000)
