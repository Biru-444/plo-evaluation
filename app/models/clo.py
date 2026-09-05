"""CLO (Course Learning Outcome) model"""
from __future__ import annotations

from decimal import Decimal

from sqlalchemy import ForeignKey, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class CLO(Base):
    __tablename__ = "clo"
    __table_args__ = (UniqueConstraint("course_id", "code"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    course_id: Mapped[int] = mapped_column(
        ForeignKey("course.id", ondelete="CASCADE", onupdate="CASCADE"), nullable=False
    )
    code: Mapped[str] = mapped_column(String(20), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    pass_threshold_percent: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), nullable=False, server_default="60.00"
    )
    created_by: Mapped[int] = mapped_column(
        ForeignKey("user.id", ondelete="RESTRICT", onupdate="CASCADE"), nullable=False
    )

    course: Mapped["Course"] = relationship(back_populates="clos")
    creator: Mapped["User"] = relationship(back_populates="created_clos", foreign_keys=[created_by])
    item_mappings: Mapped[list["ItemCLO"]] = relationship(
        back_populates="clo", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<CLO id={self.id} code={self.code!r}>"
