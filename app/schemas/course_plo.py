"""Pydantic schemas for CoursePLO — responsibility_level ใช้ได้แค่ 'primary'/'secondary' เท่านั้น
(เช็คแยกใน route ไม่ได้บังคับผ่าน Literal type ในชั้น schema นี้) ดูความสำคัญของ field นี้ต่อการ
คำนวณ PLO/YLO ทั้งระบบใน app/models/course_plo.py"""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class CoursePLOSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int | None = None
    course_id: int
    plo_id: int
    responsibility_level: str


class CoursePLOCreateSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    course_id: int
    plo_id: int
    responsibility_level: str


class CoursePLOUpdateSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    responsibility_level: str | None = None
