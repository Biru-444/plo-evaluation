"""CourseOffering model"""
from __future__ import annotations

from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


# การเปิดสอนจริงของวิชาหนึ่ง ๆ ในปีการศึกษา/เทอม/กลุ่มเรียน (section) หนึ่ง — คะแนนสอบ, การลงทะเบียน,
# ชิ้นงานประเมิน (assessment_item) ทั้งหมดผูกกับ offering นี้ ไม่ใช่ผูกกับ Course ตรง ๆ เพราะวิชาเดียวกัน
# เปิดสอนได้หลายรอบ/หลาย section และแต่ละรอบมีคะแนน/ผู้สอนของตัวเอง
class CourseOffering(Base):
    __tablename__ = "course_offering"
    # วิชาเดียวกัน ปีเดียวกัน เทอมเดียวกัน section เดียวกัน เปิดซ้ำไม่ได้
    __table_args__ = (
        UniqueConstraint("course_id", "academic_year", "semester", "section"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    course_id: Mapped[int] = mapped_column(
        ForeignKey("course.id", ondelete="CASCADE", onupdate="CASCADE"), nullable=False
    )
    # nullable=True: วิชาที่เปิดสอนแต่ยังไม่มีผู้สอน (เช่น เพิ่งเปิดวิชาใหม่ หรือแอดมินปล่อยว่างไว้ตั้งใจ
    # รอแอดมินมอบหมายผู้สอนทีหลัง)
    instructor_id: Mapped[int | None] = mapped_column(
        ForeignKey("user.id", ondelete="RESTRICT", onupdate="CASCADE"), nullable=True
    )
    # รุ่นนักศึกษาที่ offering นี้จัดไว้ให้โดยเฉพาะ (เช่น 66) — None = เปิดกว้างไม่ผูกรุ่นใดรุ่นหนึ่ง
    cohort_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    academic_year: Mapped[int] = mapped_column(Integer, nullable=False)
    semester: Mapped[int] = mapped_column(Integer, nullable=False)
    # กลุ่มเรียน (เช่น "01", "02") — ค่าเริ่มต้น "1" ถ้าวิชานั้นเปิดสอนกลุ่มเดียว
    section: Mapped[str] = mapped_column(String(10), nullable=False, server_default="1")

    course: Mapped["Course"] = relationship(back_populates="offerings")
    instructor: Mapped["User"] = relationship(
        back_populates="course_offerings", foreign_keys=[instructor_id]
    )
    # นักศึกษาที่ลงทะเบียนเรียน offering นี้
    enrollments: Mapped[list["Enrollment"]] = relationship(
        back_populates="offering", cascade="all, delete-orphan"
    )
    # ชิ้นงาน/ข้อสอบที่ใช้ประเมินใน offering นี้ (แต่ละชิ้นผูกกับ CLO ผ่านตาราง item_clo)
    assessment_items: Mapped[list["AssessmentItem"]] = relationship(
        back_populates="offering", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<CourseOffering id={self.id} course_id={self.course_id} section={self.section!r}>"
