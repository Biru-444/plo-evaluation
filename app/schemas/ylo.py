"""Pydantic schemas for YLO"""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class YLOSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int | None = None
    curriculum_id: int
    year_level: int
    description: str


class YLOCreateSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    curriculum_id: int
    year_level: int
    description: str


class YLOUpdateSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    year_level: int | None = None
    description: str | None = None
