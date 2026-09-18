"""Pydantic schemas for User — field ความหมายตรงกับ app/models/user.py ทุกตัว (ดูคอมเมนต์ที่นั่น)
UserCreateSchema.password รับเป็น plain text จากฝั่ง client แล้ว route เป็นคนเรียก hash_password()
เข้ารหัสก่อนบันทึก (ไม่มีการเข้ารหัสในชั้น schema)"""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class UserSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int | None = None
    username: str
    first_name: str
    last_name: str
    email: str | None = None
    role: str
    created_at: datetime
    updated_at: datetime


class UserCreateSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    username: str
    password: str
    first_name: str
    last_name: str
    email: str | None = None
    role: str


class UserUpdateSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    username: str | None = None
    password: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    email: str | None = None
    role: str | None = None
