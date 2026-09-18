"""User model"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


# ผู้ใช้ระบบ (แอดมินหรืออาจารย์) — ไม่มีนักศึกษาที่มี login เป็นของตัวเอง (Student เป็นคนละตารางที่ไม่
# ผูกกับ User เลย เพราะระบบนี้ไม่มีฟีเจอร์ให้นักศึกษา login ดูผลตัวเอง)
class User(Base):
    __tablename__ = "user"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    # เก็บ hash (bcrypt) เท่านั้น ไม่ใช่รหัสผ่านจริง — เข้ารหัส/ตรวจสอบผ่าน app/auth.py
    password: Mapped[str] = mapped_column(String(255), nullable=False)
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str | None] = mapped_column(String(150), unique=True, nullable=True)
    # ค่าที่ใช้จริงคือ "admin" กับ "instructor" — กำหนดสิทธิ์การเข้าถึงผ่าน require_role() ใน app/auth.py
    role: Mapped[str] = mapped_column(String(30), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )

    # CLO ทั้งหมดที่ผู้ใช้คนนี้เป็นคนสร้าง (ผูกกับ CLO.created_by)
    created_clos: Mapped[list["CLO"]] = relationship(
        back_populates="creator", foreign_keys="CLO.created_by"
    )
    # course_offering (กลุ่มเรียน) ทั้งหมดที่ผู้ใช้คนนี้เป็นผู้สอน (ผูกกับ CourseOffering.instructor_id)
    course_offerings: Mapped[list["CourseOffering"]] = relationship(
        back_populates="instructor", foreign_keys="CourseOffering.instructor_id"
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} username={self.username!r}>"
