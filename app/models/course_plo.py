"""Course-PLO relationship model"""
from __future__ import annotations

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


# ตารางเชื่อมระหว่างวิชากับ PLO ตามที่ออกแบบไว้ในหลักสูตร (มคอ.2) - เก็บไว้เป็นข้อมูล "แผนหลักสูตรตอน
# ออกแบบ" เท่านั้น (ดู GET /plo/{plo_id}/course-plan ใน app/routes/plo.py)
#
# **อัปเดต (2026-09) - คอมเมนต์เดิมด้านล่างนี้ล้าสมัยและผิดแล้ว**: comment เดิมเคยบอกว่าตารางนี้ "สำคัญ
# ที่สุดในการคำนวณผลบรรลุ PLO/YLO" และตาราง clo_plo_mapping ถูก DROP ทิ้งไปแล้ว - ทั้งสองข้อไม่จริงอีก
# ต่อไป: clo_plo_mapping ถูกกู้คืนกลับมาแล้ว (ดู scripts/migrate_restore_clo_plo_mapping.py, PR #10
# 2026-09-19) และการคำนวณ % บรรลุ PLO/YLO ทั้งระบบเปลี่ยนไปใช้ clo_plo_mapping (ระดับ CLO) เป็นหลักฐาน
# แทนตารางนี้ทั้งหมดแล้ว (ดู _build_plo_requirements ใน app/services/plo_achievement_service.py ที่ join
# clo_plo_mapping ตรงๆ ไม่แตะ course_plo เลย) - แก้ course_plo.responsibility_level ที่นี่จึง **ไม่มีผล
# ต่อ % บรรลุ PLO ของนักศึกษาคนไหนเลยในตอนนี้** เหลือแค่ใช้แสดงผลใน course-plan (ข้างบน) และใน Excel
# export ของภาพรวม PLO เป็นข้อมูลเปรียบเทียบ "แผนที่ตั้งใจ" กับ "หลักฐานจริงจาก clo_plo_mapping" เท่านั้น
# (ดู app/services/plo_report_data_service.py เรื่อง mismatch 'no_clo'/'no_course_plo')
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
    # ค่าที่ใช้จริงมีแค่ 'primary' กับ 'secondary' — 'primary' เท่านั้นที่ถูกกรองมาแสดงใน course-plan
    # (GET /plo/{plo_id}/course-plan) ตัวคอลัมน์นี้ **ไม่มีผลต่อการคำนวณ % บรรลุ PLO แล้ว** (ดูคอมเมนต์
    # ของทั้งคลาสด้านบน) - 'secondary' เป็นข้อมูลประกอบเฉยๆ ไม่ถูกใช้แสดงที่ไหนเลยตอนนี้
    responsibility_level: Mapped[str] = mapped_column(String(20), nullable=False)

    course: Mapped["Course"] = relationship(back_populates="plo_mappings")
    plo: Mapped["PLO"] = relationship(back_populates="course_mappings")

    def __repr__(self) -> str:
        return f"<CoursePLO course_id={self.course_id} plo_id={self.plo_id}>"
