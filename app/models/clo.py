"""CLO (Course Learning Outcome) model"""
from __future__ import annotations

from decimal import Decimal

from sqlalchemy import ForeignKey, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


# ผลลัพธ์การเรียนรู้ระดับรายวิชา (Course Learning Outcome) — อาจารย์ผู้สอนเป็นคนกำหนดเอง เป็น
# หน่วยเล็กที่สุดที่ระบบนี้ตัดสิน "ผ่าน/ไม่ผ่าน" จริง ๆ (PLO/YLO ผ่านหรือไม่ ประกอบขึ้นจาก CLO เหล่านี้)
class CLO(Base):
    __tablename__ = "clo"
    # รหัส CLO ไม่ซ้ำกันภายในวิชาเดียวกัน
    __table_args__ = (UniqueConstraint("course_id", "code"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    course_id: Mapped[int] = mapped_column(
        ForeignKey("course.id", ondelete="CASCADE", onupdate="CASCADE"), nullable=False
    )
    code: Mapped[str] = mapped_column(String(20), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    # เกณฑ์ผ่านเป็นร้อยละ กำหนดแยกได้ในแต่ละ CLO (ค่ามาตรฐาน 60)
    # ถ้าแก้ : กระทบการตัดสิน "ผ่าน/ไม่ผ่าน" ใน clo_calculation.py/plo_calculation.py/ylo_calculation.py
    # ย้อนหลังทั้งหมด (ทุกจุดอ่านค่านี้สด ไม่มี cache)
    pass_threshold_percent: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), nullable=False, server_default="60.00"
    )
    # อาจารย์/แอดมินผู้สร้าง CLO นี้ — RESTRICT กันการลบผู้ใช้ที่ยังมี CLO ผูกอยู่
    created_by: Mapped[int] = mapped_column(
        ForeignKey("user.id", ondelete="RESTRICT", onupdate="CASCADE"), nullable=False
    )

    course: Mapped["Course"] = relationship(back_populates="clos")
    creator: Mapped["User"] = relationship(back_populates="created_clos", foreign_keys=[created_by])
    # ชิ้นงานที่ถูกผูกมาวัด CLO นี้ (ผ่านตาราง item_clo) พร้อมน้ำหนักของแต่ละชิ้น
    item_mappings: Mapped[list["ItemCLO"]] = relationship(
        back_populates="clo", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<CLO id={self.id} code={self.code!r}>"
