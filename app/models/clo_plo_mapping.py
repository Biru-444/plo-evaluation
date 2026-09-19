"""CLO-PLO relationship mapping model"""
from __future__ import annotations

from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


# ตารางเชื่อม many-to-many ระหว่าง CLO กับ PLO โดยตรง — 1 CLO map ได้กับหลาย PLO และ 1 PLO ก็ถูกหลาย CLO
# (จากหลายวิชา) map มาได้เช่นกัน ไม่มีคอลัมน์อื่นนอกจาก id คู่กัน (pure join table เหมือน ylo_plo_mapping)
#
# ใช้เป็นหลักฐานการคำนวณ "บรรลุ PLO" แทน course_plo (ดู _build_plo_requirements ใน
# app/routes/plo_calculation.py) — course_plo ยังเก็บไว้ใช้แสดง Curriculum Mapping ระดับหลักสูตรเหมือนเดิม
# ไม่ได้ถูกแทนที่ทั้งหมด
class CLOPLOMapping(Base):
    __tablename__ = "clo_plo_mapping"
    # คู่ clo_id + plo_id ซ้ำกันไม่ได้ (map ซ้ำ 2 ครั้งไม่มีความหมายเพิ่ม)
    __table_args__ = (UniqueConstraint("clo_id", "plo_id"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    clo_id: Mapped[int] = mapped_column(
        ForeignKey("clo.id", ondelete="CASCADE", onupdate="CASCADE"), nullable=False
    )
    plo_id: Mapped[int] = mapped_column(
        ForeignKey("plo.id", ondelete="CASCADE", onupdate="CASCADE"), nullable=False
    )

    clo: Mapped["CLO"] = relationship(back_populates="plo_mappings")
    plo: Mapped["PLO"] = relationship(back_populates="clo_mappings")

    def __repr__(self) -> str:
        return f"<CLOPLOMapping clo_id={self.clo_id} plo_id={self.plo_id}>"
