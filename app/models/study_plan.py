"""StudyPlan model"""
from __future__ import annotations

from sqlalchemy import ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class StudyPlan(Base):
    __tablename__ = "study_plan"
    __table_args__ = (UniqueConstraint("curriculum_id", "course_id", "cohort_year"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    curriculum_id: Mapped[int] = mapped_column(
        ForeignKey("curriculum.id", ondelete="CASCADE", onupdate="CASCADE"), nullable=False
    )
    course_id: Mapped[int] = mapped_column(
        ForeignKey("course.id", ondelete="CASCADE", onupdate="CASCADE"), nullable=False
    )
    cohort_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    year_level: Mapped[int] = mapped_column(Integer, nullable=False)
    semester: Mapped[int] = mapped_column(Integer, nullable=False)

    curriculum: Mapped["Curriculum"] = relationship(back_populates="study_plans")
    course: Mapped["Course"] = relationship(back_populates="study_plans")

    def __repr__(self) -> str:
        return f"<StudyPlan id={self.id} course_id={self.course_id} year_level={self.year_level}>"
