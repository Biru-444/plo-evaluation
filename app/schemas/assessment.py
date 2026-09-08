"""Pydantic schemas for AssessmentItem and StudentScore"""
from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


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
    # จำนวนเต็มเท่านั้น (ไม่มีทศนิยม) - ต้องมากกว่า 0
    total_score: int = Field(gt=0)


class AssessmentItemUpdateSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str | None = None
    type: str | None = None
    total_score: int | None = Field(default=None, gt=0)


class StudentScoreSchema(BaseModel):
    """Used for responses only (list/create/update) - Decimal so any
    pre-existing fractional score still serializes fine. New writes go
    through StudentScoreCreateSchema / StudentScoreUpdateSchema below,
    which are int-only."""

    model_config = ConfigDict(from_attributes=True)

    id: int | None = None
    item_id: int
    student_id: str
    score_obtained: Decimal


class StudentScoreCreateSchema(BaseModel):
    item_id: int
    student_id: str
    # จำนวนเต็มเท่านั้น - ห้ามติดลบ (เกินคะแนนเต็มของชิ้นงานเช็คแยกใน route เพราะต้องรู้ total_score
    # ของ item ก่อน)
    score_obtained: int = Field(ge=0)


class StudentScoreDetailSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    item_id: int
    item_name: str
    total_score: Decimal
    student_id: str
    score_obtained: Decimal


class StudentScoreUpdateSchema(BaseModel):
    score_obtained: int = Field(ge=0)
