"""Enrollment model"""
from __future__ import annotations

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Enrollment(Base):
    __tablename__ = "enrollment"
    __table_args__ = (UniqueConstraint("student_id", "offering_id"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    student_id: Mapped[str] = mapped_column(
        String(15), ForeignKey("student.id", ondelete="CASCADE", onupdate="CASCADE"), nullable=False
    )
    offering_id: Mapped[int] = mapped_column(
        ForeignKey("course_offering.id", ondelete="CASCADE", onupdate="CASCADE"), nullable=False
    )
    final_grade: Mapped[str | None] = mapped_column(String(5), nullable=True)

    student: Mapped["Student"] = relationship(back_populates="enrollments")
    offering: Mapped["CourseOffering"] = relationship(back_populates="enrollments")

    def __repr__(self) -> str:
        return f"<Enrollment id={self.id} student_id={self.student_id!r} offering_id={self.offering_id}>"
