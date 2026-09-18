"""
ทำอะไร : CRUD มาตรฐาน (list/get/create/update/delete) สำหรับบัญชีผู้ใช้ระบบ (admin/instructor) — คนละ
         เรื่องกับ Student (นักศึกษาไม่มีบัญชี login) endpoint ทั้งหมดในไฟล์นี้ admin เท่านั้นที่เข้าได้

เชื่อมกับ : create_user เรียก hash_password จาก app/auth.py ก่อนบันทึกเสมอ (ไม่เคยเก็บรหัสผ่าน plain
            text) — VALID_ROLES จำกัดค่า role ให้เหลือแค่ "admin"/"instructor" เท่านั้น (บังคับใน route
            ไม่ใช่ระดับฐานข้อมูล เพราะ User.role เป็น string ธรรมดา ไม่ใช่ enum)

ถ้าแก้ : ลบผู้ใช้ที่ยังเป็นผู้สอนอยู่ใน course_offering หรือยังเป็นผู้สร้าง CLO ไม่ได้ (409 - ป้องกันด้วย
         ondelete="RESTRICT" ที่ระดับฐานข้อมูล) ต้องย้ายงานสอน/ความเป็นเจ้าของก่อนถึงจะลบได้
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import hash_password, require_role
from app.database import get_db
from app.models import User
from app.schemas import UserCreateSchema, UserSchema, UserUpdateSchema

router = APIRouter(prefix="/users", tags=["Users"])
VALID_ROLES = {"admin", "instructor"}


# คืนรายชื่อผู้ใช้ทั้งหมดในระบบ (admin เท่านั้น)
@router.get("", response_model=list[UserSchema])
def list_users(db: Session = Depends(get_db), _=Depends(require_role("admin"))):
    return db.query(User).order_by(User.id).all()


# คืนผู้ใช้รายตัวตาม id (admin เท่านั้น)
@router.get("/{user_id}", response_model=UserSchema)
def get_user(user_id: int, db: Session = Depends(get_db), _=Depends(require_role("admin"))):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return user


# สร้างผู้ใช้ใหม่ (admin เท่านั้น) — เข้ารหัสผ่านก่อนบันทึกเสมอ 409 ถ้า username/email ซ้ำ
@router.post("", response_model=UserSchema, status_code=201)
def create_user(
    payload: UserCreateSchema, db: Session = Depends(get_db), _=Depends(require_role("admin"))
):
    if payload.role not in VALID_ROLES:
        raise HTTPException(status_code=400, detail=f"role ต้องเป็นหนึ่งใน {VALID_ROLES}")
    user = User(
        username=payload.username,
        password=hash_password(payload.password),
        first_name=payload.first_name,
        last_name=payload.last_name,
        email=payload.email,
        role=payload.role,
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="User could not be created (username/email ซ้ำ?)") from exc
    db.refresh(user)
    return user


# แก้ไขผู้ใช้ (admin เท่านั้น) — ถ้าส่ง password มาด้วยจะเข้ารหัสใหม่ก่อนบันทึก (ไม่ส่ง = รหัสผ่านเดิม
# ไม่เปลี่ยน)
@router.put("/{user_id}", response_model=UserSchema)
def update_user(
    user_id: int,
    payload: UserUpdateSchema,
    db: Session = Depends(get_db),
    _=Depends(require_role("admin")),
):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    data = payload.model_dump(exclude_unset=True)
    if "role" in data and data["role"] not in VALID_ROLES:
        raise HTTPException(status_code=400, detail=f"role ต้องเป็นหนึ่งใน {VALID_ROLES}")
    if "password" in data and data["password"]:
        data["password"] = hash_password(data["password"])
    for field, value in data.items():
        setattr(user, field, value)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="User could not be updated (username/email ซ้ำ?)") from exc
    db.refresh(user)
    return user


# ลบผู้ใช้ (admin เท่านั้น) — 409 ถ้ายังถูกอ้างอิงอยู่ (เป็นผู้สอน/ผู้สร้าง CLO)
@router.delete("/{user_id}", status_code=204)
def delete_user(user_id: int, db: Session = Depends(get_db), _=Depends(require_role("admin"))):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    try:
        db.delete(user)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="ลบไม่ได้ - ผู้ใช้นี้ยังถูกอ้างอิงอยู่ (เช่น เป็นผู้สอนใน course_offering หรือเป็นผู้สร้าง CLO)",
        ) from exc
