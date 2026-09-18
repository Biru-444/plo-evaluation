"""
ทำอะไร : endpoint สำหรับ login และดึงข้อมูลผู้ใช้ปัจจุบัน — ไฟล์นี้คนละไฟล์กับ app/auth.py (นั่นคือ
         utility ฟังก์ชัน เช่น hash/verify/create token, dependency ของ endpoint อื่น ๆ ทั้งระบบ ส่วน
         ไฟล์นี้คือ route จริงที่ frontend เรียก)

เชื่อมกับ : POST /auth/login เรียก verify_password + create_access_token จาก app/auth.py — ฝั่ง
            frontend (LoginPage) เรียก endpoint นี้แล้วเก็บ access_token ไว้ใน localStorage ผ่าน
            AuthContext.jsx (ไม่ได้เรียก GET /auth/me ต่อเพื่อ verify ซ้ำ — ดูหัวข้อ "ถ้าแก้")

ถ้าแก้ : GET /auth/me มีให้ใช้ตามมาตรฐาน REST API ทั่วไป แต่ปัจจุบัน frontend ไม่เคยเรียก endpoint นี้
         เลย (auth ฝั่ง frontend เชื่อ token ใน localStorage ตรง ๆ ไม่ re-verify ทุกครั้งที่โหลดหน้า) —
         ถ้าจะลบทิ้งต้องตรวจให้แน่ใจก่อนว่าไม่มีที่ไหนอ้างถึง
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.auth import create_access_token, get_current_user, verify_password
from app.database import get_db
from app.models import User

router = APIRouter(prefix="/auth", tags=["Auth"])


# ข้อมูลผู้ใช้แบบเปิดเผยได้ (ไม่มี password hash ปนมา) — ต่างจาก UserSchema ใน app/schemas/user.py
# ตรงที่ไม่มี created_at/updated_at (ไม่จำเป็นสำหรับ response ตอน login)
class UserPublicSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    first_name: str
    last_name: str
    email: str | None
    role: str


# response ของ POST /login — access_token คือ JWT ที่ frontend ต้องแนบไปกับทุก request ถัดไปใน header
# Authorization: Bearer <token>
class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    user: UserPublicSchema


# เข้าสู่ระบบด้วย username/password (ผ่าน OAuth2 password flow ตามมาตรฐานของ FastAPI) ตรวจรหัสผ่านด้วย
# verify_password (bcrypt) แล้วออก JWT token กลับไปพร้อมข้อมูลผู้ใช้
@router.post("/login", response_model=TokenResponse)
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.username == form_data.username).first()
    if user is None or not verify_password(form_data.password, user.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_access_token(data={"sub": user.username})
    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        user=UserPublicSchema.model_validate(user),
    )


# คืนข้อมูลผู้ใช้ปัจจุบันจาก token ที่แนบมา — endpoint มาตรฐานที่มีให้ใช้ แต่ frontend ไม่เคยเรียกเลย
# (ดู "ถ้าแก้" ในหัว docstring ของไฟล์นี้)
@router.get("/me", response_model=UserPublicSchema)
def get_me(current_user: User = Depends(get_current_user)):
    return current_user
