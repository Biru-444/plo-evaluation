"""CLO-PLO relationship mapping model"""
from __future__ import annotations

from decimal import Decimal

from sqlalchemy import ForeignKey, Numeric, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class CLOPLOMapping(Base):
    __tablename__ = "clo_plo_mapping"
    __table_args__ = (UniqueConstraint("clo_id", "plo_id"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    clo_id: Mapped[int] = mapped_column(
        ForeignKey("clo.id", ondelete="CASCADE", onupdate="CASCADE"), nullable=False
    )
    plo_id: Mapped[int] = mapped_column(
        ForeignKey("plo.id", ondelete="CASCADE", onupdate="CASCADE"), nullable=False
    )
    weight_percent: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)

    clo: Mapped["CLO"] = relationship(back_populates="plo_mappings")
    plo: Mapped["PLO"] = relationship(back_populates="clo_mappings")

    def __repr__(self) -> str:
        return f"<CLOPLOMapping clo_id={self.clo_id} plo_id={self.plo_id}>"
