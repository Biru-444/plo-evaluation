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


class BulkRemoveByCohortResult(BaseModel):
    removed_count: int
    removed_students: list[EnrolledStudentBrief]


class BulkEnrollResult(BaseModel):
    added_count: int
    already_enrolled: list[str]
    not_found: list[str]
    wrong_curriculum: list[str] = []
    already_in_other_section: list[OtherSectionConflict] = []


class RecommendedOfferingSchema(BaseModel):
    """วิชาที่ study_plan แนะนำสำหรับนักศึกษาคนนี้ (year_level <= current_year_level) และมี
    course_offering จริงรองรับแล้ว แต่ยังไม่ได้ลงทะเบียน - ใช้เป็น "คำแนะนำ" กดเลือกในหน้าลงทะเบียน
    ด้วยตนเอง ไม่ auto-enroll (ดู _build_recommended_offerings ใน routes/students.py)"""

    offering_id: int
    course_id: int
    course_code: str
    name_th: str
    academic_year: int
    semester: int
    section: str
    year_level: int
