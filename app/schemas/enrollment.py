"""Pydantic schemas for Enrollment"""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class EnrollmentSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int | None = None
    student_id: str
    offering_id: int
    final_grade: str | None = None


class EnrollmentCreateSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    student_id: str
    offering_id: int
    final_grade: str | None = None


class EnrollmentUpdateSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    final_grade: str | None = None


class BulkEnrollByCohortSchema(BaseModel):
    offering_id: int
    cohort_year: int


class BulkEnrollSchema(BaseModel):
    offering_id: int
    student_ids: list[str]


class EnrolledStudentBrief(BaseModel):
    id: str
    first_name: str
    last_name: str


class OtherSectionConflict(BaseModel):
    student_id: str
    section: str


class BulkEnrollByCohortResult(BaseModel):
    added_count: int
    already_enrolled_count: int
    added_students: list[EnrolledStudentBrief]
    already_in_other_section: list[OtherSectionConflict] = []


class BulkEnrollResult(BaseModel):
    added_count: int
    already_enrolled: list[str]
    not_found: list[str]
    wrong_curriculum: list[str] = []
    already_in_other_section: list[OtherSectionConflict] = []
