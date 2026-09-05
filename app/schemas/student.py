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
    """StudentSchema + offering_id + plo_achieved - เฉพาะ GET /courses/{course_id}/enrolled-students
    (ดู courses.py)

    offering_id: course_offering ที่ใช้อ้างอิงคำนวณ (เช่น เรียก GET /clo-achievement?offering_id=...
    ต่อ) ถ้านักศึกษาคนนี้ลงทะเบียนวิชานี้มากกว่า 1 offering จะเลือก enrollment ล่าสุด (Enrollment.id
    มากสุด) มาให้ - เป็นการลดรูปที่ตั้งใจ (ดูคอมเมนต์ใน courses.py) เพราะข้อมูลจริงปัจจุบันไม่มีเคส
    "1 คนหลาย offering ของวิชาเดียวกัน" เลยสักคน

    plo_achieved (ผ่าน/ไม่ผ่าน) - มีค่าเฉพาะเมื่อมี query param plo_id ส่งมา None ("ยังไม่มีข้อมูลให้
    ประเมิน") ใน 2 กรณี: ไม่ได้ส่ง plo_id เลย, หรือส่งมาแต่วิชานี้ไม่มี CLO ผูกกับ PLO ข้อนั้นเลย/
    นักศึกษาคนนี้ยังไม่มี record คะแนนบันทึกไว้เลยสักรายการสำหรับ CLO ที่เกี่ยวข้อง (ต่างจากได้คะแนน 0
    จริงซึ่งนับเป็นข้อมูลแล้ว) - False เกิดเฉพาะเมื่อมี record คะแนนอยู่แล้วอย่างน้อย 1 รายการ แล้ว
    คำนวณตามเกณฑ์ผ่านแล้วไม่ถึง (all-or-nothing ต่อ CLO)"""

    offering_id: int
    plo_achieved: bool | None = None


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
