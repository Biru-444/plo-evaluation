"""Course-PLO relationship model"""
from __future__ import annotations

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class CoursePLO(Base):
    __tablename__ = "course_plo"
    __table_args__ = (UniqueConstraint("course_id", "plo_id"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    course_id: Mapped[int] = mapped_column(
        ForeignKey("course.id", ondelete="CASCADE", onupdate="CASCADE"), nullable=False
    )
    plo_id: Mapped[int] = mapped_column(
        ForeignKey("plo.id", ondelete="CASCADE", onupdate="CASCADE"), nullable=False
    )
    responsibility_level: Mapped[str] = mapped_column(String(20), nullable=False)

    course: Mapped["Course"] = relationship(back_populates="plo_mappings")
    plo: Mapped["PLO"] = relationship(back_populates="course_mappings")

    def __repr__(self) -> str:
        return f"<CoursePLO course_id={self.course_id} plo_id={self.plo_id}>"
