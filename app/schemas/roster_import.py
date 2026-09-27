"""Pydantic schemas for the university Excel roster import feature (`/roster-import`).

ไฟล์ที่มหาวิทยาลัยส่งให้อาจารย์ (.xls รูปแบบเก่า) มีข้อมูลรายวิชา/ภาคเรียน/ผู้สอน/รายชื่อนักศึกษา
ครบในตัว endpoint นี้ parse ไฟล์แล้วจับคู่/สร้างข้อมูลที่เกี่ยวข้องให้อัตโนมัติ รองรับโหมด dry-run
(preview ไม่บันทึกจริง) และโหมด commit (บันทึกจริง) ผ่าน flag เดียวกัน (`dry_run`)
"""
from __future__ import annotations

from pydantic import BaseModel


class RosterImportStudentRow(BaseModel):
    line_no: int
    student_id: str
    title: str | None = None
    first_name: str
    last_name: str
    # "create" = จะสร้าง/สร้างนักศึกษาใหม่, "update_info" = มีอยู่แล้วแต่ชื่อและ/หรือหมู่ในไฟล์ไม่ตรง (จะแก้ตามไฟล์),
    # "unchanged" = มีอยู่แล้วและชื่อ+หมู่ตรงกัน, "error" = ข้าม (เช่น อยู่คนละหลักสูตร)
    action: str
    detail: str | None = None


class RosterImportInstructor(BaseModel):
    full_name: str
    title: str | None = None
    # "matched_existing" = เจอบัญชีเดิมในระบบ, "will_create" = ยังไม่มี (โหมด dry-run),
    # "created" = สร้างบัญชีใหม่แล้ว (โหมด commit)
    action: str
    user_id: int | None = None
    username: str | None = None
    temp_password: str | None = None


class RosterImportResponse(BaseModel):
    dry_run: bool
    course_code: str
    course_name_th: str | None = None
    course_found: bool
    academic_year: int
    semester: int
    section: str
    cohort_year: int | None = None
    offering_id: int | None = None
    # "matched_existing" | "will_create" | "created" | "skipped_no_course" (ไม่พบวิชาในระบบ - นำเข้า
    # เฉพาะรายชื่อนักศึกษา ไม่สร้างวิชา/การเปิดสอน/ลงทะเบียนให้ - ดู needs_curriculum_id ด้านล่าง)
    offering_action: str
    # true = ไม่พบวิชาในระบบ และยังไม่มี/ไม่ได้ระบุ curriculum_id ที่ถูกต้องมาด้วย - frontend ต้องให้ผู้ใช้
    # เลือกหลักสูตรก่อนถึงจะกด "ยืนยันนำเข้าจริง" ได้ (ส่ง curriculum_id กลับมาในคำขอถัดไป ทั้ง dry_run
    # และ commit)
    needs_curriculum_id: bool = False
    instructors: list[RosterImportInstructor] = []
    students: list[RosterImportStudentRow] = []
    enrollments_added: int = 0
    enrollments_already: int = 0
    # summary keys เพิ่มเติมตอน offering_action == "skipped_no_course":
    # "enrollments_skipped_no_course" (จำนวนนักศึกษาที่ไม่ได้ลงทะเบียนเพราะไม่มีวิชาให้ลงทะเบียน)
    summary: dict[str, int] = {}
    new_instructor_credentials: list[dict] = []
    errors: list[str] = []
