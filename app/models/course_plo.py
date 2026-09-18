"""Course-PLO relationship model"""
from __future__ import annotations

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


# ตารางเชื่อมระหว่างวิชากับ PLO ตามที่ออกแบบไว้ในหลักสูตร (มคอ.2) — เป็นตารางที่สำคัญที่สุดในการคำนวณ
# ผลบรรลุ PLO/YLO ทั้งระบบ (ดู app/routes/plo_calculation.py, ylo_calculation.py) ตารางเดิมชื่อ
# clo_plo_mapping ถูก DROP ทิ้งไปแล้ว (ดู scripts/migrate_drop_clo_plo_mapping.py) — ตอนนี้ mapping
# อยู่ที่ระดับวิชาทั้งวิชาเท่านั้น ไม่ใช่ระดับ CLO
class CoursePLO(Base):
    __tablename__ = "course_plo"
    # วิชาเดียวกัน map กับ PLO เดียวกันซ้ำสองแถวไม่ได้
    __table_args__ = (UniqueConstraint("course_id", "plo_id"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    course_id: Mapped[int] = mapped_column(
        ForeignKey("course.id", ondelete="CASCADE", onupdate="CASCADE"), nullable=False
    )
    plo_id: Mapped[int] = mapped_column(
        ForeignKey("plo.id", ondelete="CASCADE", onupdate="CASCADE"), nullable=False
    )
    # ค่าที่ใช้จริงมีแค่ 'primary' กับ 'secondary' — 'primary' เท่านั้นที่ถูกนับเป็น "วิชาบังคับ" ในการ
    # ตัดสิน % บรรลุ PLO (นักศึกษาต้องผ่านทุก CLO ของวิชานั้น) ส่วน 'secondary' เป็นข้อมูลประกอบเฉย ๆ
    # ไม่มีผลต่อการคำนวณเลย (ดู _build_plo_requirements ใน plo_calculation.py ที่กรองเฉพาะ 'primary')
    responsibility_level: Mapped[str] = mapped_column(String(20), nullable=False)

    course: Mapped["Course"] = relationship(back_populates="plo_mappings")
    plo: Mapped["PLO"] = relationship(back_populates="course_mappings")

    def __repr__(self) -> str:
        return f"<CoursePLO course_id={self.course_id} plo_id={self.plo_id}>"
