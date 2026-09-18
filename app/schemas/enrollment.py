"""Pydantic schemas for Enrollment — EnrollmentSchema/Create/Update สามตัวแรกคือ CRUD ปกติ (field
ตรงกับ app/models/enrollment.py) ที่เหลือด้านล่างเป็น schema เฉพาะทางสำหรับฟีเจอร์ลงทะเบียนแบบกลุ่ม
(bulk enroll/remove) ที่ endpoint ใน app/routes/enrollment.py ใช้"""
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


# request : ลงทะเบียนนักศึกษาทั้งรุ่น (cohort_year) เข้า offering เดียวในครั้งเดียว
class BulkEnrollByCohortSchema(BaseModel):
    offering_id: int
    cohort_year: int


# request : ลงทะเบียนนักศึกษาตามรายชื่อ (student_ids) ที่เลือกเองเข้า offering เดียว
class BulkEnrollSchema(BaseModel):
    offering_id: int
    student_ids: list[str]


# ข้อมูลย่อของนักศึกษา 1 คน ใช้แสดงในผลลัพธ์ bulk enroll/remove (ไม่ต้องส่งข้อมูลเต็มแบบ StudentSchema)
class EnrolledStudentBrief(BaseModel):
    id: str
    first_name: str
    last_name: str


# นักศึกษาที่ข้ามไปตอน bulk enroll เพราะลงทะเบียนวิชานี้ไว้แล้วใน section อื่น (กันลงทะเบียนซ้ำวิชา
# เดียวกันคนละ section)
class OtherSectionConflict(BaseModel):
    student_id: str
    section: str


# response ของ bulk-enroll-by-cohort — สรุปว่าเพิ่มกี่คน ลงแล้วกี่คน ใครถูกข้ามเพราะ section ชนกัน
class BulkEnrollByCohortResult(BaseModel):
    added_count: int
    already_enrolled_count: int
    added_students: list[EnrolledStudentBrief]
    already_in_other_section: list[OtherSectionConflict] = []


# response ของ bulk-remove-by-cohort — ถอนนักศึกษาทั้งรุ่นออกจาก offering ในครั้งเดียว
class BulkRemoveByCohortResult(BaseModel):
    removed_count: int
    removed_students: list[EnrolledStudentBrief]


# response ของ bulk-enroll แบบเลือกรายชื่อเอง — แยกแจกแจงเหตุผลที่บางคนไม่ถูกเพิ่ม (ไม่พบรหัส,
# คนละหลักสูตร, ลงทะเบียนไปแล้ว, หรือชน section อื่น)
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
