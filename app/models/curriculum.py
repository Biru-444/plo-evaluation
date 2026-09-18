"""Curriculum model"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


# หลักสูตร (เช่น "วิศวกรรมคอมพิวเตอร์ 2566") — เป็นตารางแม่ที่ PLO, YLO, Course, Student,
# StudyPlan ทุกตัวต้องผูกกับหลักสูตรใดหลักสูตรหนึ่งเสมอ
class Curriculum(Base):
    __tablename__ = "curriculum"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    # ปี พ.ศ. ที่หลักสูตรนี้เริ่มใช้ (เช่น 2566) — ไม่ใช่ปีที่นักศึกษาเข้าเรียน (ดู Student.cohort_year)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )

    # cascade="all, delete-orphan" บนทุก relationship ด้านล่าง (ยกเว้น students) หมายความว่า ลบ
    # Curriculum แล้ว PLO/YLO/Course/StudyPlan ของหลักสูตรนั้นจะถูกลบตามไปด้วยอัตโนมัติ
    plos: Mapped[list["PLO"]] = relationship(back_populates="curriculum", cascade="all, delete-orphan")
    ylos: Mapped[list["YLO"]] = relationship(back_populates="curriculum", cascade="all, delete-orphan")
    courses: Mapped[list["Course"]] = relationship(back_populates="curriculum", cascade="all, delete-orphan")
    # ไม่มี cascade delete-orphan ตรงนี้โดยตั้งใจ (ต่างจากอันอื่น) — Student.curriculum_id ใช้
    # ondelete="RESTRICT" (ดู student.py) กันการลบหลักสูตรที่ยังมีนักศึกษาอยู่โดยไม่ได้ตั้งใจ
    students: Mapped[list["Student"]] = relationship(back_populates="curriculum")
    study_plans: Mapped[list["StudyPlan"]] = relationship(
        back_populates="curriculum", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Curriculum id={self.id} name={self.name!r} year={self.year}>"
