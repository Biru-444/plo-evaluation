"""
Tests สำหรับ POST /curricula/import-from-mco2/save (Phase 2 ของฟีเจอร์ "นำเข้าหลักสูตร/PLO จาก
มคอ.2 ด้วย AI" - ดู app/routes/curriculum_import.py) บันทึก Curriculum + PLO จริงจากผลลัพธ์ที่
แอดมินตรวจ/แก้ไขแล้วใน Phase 3 (ยังไม่มี Phase 3 - test เหล่านี้ยิง JSON ตรงเหมือนเป็นผลลัพธ์ที่ผ่าน
การตรวจแล้ว) เลียนแบบ tests/test_mco3_import_save.py ทุกประการ

ต่างจาก tests/test_mco3_import_extended.py (Phase 1) ตรงที่ endpoint นี้ไม่เรียก Gemini เลย - เป็น
DB write ธรรมดา จึง deterministic เต็มร้อย ไม่ต้อง skip ตาม GEMINI_API_KEY
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.auth import get_current_user
from app.database import get_db
from app.main import app
from app.models import Curriculum, PLO, User


@pytest.fixture()
def make_client(db_session):
    """เหมือน conftest.py's `client` fixture แต่รับ user ที่จะให้เป็น current_user ได้ - ก๊อปจาก
    test_mco3_import_save.py เพราะ pytest fixture ไม่แชร์ข้ามไฟล์นอก conftest.py"""

    def _make(user: User) -> TestClient:
        def _override_get_db():
            yield db_session

        def _override_get_current_user():
            return user

        app.dependency_overrides[get_db] = _override_get_db
        app.dependency_overrides[get_current_user] = _override_get_current_user
        return TestClient(app)

    yield _make
    app.dependency_overrides.clear()


def _payload(curriculum_id: int | None = None, **overrides):
    body = {
        "curriculum_id": curriculum_id,
        "curriculum_name": "หลักสูตรทดสอบ มคอ.2",
        "curriculum_year": 2569,
        "plos": [
            {"code": "PLO1", "description_th": "คำอธิบาย PLO1", "category": "ความรู้"},
            {"code": "PLO2", "description_th": "คำอธิบาย PLO2", "category": "ทักษะ"},
        ],
    }
    body.update(overrides)
    return body


def test_save_creates_new_curriculum_and_plos_when_no_curriculum_id(client, db_session):
    resp = client.post("/curricula/import-from-mco2/save", json=_payload())
    assert resp.status_code == 201
    body = resp.json()

    assert body["curriculum"]["name"] == "หลักสูตรทดสอบ มคอ.2"
    assert body["curriculum"]["year"] == 2569
    assert len(body["plos"]) == 2
    assert set(body["created_plo_codes"]) == {"PLO1", "PLO2"}
    assert body["updated_plo_codes"] == []

    curriculum = db_session.query(Curriculum).filter(Curriculum.name == "หลักสูตรทดสอบ มคอ.2").first()
    assert curriculum is not None
    plos_in_db = db_session.query(PLO).filter(PLO.curriculum_id == curriculum.id).all()
    assert len(plos_in_db) == 2


def test_save_upserts_into_existing_curriculum_not_rejected(client, db_session):
    """หัวใจของ Workstream 2 - ต่างจาก มคอ.3 ตรงที่หลักสูตรมีอยู่แล้วต้องไม่ถูก 409 ปฏิเสธ ต้องเพิ่ม/
    อัปเดต PLO เข้าไปได้เลย"""
    curriculum = Curriculum(name="หลักสูตรที่มีอยู่แล้ว", year=2568)
    db_session.add(curriculum)
    db_session.commit()
    db_session.refresh(curriculum)

    existing_plo = PLO(
        curriculum_id=curriculum.id,
        code="PLO1",
        description_th="คำอธิบายเดิม",
        category="ความรู้",
    )
    db_session.add(existing_plo)
    db_session.commit()

    payload = _payload(curriculum_id=curriculum.id)
    payload["curriculum_name"] = "หลักสูตรที่มีอยู่แล้ว"
    payload["curriculum_year"] = 2568
    payload["plos"] = [
        {"code": "PLO1", "description_th": "คำอธิบายที่แก้ไขแล้ว", "category": "ทักษะ"},
        {"code": "PLO2", "description_th": "PLO ใหม่ที่เพิ่งเพิ่ม", "category": "ความรู้"},
    ]

    resp = client.post("/curricula/import-from-mco2/save", json=payload)
    assert resp.status_code == 201
    body = resp.json()

    assert body["curriculum"]["id"] == curriculum.id
    assert body["updated_plo_codes"] == ["PLO1"]
    assert body["created_plo_codes"] == ["PLO2"]

    db_session.refresh(existing_plo)
    assert existing_plo.description_th == "คำอธิบายที่แก้ไขแล้ว"
    assert existing_plo.category == "ทักษะ"

    all_plos = db_session.query(PLO).filter(PLO.curriculum_id == curriculum.id).all()
    assert len(all_plos) == 2


def test_save_rejects_missing_category_with_400(client):
    payload = _payload()
    payload["plos"][0]["category"] = None
    resp = client.post("/curricula/import-from-mco2/save", json=payload)
    assert resp.status_code == 400
    assert "PLO1" in resp.json()["detail"]


def test_save_rejects_duplicate_plo_code_within_payload_with_400(client):
    payload = _payload()
    payload["plos"] = [
        {"code": "PLO1", "description_th": "อันแรก", "category": "ความรู้"},
        {"code": "PLO1", "description_th": "อันที่สอง รหัสซ้ำ", "category": "ทักษะ"},
    ]
    resp = client.post("/curricula/import-from-mco2/save", json=payload)
    assert resp.status_code == 400
    assert "PLO1" in resp.json()["detail"]


def test_save_rejects_invalid_curriculum_id_with_404(client):
    resp = client.post("/curricula/import-from-mco2/save", json=_payload(curriculum_id=999999))
    assert resp.status_code == 404


def test_save_requires_admin(make_client, db_session):
    instructor = User(
        username="test-instructor-mco2-save",
        password="unused-in-tests",
        first_name="Test",
        last_name="Instructor",
        role="instructor",
    )
    db_session.add(instructor)
    db_session.commit()
    db_session.refresh(instructor)

    instructor_client = make_client(instructor)
    resp = instructor_client.post("/curricula/import-from-mco2/save", json=_payload())
    assert resp.status_code == 403
