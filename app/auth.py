"""
ทำอะไร : รวมฟังก์ชันด้าน authentication (เข้ารหัส/ตรวจรหัสผ่าน, ออก/ตรวจ JWT token) และ authorization
         แบบ role-based (จำกัดสิทธิ์ตาม role เช่น admin/instructor)

เชื่อมกับ : ทุก route ในระบบที่ต้อง login ก่อนใช้งาน จะใส่ Depends(get_current_user) ไว้เป็น dependency
            — endpoint /auth/login (ใน app/routes/auth.py) เรียก verify_password + create_access_token
            ที่นี่ตอนออก token ให้ผู้ใช้ตอน login สำเร็จ ฝั่ง frontend เก็บ token ไว้ใน localStorage
            ผ่าน AuthContext.jsx (ไม่ได้เรียก endpoint ใด ๆ ในไฟล์นี้เพื่อ verify token ซ้ำ)

ถ้าแก้ : SECRET_KEY มาจาก environment variable เท่านั้น (ไม่มีอยู่ในโค้ด) ถ้าไม่ได้ตั้งค่าไว้ แอปจะ
         สตาร์ทไม่ขึ้นทันที (ดู RuntimeError ด้านล่าง) — เปลี่ยน ALGORITHM หรือโครงสร้าง payload ของ
         token จะทำให้ token เก่าที่ผู้ใช้ถืออยู่ใช้ไม่ได้ทันที ต้อง login ใหม่ทุกคน
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User

# ต้องตั้งค่าผ่าน environment variable เท่านั้น (ห้าม hardcode ในโค้ด) — ถ้าไม่ตั้งไว้ แอปจะไม่สตาร์ท
# เลยแทนที่จะรันด้วยค่า default ที่ไม่ปลอดภัย
SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    raise RuntimeError("SECRET_KEY environment variable is not set (see .env.example)")

ALGORITHM = "HS256"

# ใช้ bcrypt เข้ารหัสผ่านผู้ใช้ก่อนบันทึกลงฐานข้อมูลเสมอ (ไม่เก็บ plain text)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# บอก FastAPI ว่า client ต้องขอ token จาก endpoint ไหน (/auth/login) — ใช้ประกอบ Swagger UI ที่ /docs
# ให้มีปุ่ม "Authorize" กรอก username/password ทดสอบได้
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


# เข้ารหัสรหัสผ่านก่อนบันทึกลงฐานข้อมูล (bcrypt hash แบบ one-way ถอดกลับไม่ได้)
def hash_password(plain: str) -> str:
    return pwd_context.hash(plain)


# เทียบรหัสผ่านที่กรอกกับ hash ที่เก็บไว้ในฐานข้อมูล — ใช้ตอน login
def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


# ออก JWT access token (เข้ารหัสข้อมูลผู้ใช้ + เวลาหมดอายุ) — ค่า default หมดอายุใน 480 นาที (8
# ชั่วโมง) เท่ากับ 1 วันทำงาน ให้ผู้ใช้ไม่ต้อง login ซ้ำบ่อยเกินไประหว่างวัน
def create_access_token(data: dict, expires_minutes: int = 480) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=expires_minutes)
    to_encode["exp"] = expire
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


# dependency ที่แทบทุก endpoint ในระบบใช้ (Depends(get_current_user)) — ถอดรหัส JWT token จาก header
# Authorization: Bearer แล้วหาผู้ใช้จริงในฐานข้อมูล token ปลอมหรือหมดอายุจะโดน 401 ทันที
def get_current_user(
    token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        # "sub" (subject) คือ username ที่ฝังไว้ตอนออก token (ดู /auth/login ใน routes/auth.py)
        username = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = db.query(User).filter(User.username == username).first()
    if user is None:
        raise credentials_exception
    return user


def require_role(*roles: str):
    """
    ทำอะไร : dependency factory — คืน dependency function ที่อนุญาตเฉพาะผู้ใช้ที่ role อยู่ใน roles
             ที่ระบุ (เช่น require_role("admin") หรือ require_role("admin", "instructor"))

    เชื่อมกับ : ใช้ใน endpoint ที่ต้องจำกัดสิทธิ์เฉพาะบาง role เช่น endpoint จัดการผู้ใช้ที่ admin
                เท่านั้นเข้าได้ — เรียก get_current_user ต่ออีกทีเพื่อยืนยันตัวตนก่อน แล้วค่อยเช็ค role

    ถ้าแก้ : ผู้ใช้ role ไม่ตรงจะโดน 403 Forbidden (ต่างจาก 401 ที่แปลว่ายังไม่ login/token ไม่ถูกต้อง)
    """

    def dependency(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not enough permissions",
            )
        return current_user

    return dependency
