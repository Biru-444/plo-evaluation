"""API routes for User (staff: admin/instructor accounts)"""
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


@router.get("", response_model=list[UserSchema])
def list_users(db: Session = Depends(get_db), _=Depends(require_role("admin"))):
    return db.query(User).order_by(User.id).all()


@router.get("/{user_id}", response_model=UserSchema)
def get_user(user_id: int, db: Session = Depends(get_db), _=Depends(require_role("admin"))):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return user


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
