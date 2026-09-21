"""
Tests สำหรับ /plo CRUD (app/routes/plo.py) - เน้นฟิลด์ category ที่เพิ่งเพิ่มเข้ามา (บังคับกรอกเสมอ
ต่างจาก course.category ที่เป็น optional) ดู scripts/migrate_add_plo_category.py และ
app/models/plo.py สำหรับที่มาของ constraint นี้
"""
from __future__ import annotations

import pytest

from app.models import Curriculum, PLO


@pytest.fixture()
def curriculum(db_session):
    curriculum = Curriculum(name="Test Curriculum PLO Category", year=2569)
    db_session.add(curriculum)
    db_session.commit()
    db_session.refresh(curriculum)
    return curriculum


def test_create_without_category_returns_422(client, curriculum):
    resp = client.post(
        "/plo",
        json={
            "curriculum_id": curriculum.id,
            "code": "PLO1",
            "description_th": "ทดสอบ PLO",
        },
    )
    assert resp.status_code == 422


def test_create_with_category_succeeds(client, curriculum):
    resp = client.post(
        "/plo",
        json={
            "curriculum_id": curriculum.id,
            "code": "PLO1",
            "description_th": "ทดสอบ PLO",
            "category": "ความรู้",
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["category"] == "ความรู้"


def test_update_category_succeeds(client, db_session, curriculum):
    plo = PLO(
        curriculum_id=curriculum.id,
        code="PLO1",
        description_th="ทดสอบ PLO",
        category="ความรู้",
    )
    db_session.add(plo)
    db_session.commit()
    db_session.refresh(plo)

    resp = client.put(f"/plo/{plo.id}", json={"category": "ทักษะ"})
    assert resp.status_code == 200
    assert resp.json()["category"] == "ทักษะ"

    db_session.refresh(plo)
    assert plo.category == "ทักษะ"
