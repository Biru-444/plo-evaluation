"""CourseOffering model"""
from __future__ import annotations

from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class CourseOffering(Base):
    __tablename__ = "course_offering"
    __table_args__ = (
        UniqueConstraint("course_id", "academic_year", "semester", "section"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    course_id: Mapped[int] = mapped_column(
        ForeignKey("course.id", ondelete="CASCADE", onupdate="CASCADE"), nullable=False
    )
    instructor_id: Mapped[int] = mapped_column(
        ForeignKey("user.id", ondelete="RESTRICT", onupdate="CASCADE"), nullable=False
    )
    cohort_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    academic_year: Mapped[int] = mapped_column(Integer, nullable=False)
    semester: Mapped[int] = mapped_column(Integer, nullable=False)
    section: Mapped[str] = mapped_column(String(10), nullable=False, server_default="1")

    course: Mapped["Course"] = relationship(back_populates="offerings")
    instructor: Mapped["User"] = relationship(
        back_populates="course_offerings", foreign_keys=[instructor_id]
    )
    enrollments: Mapped[list["Enrollment"]] = relationship(
        back_populates="offering", cascade="all, delete-orphan"
    )
    assessment_items: Mapped[list["AssessmentItem"]] = relationship(
        back_populates="offering", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<CourseOffering id={self.id} course_id={self.course_id} section={self.section!r}>"
