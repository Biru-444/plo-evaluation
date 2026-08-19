"""Course model"""
from __future__ import annotations

from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Course(Base):
    __tablename__ = "course"
    __table_args__ = (UniqueConstraint("curriculum_id", "course_code"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    curriculum_id: Mapped[int] = mapped_column(
        ForeignKey("curriculum.id", ondelete="CASCADE", onupdate="CASCADE"), nullable=False
    )
    course_code: Mapped[str] = mapped_column(String(20), nullable=False)
    name_th: Mapped[str] = mapped_column(String(255), nullable=False)
    name_en: Mapped[str | None] = mapped_column(String(255), nullable=True)
    credit: Mapped[int] = mapped_column(Integer, nullable=False)
    category: Mapped[str | None] = mapped_column(String(100), nullable=True)

    curriculum: Mapped["Curriculum"] = relationship(back_populates="courses")
    plo_mappings: Mapped[list["CoursePLO"]] = relationship(
        back_populates="course", cascade="all, delete-orphan"
    )
    study_plans: Mapped[list["StudyPlan"]] = relationship(
        back_populates="course", cascade="all, delete-orphan"
    )
    offerings: Mapped[list["CourseOffering"]] = relationship(
        back_populates="course", cascade="all, delete-orphan"
    )
    clos: Mapped[list["CLO"]] = relationship(back_populates="course", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Course id={self.id} course_code={self.course_code!r}>"
