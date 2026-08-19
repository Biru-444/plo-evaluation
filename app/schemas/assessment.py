"""Pydantic schemas for AssessmentItem and StudentScore"""
from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class AssessmentItemSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int | None = None
    offering_id: int
    name: str
    type: str
    total_score: Decimal


class AssessmentCreateSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    offering_id: int
    name: str
    type: str
    total_score: Decimal


class StudentScoreSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int | None = None
    item_id: int
    student_id: str
    score_obtained: Decimal
