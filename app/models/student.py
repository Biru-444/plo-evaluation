"""Student model"""
from __future__ import annotations

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.services.year_level import current_year_level as _compute_year_level


# นักศึกษา — ไม่มีบัญชี login เป็นของตัวเอง (ต่างจาก User) id คือรหัสนักศึกษาจริง (string ความยาวคงที่
# เช่น "660112230001") ใช้เป็น primary key ตรง ๆ ไม่มี id แยกต่างหาก
class Student(Base):
    __tablename__ = "student"

    id: Mapped[str] = mapped_column(String(15), primary_key=True)
    # ลบหลักสูตรที่ยังมีนักศึกษาอยู่ไม่ได้ (RESTRICT) — ต่างจากตารางอื่นที่ใช้ CASCADE เพราะข้อมูล
    # นักศึกษาสำคัญเกินกว่าจะให้หายไปเงียบ ๆ ตามหลักสูตรที่ถูกลบ
    curriculum_id: Mapped[int] = mapped_column(
        ForeignKey("curriculum.id", ondelete="RESTRICT", onupdate="CASCADE"), nullable=False
    )
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    title: Mapped[str | None] = mapped_column(String(20), nullable=True)
    # สถานะการเป็นนักศึกษา (เช่น "กำลังศึกษา", "จบการศึกษา", "พ้นสภาพ", "ลาพัก") — เป็น free text ไม่ใช่
    # enum ระดับฐานข้อมูล ค่าเริ่มต้น "กำลังศึกษา"
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="กำลังศึกษา")
    # หมู่เรียน (เช่น "01", "02") — คนละความหมายกับ CourseOffering.section (ของวิชา) นี่คือหมู่ของ
    # นักศึกษาทั้งรุ่น ใช้กรองหน้ารายชื่อนักศึกษา
    section: Mapped[str | None] = mapped_column(String(20), nullable=True)
    # ปีที่เข้าเรียน (เช่น 66) — คงที่ตลอดที่เรียน ที่มาเดียวของชั้นปีปัจจุบัน (ดู current_year_level
    # property ด้านล่าง)
    cohort_year: Mapped[int] = mapped_column(Integer, nullable=False)

    curriculum: Mapped["Curriculum"] = relationship(back_populates="students")
    enrollments: Mapped[list["Enrollment"]] = relationship(
        back_populates="student", cascade="all, delete-orphan"
    )
    scores: Mapped[list["StudentScore"]] = relationship(
        back_populates="student", cascade="all, delete-orphan"
    )

    # ชั้นปีที่เรียนอยู่ตอนนี้ - คำนวณสดจาก cohort_year ทุกครั้งที่อ่าน (ไม่เก็บ column แยกอีกต่อไป ดูเหตุผล
    # เต็มใน app/services/year_level.py) ตั้งชื่อ property ตรงกับชื่อ column เดิมโดยตั้งใจ ให้ route/schema
    # เดิมทุกจุดที่เคยอ่าน student.current_year_level (รวมถึง response ผ่าน Pydantic's from_attributes)
    # ทำงานเหมือนเดิมโดยไม่ต้องแก้ - อ่านอย่างเดียว ไม่มี setter (เซ็ตตรงๆ ไม่ได้แล้ว)
    @property
    def current_year_level(self) -> int:
        return _compute_year_level(self.cohort_year).level

    # True ถ้าชั้นปีจริงเกิน 4 (โครงสร้างหลักสูตรมีแค่ 4 ปี) - ฝั่งเรียกใช้ (API response/frontend) ใช้
    # ตัดสินใจแสดง "ปี 4+" แทนเลขจริงที่อาจดูแปลก (เช่น "ปี 7")
    @property
    def beyond_curriculum(self) -> bool:
        return _compute_year_level(self.cohort_year).beyond_curriculum

    def __repr__(self) -> str:
        return f"<Student id={self.id!r} name={self.first_name} {self.last_name}>"
