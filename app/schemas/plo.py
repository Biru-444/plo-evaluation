"""Pydantic schemas for PLO"""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class PLOSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int | None = None
    curriculum_id: int
    code: str
    description_th: str
    description_en: str | None = None


class PLOCreateSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    curriculum_id: int
    code: str
    description_th: str
    description_en: str | None = None
