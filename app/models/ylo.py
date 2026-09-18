"""YLO (Year Learning Outcome) model"""
from __future__ import annotations

from sqlalchemy import ForeignKey, Integer, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


# ผลลัพธ์การเรียนรู้ระดับชั้นปี (Year Learning Outcome) — 1 แถวต่อ 1 ชั้นปีของหลักสูตร (ปกติมี 4
# แถวต่อหลักสูตร คือปี 1-4) ใช้คำนวณ "% บรรลุ YLO" ใน app/routes/ylo_calculation.py
class YLO(Base):
    __tablename__ = "ylo"
    # หลักสูตรเดียวกันมี YLO ซ้ำชั้นปีเดียวกันไม่ได้ (1 ปี = 1 YLO เท่านั้น)
    __table_args__ = (UniqueConstraint("curriculum_id", "year_level"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    curriculum_id: Mapped[int] = mapped_column(
        ForeignKey("curriculum.id", ondelete="CASCADE", onupdate="CASCADE"), nullable=False
    )
    year_level: Mapped[int] = mapped_column(Integer, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)

    curriculum: Mapped["Curriculum"] = relationship(back_populates="ylos")
    # PLO กลุ่มที่ YLO ปีนี้ต้องพึ่งพา (ผ่านตาราง ylo_plo_mapping) — YLO 1 ปีมักถูก map กับหลาย PLO
    # พร้อมกัน (ดูสูตรคำนวณใน ylo_calculation.py ว่าใช้ PLO กลุ่มนี้ยังไง)
    plo_mappings: Mapped[list["YLOPLOMapping"]] = relationship(
        back_populates="ylo", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<YLO id={self.id} year_level={self.year_level}>"
