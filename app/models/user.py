"""User model"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class User(Base):
    __tablename__ = "user"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    password: Mapped[str] = mapped_column(String(255), nullable=False)
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str | None] = mapped_column(String(150), unique=True, nullable=True)
    role: Mapped[str] = mapped_column(String(30), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )

    created_clos: Mapped[list["CLO"]] = relationship(
        back_populates="creator", foreign_keys="CLO.created_by"
    )
    course_offerings: Mapped[list["CourseOffering"]] = relationship(
        back_populates="instructor", foreign_keys="CourseOffering.instructor_id"
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} username={self.username!r}>"
