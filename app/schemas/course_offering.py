"""Pydantic schemas for CourseOffering"""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class CourseOfferingSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int | None = None
    course_id: int
    instructor_id: int
    cohort_year: int | None = None
    academic_year: int
    semester: int
    section: str


class CourseOfferingCreateSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    course_id: int
    instructor_id: int
    cohort_year: int | None = None
    academic_year: int
    semester: int
    section: str = "1"


class CourseOfferingUpdateSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    instructor_id: int | None = None
    cohort_year: int | None = None
    academic_year: int | None = None
    semester: int | None = None
    section: str | None = None
