"""StudyPlan model"""
from __future__ import annotations

from sqlalchemy import ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


# แผนการศึกษา — กำหนดว่าวิชาหนึ่ง ๆ ถูกจัดสอนชั้นปีไหน เทอมไหน ของหลักสูตรนั้น ใช้ตอบคำถาม "ปีนี้
# เรียนอะไรบ้าง" และเป็นส่วนหนึ่งของเงื่อนไขตัดสิน "วิชานี้เกี่ยวกับ YLO ปีไหน" (ดู ylo_calculation.py)
class StudyPlan(Base):
    __tablename__ = "study_plan"
    # วิชาเดียวกันปรากฏซ้ำได้ถ้า cohort_year ต่างกัน (แผนมาตรฐานกับแผนเฉพาะรุ่น) แต่ต้องไม่ซ้ำ
    # ครบทั้ง 3 ค่านี้พร้อมกัน
    __table_args__ = (UniqueConstraint("curriculum_id", "course_id", "cohort_year"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    curriculum_id: Mapped[int] = mapped_column(
        ForeignKey("curriculum.id", ondelete="CASCADE", onupdate="CASCADE"), nullable=False
    )
    course_id: Mapped[int] = mapped_column(
        ForeignKey("course.id", ondelete="CASCADE", onupdate="CASCADE"), nullable=False
    )
    # None = แผนมาตรฐาน (ใช้กับทุกรุ่นที่ไม่มีแผนเฉพาะของตัวเอง) ใส่ปีรุ่น (เช่น 66) = แผนเฉพาะรุ่นนั้น
    # ที่จะ "ชนะ" แผนมาตรฐานถ้ามีอยู่จริง (ดู _study_plan_course_ids ใน ylo_calculation.py) ข้อมูลจริง
    # ในระบบตอนนี้มีแต่แผนมาตรฐานเท่านั้น
    cohort_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    year_level: Mapped[int] = mapped_column(Integer, nullable=False)
    semester: Mapped[int] = mapped_column(Integer, nullable=False)

    curriculum: Mapped["Curriculum"] = relationship(back_populates="study_plans")
    course: Mapped["Course"] = relationship(back_populates="study_plans")

    def __repr__(self) -> str:
        return f"<StudyPlan id={self.id} course_id={self.course_id} year_level={self.year_level}>"
