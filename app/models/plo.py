"""PLO (Program Learning Outcome) model"""
from __future__ import annotations

from sqlalchemy import ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class PLO(Base):
    __tablename__ = "plo"
    __table_args__ = (UniqueConstraint("curriculum_id", "code"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    curriculum_id: Mapped[int] = mapped_column(
        ForeignKey("curriculum.id", ondelete="CASCADE", onupdate="CASCADE"), nullable=False
    )
    code: Mapped[str] = mapped_column(String(20), nullable=False)
    description_th: Mapped[str] = mapped_column(Text, nullable=False)
    description_en: Mapped[str | None] = mapped_column(Text, nullable=True)

    curriculum: Mapped["Curriculum"] = relationship(back_populates="plos")
    ylo_mappings: Mapped[list["YLOPLOMapping"]] = relationship(
        back_populates="plo", cascade="all, delete-orphan"
    )
    course_mappings: Mapped[list["CoursePLO"]] = relationship(
        back_populates="plo", cascade="all, delete-orphan"
    )
    clo_mappings: Mapped[list["CLOPLOMapping"]] = relationship(
        back_populates="plo", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<PLO id={self.id} code={self.code!r}>"
