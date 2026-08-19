"""YLO (Year Learning Outcome) model"""
from __future__ import annotations

from sqlalchemy import ForeignKey, Integer, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class YLO(Base):
    __tablename__ = "ylo"
    __table_args__ = (UniqueConstraint("curriculum_id", "year_level"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    curriculum_id: Mapped[int] = mapped_column(
        ForeignKey("curriculum.id", ondelete="CASCADE", onupdate="CASCADE"), nullable=False
    )
    year_level: Mapped[int] = mapped_column(Integer, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)

    curriculum: Mapped["Curriculum"] = relationship(back_populates="ylos")
    plo_mappings: Mapped[list["YLOPLOMapping"]] = relationship(
        back_populates="ylo", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<YLO id={self.id} year_level={self.year_level}>"
