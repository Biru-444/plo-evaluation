"""StudentScore model"""
from __future__ import annotations

from decimal import Decimal

from sqlalchemy import ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


# คะแนนดิบที่นักศึกษา 1 คนได้ในชิ้นงาน 1 ชิ้น — ข้อมูลที่ละเอียดที่สุดในระบบ ทุกสูตรคำนวณ (CLO/PLO/YLO
# mastery) ไล่ขึ้นมาจากตารางนี้ทั้งหมด ไม่มีแถวในตารางนี้ = ยังไม่มีคะแนนบันทึก (ไม่ใช่ได้ 0 คะแนนจริง)
class StudentScore(Base):
    __tablename__ = "student_score"
    # นักศึกษาคนเดียวมีคะแนนชิ้นงานเดียวกันซ้ำสองแถวไม่ได้ (แก้คะแนนคือ UPDATE แถวเดิม ไม่ใช่เพิ่มแถวใหม่)
    __table_args__ = (UniqueConstraint("item_id", "student_id"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    item_id: Mapped[int] = mapped_column(
        ForeignKey("assessment_item.id", ondelete="CASCADE", onupdate="CASCADE"), nullable=False
    )
    student_id: Mapped[str] = mapped_column(
        String(15), ForeignKey("student.id", ondelete="CASCADE", onupdate="CASCADE"), nullable=False
    )
    # คะแนนดิบที่ได้จริง (ไม่ใช่ %) — ต้องหารด้วย AssessmentItem.total_score เองถึงจะได้ % (ดูสูตรใน
    # plo_calculation.py._clo_mastery_for_student)
    score_obtained: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False)

    item: Mapped["AssessmentItem"] = relationship(back_populates="scores")
    student: Mapped["Student"] = relationship(back_populates="scores")

    def __repr__(self) -> str:
        return f"<StudentScore item_id={self.item_id} student_id={self.student_id!r}>"
