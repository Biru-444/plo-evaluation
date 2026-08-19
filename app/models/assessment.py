"""AssessmentItem & ItemCLO models"""
from __future__ import annotations

from decimal import Decimal

from sqlalchemy import ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class AssessmentItem(Base):
    __tablename__ = "assessment_item"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    offering_id: Mapped[int] = mapped_column(
        ForeignKey("course_offering.id", ondelete="CASCADE", onupdate="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    type: Mapped[str] = mapped_column(String(50), nullable=False)
    total_score: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False)

    offering: Mapped["CourseOffering"] = relationship(back_populates="assessment_items")
    clo_mappings: Mapped[list["ItemCLO"]] = relationship(
        back_populates="item", cascade="all, delete-orphan"
    )
    scores: Mapped[list["StudentScore"]] = relationship(
        back_populates="item", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<AssessmentItem id={self.id} name={self.name!r}>"


class ItemCLO(Base):
    __tablename__ = "item_clo"
    __table_args__ = (UniqueConstraint("item_id", "clo_id"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    item_id: Mapped[int] = mapped_column(
        ForeignKey("assessment_item.id", ondelete="CASCADE", onupdate="CASCADE"), nullable=False
    )
    clo_id: Mapped[int] = mapped_column(
        ForeignKey("clo.id", ondelete="CASCADE", onupdate="CASCADE"), nullable=False
    )
    weight_percent: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)

    item: Mapped["AssessmentItem"] = relationship(back_populates="clo_mappings")
    clo: Mapped["CLO"] = relationship(back_populates="item_mappings")

    def __repr__(self) -> str:
        return f"<ItemCLO item_id={self.item_id} clo_id={self.clo_id}>"
