"""YLO-PLO relationship mapping model"""
from __future__ import annotations

from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


# ตารางเชื่อม many-to-many ระหว่าง YLO กับ PLO — 1 YLO (1 ชั้นปี) map ได้กับหลาย PLO และ 1 PLO ก็ถูก
# หลาย YLO (หลายปี) map มาได้เช่นกัน ไม่มีคอลัมน์อื่นนอกจาก id คู่กัน (pure join table)
class YLOPLOMapping(Base):
    __tablename__ = "ylo_plo_mapping"
    # คู่ ylo_id + plo_id ซ้ำกันไม่ได้ (map ซ้ำ 2 ครั้งไม่มีความหมายเพิ่ม)
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
