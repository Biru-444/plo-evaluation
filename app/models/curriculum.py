"""Curriculum model"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Curriculum(Base):
    __tablename__ = "curriculum"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )

    plos: Mapped[list["PLO"]] = relationship(back_populates="curriculum", cascade="all, delete-orphan")
    ylos: Mapped[list["YLO"]] = relationship(back_populates="curriculum", cascade="all, delete-orphan")
    courses: Mapped[list["Course"]] = relationship(back_populates="curriculum", cascade="all, delete-orphan")
    students: Mapped[list["Student"]] = relationship(back_populates="curriculum")
    study_plans: Mapped[list["StudyPlan"]] = relationship(
        back_populates="curriculum", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Curriculum id={self.id} name={self.name!r} year={self.year}>"
