"""CLO-PLO relationship mapping model"""
from __future__ import annotations

from decimal import Decimal

from sqlalchemy import ForeignKey, Numeric, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


# ตารางเชื่อม many-to-many ระหว่าง CLO กับ PLO โดยตรง — 1 CLO map ได้กับหลาย PLO และ 1 PLO ก็ถูกหลาย CLO
# (จากหลายวิชา) map มาได้เช่นกัน
#
# ใช้เป็นหลักฐานการคำนวณ "บรรลุ PLO" แทน course_plo (ดู plo_calculation.py) — course_plo ยังเก็บไว้ใช้
# แสดง Curriculum Mapping ระดับหลักสูตรเหมือนเดิม ไม่ได้ถูกแทนที่ทั้งหมด
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
    # น้ำหนักของ "คู่" CLO-PLO นี้โดยเฉพาะ (ไม่ใช่ของ CLO เฉยๆ - CLO เดียวกันผูกกับหลาย PLO ได้ คนละ
    # น้ำหนักกัน) ใช้เข้าสูตร PLO_x = Σ(mastery_i × weight_i) / Σ(weight_i) ใน plo_calculation.py ผลรวม
    # น้ำหนักของ CLO ทุกตัวที่ผูกกับ PLO ข้อหนึ่งๆ **ไม่บังคับต้องเท่า 100** (สูตรหารด้วยผลรวมน้ำหนักเอง
    # อยู่แล้ว) NOT NULL เสมอ - ทุกจุดที่สร้างแถวนี้ (POST /clo-plo-mapping, POST/PUT /clo ที่มี plo_ids,
    # Phase 2 ของ มคอ.3 import) ต้องกำหนดค่ามาให้เสมอ ห้ามปล่อย null (auto-fill เกลี่ยเท่ากันฝั่ง
    # backend/frontend ตามจุดที่สร้าง - ดู app/routes/clo_plo_mapping.py::_rebalance_clo_weights_evenly)
    weight_percent: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)

    clo: Mapped["CLO"] = relationship(back_populates="plo_mappings")
    plo: Mapped["PLO"] = relationship(back_populates="clo_mappings")

    def __repr__(self) -> str:
        return f"<CLOPLOMapping clo_id={self.clo_id} plo_id={self.plo_id} weight_percent={self.weight_percent}>"
