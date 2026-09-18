"""Course model"""
from __future__ import annotations

from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


# รายวิชาตามหลักสูตร (เช่น "01204211 โครงสร้างข้อมูล") — เป็นแม่แบบของวิชา ไม่ใช่การเปิดสอนจริงในเทอม
# ใดเทอมหนึ่ง (ดู CourseOffering สำหรับ "การเปิดสอนจริง")
class Course(Base):
    __tablename__ = "course"
    # รหัสวิชา (course_code) ต้องไม่ซ้ำกันภายในหลักสูตรเดียวกัน
    __table_args__ = (UniqueConstraint("curriculum_id", "course_code"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    curriculum_id: Mapped[int] = mapped_column(
        ForeignKey("curriculum.id", ondelete="CASCADE", onupdate="CASCADE"), nullable=False
    )
    course_code: Mapped[str] = mapped_column(String(20), nullable=False)
    name_th: Mapped[str] = mapped_column(String(255), nullable=False)
    name_en: Mapped[str | None] = mapped_column(String(255), nullable=True)
    credit: Mapped[int] = mapped_column(Integer, nullable=False)
    # หมวดวิชา (เช่น "วิชาเฉพาะบังคับ", "วิชาศึกษาทั่วไป") — เป็น free text แสดงผลอย่างเดียว ไม่มีผลต่อ
    # การคำนวณ PLO/YLO ใด ๆ (ตัวที่มีผลจริงคือ course_plo.responsibility_level)
    category: Mapped[str | None] = mapped_column(String(100), nullable=True)

    curriculum: Mapped["Curriculum"] = relationship(back_populates="courses")
    # PLO ที่วิชานี้ถูก map ไว้ (ผ่าน course_plo) พร้อมระดับความรับผิดชอบ (primary/secondary)
    plo_mappings: Mapped[list["CoursePLO"]] = relationship(
        back_populates="course", cascade="all, delete-orphan"
    )
    # แผนการศึกษาที่กำหนดว่าวิชานี้สอนชั้นปี/เทอมไหน (อาจมีหลายแถวถ้ามีแผนเฉพาะบางรุ่น)
    study_plans: Mapped[list["StudyPlan"]] = relationship(
        back_populates="course", cascade="all, delete-orphan"
    )
    # การเปิดสอนจริงของวิชานี้ในแต่ละปีการศึกษา/เทอม/section (1 วิชาเปิดได้หลาย offering)
    offerings: Mapped[list["CourseOffering"]] = relationship(
        back_populates="course", cascade="all, delete-orphan"
    )
    # CLO (ผลลัพธ์การเรียนรู้ระดับวิชา) ทั้งหมดของวิชานี้
    clos: Mapped[list["CLO"]] = relationship(back_populates="course", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Course id={self.id} course_code={self.course_code!r}>"
