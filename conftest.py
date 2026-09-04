"""
Pytest infrastructure ตัวแรกของ repo นี้ (ก่อนหน้านี้ไม่มี test เลย - ยืนยันด้วยผู้ใช้แล้วว่าให้
สร้างขึ้นใหม่จริงจัง ไม่ใช่แค่ script ตรวจสอบแบบที่เคยทำผ่าน raw SQL/curl ตลอดมา)

DATABASE_URL ถูก override เป็นฐานข้อมูลทดสอบแยกต่างหาก (<ชื่อ db เดิม>_test บน Postgres เครื่องเดียวกัน
กับที่ .env ชี้อยู่ ไม่ใช่ฐานข้อมูลจริง) ก่อน import อะไรจาก app ทั้งสิ้น กัน test แตะข้อมูลจริงเด็ดขาด -
ต้องตั้งค่านี้เป็นบรรทัดแรกๆ ของไฟล์นี้ ก่อน import ใดๆ ที่อาจ import app.database ต่อกันไป (app/database.py
เรียก os.getenv("DATABASE_URL") ตอน import module ครั้งแรกเท่านั้น) - derive จาก DATABASE_URL ที่มีอยู่แล้ว
ใน .env (host/user/password เดิมทุกอย่าง สลับแค่ชื่อ database ต่อท้าย "_test") ไม่ hardcode credentials
ไว้ในไฟล์นี้เด็ดขาด เพราะไฟล์นี้ถูก commit ขึ้น repo จริง (.env เองถูก .gitignore กันไว้อยู่แล้ว)
"""
from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()
_real_database_url = os.environ.get("DATABASE_URL")
if not _real_database_url:
    raise RuntimeError(
        "DATABASE_URL is not set (check .env - see .env.example) - needed to derive the test database URL"
    )
_base_url, _, _db_name = _real_database_url.rpartition("/")
os.environ["DATABASE_URL"] = f"{_base_url}/{_db_name}_test"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlalchemy.orm import sessionmaker

from app.database import Base, engine, get_db
from app.main import app
from app.auth import get_current_user
from app.models import User


@pytest.fixture(scope="session", autouse=True)
def _create_test_schema():
    """สร้างตารางทั้งหมดในฐานข้อมูลทดสอบครั้งเดียวตอนเริ่ม test session (ไม่ใช่ outcome_based_db จริง -
    ดู DATABASE_URL override ด้านบน) drop ทิ้งตอนจบ session ทั้งหมด"""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def db_session():
    """1 การเชื่อมต่อ + 1 transaction ต่อเทส ครอบด้วย SAVEPOINT ที่ restart ทุกครั้งที่โค้ดแอป commit
    เอง (routes เรียก db.commit() ปกติ) แล้ว rollback transaction นอกสุดทิ้งหลังเทสจบเสมอ - เทสนี้จึง
    ไม่ทิ้งร่องรอยในฐานข้อมูลทดสอบเลย ไม่ต้องลบข้อมูลเองทีละอัน"""
    connection = engine.connect()
    outer_transaction = connection.begin()
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=connection)
    session = TestingSessionLocal()
    session.begin_nested()

    @event.listens_for(session, "after_transaction_end")
    def restart_savepoint(sess, transaction):
        if transaction.nested and not transaction._parent.nested:
            sess.begin_nested()

    yield session

    session.close()
    outer_transaction.rollback()
    connection.close()


@pytest.fixture()
def admin_user(db_session):
    """User จริงในฐานข้อมูลทดสอบ (ไม่ mock ทั้งหมด) เพราะ get_current_user query User table จริง -
    override แค่ dependency ให้ข้าม JWT decode ไม่ต้อง login จริงตอนเทส"""
    user = User(
        username="test-admin",
        password="unused-in-tests",
        first_name="Test",
        last_name="Admin",
        role="admin",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture()
def client(db_session, admin_user):
    """FastAPI TestClient พร้อม override get_db (ใช้ transaction ของเทสนี้เท่านั้น) และ
    get_current_user (ข้าม JWT จริง, ใช้ admin_user ที่สร้างไว้แทน)"""

    def _override_get_db():
        yield db_session

    def _override_get_current_user():
        return admin_user

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_current_user] = _override_get_current_user

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()
