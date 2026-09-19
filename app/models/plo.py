"""PLO (Program Learning Outcome) model"""
from __future__ import annotations

from sqlalchemy import ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


# ผลลัพธ์การเรียนรู้ระดับหลักสูตร (Program Learning Outcome) ตามที่กำหนดไว้ใน มคอ.2 — เป็นเป้าหมาย
# สูงสุดที่ระบบนี้คำนวณ "% บรรลุ" ให้ (ดู app/routes/plo_calculation.py)
class PLO(Base):
    __tablename__ = "plo"
    # รหัส PLO (code) ต้องไม่ซ้ำกันภายในหลักสูตรเดียวกัน (ต่างหลักสูตรใช้รหัสซ้ำกันได้)
    __table_args__ = (UniqueConstraint("curriculum_id", "code"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    curriculum_id: Mapped[int] = mapped_column(
        ForeignKey("curriculum.id", ondelete="CASCADE", onupdate="CASCADE"), nullable=False
    )
    code: Mapped[str] = mapped_column(String(20), nullable=False)
    description_th: Mapped[str] = mapped_column(Text, nullable=False)
    description_en: Mapped[str | None] = mapped_column(Text, nullable=True)

    curriculum: Mapped["Curriculum"] = relationship(back_populates="plos")
    # YLO ที่ถูก map มาที่ PLO นี้ (ผ่านตาราง ylo_plo_mapping) — ใช้ตัดสินว่า YLO ปีไหนต้องพึ่ง PLO นี้บ้าง
    ylo_mappings: Mapped[list["YLOPLOMapping"]] = relationship(
        back_populates="plo", cascade="all, delete-orphan"
    )
    # วิชาที่ถูก map มาที่ PLO นี้ (ผ่านตาราง course_plo) — เฉพาะแถวที่ responsibility_level='primary'
    # เท่านั้นที่นับเป็น "วิชาบังคับ" ในการคำนวณ % บรรลุ (ดู course_plo.py และ plo_calculation.py)
    course_mappings: Mapped[list["CoursePLO"]] = relationship(
        back_populates="plo", cascade="all, delete-orphan"
    )
    # CLO ที่ผูกกับ PLO นี้โดยตรง (ผ่านตาราง clo_plo_mapping)
    clo_mappings: Mapped[list["CLOPLOMapping"]] = relationship(
        back_populates="plo", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<PLO id={self.id} code={self.code!r}>"
