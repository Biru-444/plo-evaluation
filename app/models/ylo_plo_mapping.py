"""YLO-PLO relationship mapping model"""
from __future__ import annotations

from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class YLOPLOMapping(Base):
    __tablename__ = "ylo_plo_mapping"
    __table_args__ = (UniqueConstraint("ylo_id", "plo_id"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    ylo_id: Mapped[int] = mapped_column(
        ForeignKey("ylo.id", ondelete="CASCADE", onupdate="CASCADE"), nullable=False
    )
    plo_id: Mapped[int] = mapped_column(
        ForeignKey("plo.id", ondelete="CASCADE", onupdate="CASCADE"), nullable=False
    )

    ylo: Mapped["YLO"] = relationship(back_populates="plo_mappings")
    plo: Mapped["PLO"] = relationship(back_populates="ylo_mappings")

    def __repr__(self) -> str:
        return f"<YLOPLOMapping ylo_id={self.ylo_id} plo_id={self.plo_id}>"
