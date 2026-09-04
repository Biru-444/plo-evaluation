"""Pydantic schemas for Student"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

StudentStatus = Literal["กำลังศึกษา", "ลาออก", "พักการเรียน", "จบการศึกษา"]


class StudentSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str | None = None
    curriculum_id: int
    first_name: str
    last_name: str
    title: str | None = None
    status: StudentStatus = "กำลังศึกษา"
    section: str | None = None
    cohort_year: int
    current_year_level: int


class EnrolledStudentSchema(StudentSchema):
    """StudentSchema + clo_mastery_percent (0-100) - เฉพาะ GET /courses/{course_id}/enrolled-students
    เมื่อมี query param plo_id ส่งมา (ดู courses.py) เป็น None เสมอเมื่อไม่ได้ส่ง plo_id หรือเมื่อวิชานี้
    ไม่มี CLO ผูกกับ PLO ข้อนั้นเลย/นักศึกษาคนนี้ยังไม่มีคะแนนให้ CLO ไหนของวิชานี้เลย"""

    clo_mastery_percent: float | None = None


class StudentCreateSchema(BaseModel):
    """`id` (student code) has no DB default/sequence, so unlike other
    create schemas it must be supplied by the client rather than omitted."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(..., max_length=15)
    curriculum_id: int
    first_name: str
    last_name: str
    title: str | None = None
    status: StudentStatus = "กำลังศึกษา"
    section: str | None = None
    cohort_year: int
    current_year_level: int


class StudentUpdateSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    first_name: str | None = None
    last_name: str | None = None
    title: str | None = None
    status: StudentStatus | None = None
    section: str | None = None
    cohort_year: int | None = None
    current_year_level: int | None = None
