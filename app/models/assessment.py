"""AssessmentItem & ItemCLO models"""
from __future__ import annotations

from decimal import Decimal

from sqlalchemy import ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


# ชิ้นงาน/ข้อสอบที่ใช้ประเมิน 1 offering (เช่น "สอบกลางภาค", "การบ้านที่ 3") — คะแนนดิบของนักศึกษาแต่ละ
# คนต่อชิ้นงานเก็บแยกไว้ในตาราง StudentScore ไม่ได้เก็บในตารางนี้
class AssessmentItem(Base):
    __tablename__ = "assessment_item"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    offering_id: Mapped[int] = mapped_column(
        ForeignKey("course_offering.id", ondelete="CASCADE", onupdate="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    # ประเภทชิ้นงาน (เช่น "quiz", "midterm", "assignment") — free text แสดงผลอย่างเดียว
    type: Mapped[str] = mapped_column(String(50), nullable=False)
    # คะแนนเต็มของชิ้นงานนี้ — ใช้เป็นตัวหารแปลงคะแนนดิบเป็น % ในทุกสูตรคำนวณ (ดู plo_calculation.py)
    total_score: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False)

    offering: Mapped["CourseOffering"] = relationship(back_populates="assessment_items")
    # CLO ที่ชิ้นงานนี้ถูกผูกไว้ให้วัด (1 ชิ้นงานวัดได้หลาย CLO พร้อมกัน คนละน้ำหนักได้)
    clo_mappings: Mapped[list["ItemCLO"]] = relationship(
        back_populates="item", cascade="all, delete-orphan"
    )
    # คะแนนดิบของนักศึกษาแต่ละคนสำหรับชิ้นงานนี้
    scores: Mapped[list["StudentScore"]] = relationship(
        back_populates="item", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<AssessmentItem id={self.id} name={self.name!r}>"


# ตารางเชื่อมระหว่างชิ้นงาน (assessment_item) กับ CLO ที่ชิ้นงานนั้นวัด พร้อมน้ำหนัก — เป็นหัวใจของสูตร
# คำนวณ mastery แบบถ่วงน้ำหนักทั้งระบบ (ดู _clo_mastery_for_student ใน plo_calculation.py)
class ItemCLO(Base):
    __tablename__ = "item_clo"
    # ชิ้นงานเดียวกันผูกกับ CLO เดียวกันซ้ำสองแถวไม่ได้
    __table_args__ = (UniqueConstraint("item_id", "clo_id"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    item_id: Mapped[int] = mapped_column(
        ForeignKey("assessment_item.id", ondelete="CASCADE", onupdate="CASCADE"), nullable=False
    )
    clo_id: Mapped[int] = mapped_column(
        ForeignKey("clo.id", ondelete="CASCADE", onupdate="CASCADE"), nullable=False
    )
    # น้ำหนักของชิ้นงานนี้ต่อ CLO นี้โดยเฉพาะ (เป็น %) — ผลรวม weight_percent ของทุกชิ้นงานที่ผูกกับ
    # CLO เดียวกัน ควรรวมได้ไม่เกิน 100 (เช็คตอนสร้าง/แก้ไขในระดับ route ไม่ใช่ระดับฐานข้อมูล)
    weight_percent: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)

    item: Mapped["AssessmentItem"] = relationship(back_populates="clo_mappings")
    clo: Mapped["CLO"] = relationship(back_populates="item_mappings")

    def __repr__(self) -> str:
        return f"<ItemCLO item_id={self.item_id} clo_id={self.clo_id}>"
