"""Tests สำหรับเช็คว่า CLO กับ PLO ที่กำลังจะผูกกันต้องอยู่หลักสูตรเดียวกัน (422 ถ้าไม่ตรง) - ดู
app/services/curriculum_match_check.py ครอบคลุมทั้ง 3 จุดที่รับ clo_id+plo_id คู่จาก client โดยตรง:
POST /clo-plo-mapping, POST /clo (plo_ids), PUT /clo/{id} (plo_ids)

ไม่ต้องทดสอบ app/routes/course_import.py (มคอ.3 import) เพราะ query PLO ที่นั่นกรองด้วย
payload.curriculum_id อยู่แล้ว ข้ามหลักสูตรไม่ได้โดยโครงสร้าง (ดู docstring ของ
curriculum_match_check.py)"""
from __future__ import annotations

import pytest

from app.models import CLO, Course, Curriculum, PLO


@pytest.fixture()
def two_curricula(db_session, admin_user):
    """หลักสูตร A (มีวิชา+CLO) กับหลักสูตร B (มีแค่ PLO) แยกกันคนละหลักสูตร - ใช้สร้างกรณีข้ามหลักสูตร"""
    curriculum_a = Curriculum(name="Test Curriculum A (cross-curriculum)", year=2569)
    curriculum_b = Curriculum(name="Test Curriculum B (cross-curriculum)", year=2569)
    db_session.add_all([curriculum_a, curriculum_b])
    db_session.flush()

    course_a = Course(
        curriculum_id=curriculum_a.id, course_code="TESTXCUR1", name_th="วิชาทดสอบ A", credit=3
    )
    db_session.add(course_a)
    db_session.flush()

    clo_a = CLO(
        course_id=course_a.id,
        code="CLO1",
        description="ทดสอบ CLO ของหลักสูตร A",
        created_by=admin_user.id,
    )
    plo_a = PLO(curriculum_id=curriculum_a.id, code="PLO-A", description_th="PLO หลักสูตร A", category="ความรู้")
    plo_b = PLO(curriculum_id=curriculum_b.id, code="PLO-B", description_th="PLO หลักสูตร B", category="ความรู้")
    db_session.add_all([clo_a, plo_a, plo_b])
    db_session.commit()
    db_session.refresh(clo_a)
    db_session.refresh(plo_a)
    db_session.refresh(plo_b)

    return {
        "curriculum_a": curriculum_a,
        "curriculum_b": curriculum_b,
        "course_a": course_a,
        "clo_a": clo_a,
        "plo_same": plo_a,  # หลักสูตรเดียวกับ clo_a
        "plo_other": plo_b,  # คนละหลักสูตรกับ clo_a
    }


class TestClopPloMappingEndpoint:
    def test_same_curriculum_succeeds(self, client, two_curricula):
        fx = two_curricula
        resp = client.post(
            "/clo-plo-mapping", json={"clo_id": fx["clo_a"].id, "plo_id": fx["plo_same"].id}
        )
        assert resp.status_code == 201

    def test_cross_curriculum_returns_422(self, client, two_curricula):
        fx = two_curricula
        resp = client.post(
            "/clo-plo-mapping", json={"clo_id": fx["clo_a"].id, "plo_id": fx["plo_other"].id}
        )
        assert resp.status_code == 422
        assert "หลักสูตรเดียวกัน" in resp.json()["detail"]


class TestCreateCloWithPloIds:
    def test_same_curriculum_succeeds(self, client, two_curricula):
        fx = two_curricula
        resp = client.post(
            "/clo",
            json={
                "course_id": fx["course_a"].id,
                "code": "CLO2",
                "description": "ทดสอบ",
                "domain": "knowledge",
                "plo_ids": [fx["plo_same"].id],
            },
        )
        assert resp.status_code == 201

    def test_cross_curriculum_returns_422(self, client, two_curricula):
        fx = two_curricula
        resp = client.post(
            "/clo",
            json={
                "course_id": fx["course_a"].id,
                "code": "CLO2",
                "description": "ทดสอบ",
                "domain": "knowledge",
                "plo_ids": [fx["plo_other"].id],
            },
        )
        assert resp.status_code == 422
        assert "หลักสูตรเดียวกัน" in resp.json()["detail"]


class TestUpdateCloWithPloIds:
    def test_same_curriculum_succeeds(self, client, two_curricula):
        fx = two_curricula
        resp = client.put(
            f"/clo/{fx['clo_a'].id}", json={"plo_ids": [fx["plo_same"].id]}
        )
        assert resp.status_code == 200

    def test_cross_curriculum_returns_422(self, client, two_curricula):
        fx = two_curricula
        resp = client.put(
            f"/clo/{fx['clo_a'].id}", json={"plo_ids": [fx["plo_other"].id]}
        )
        assert resp.status_code == 422
        assert "หลักสูตรเดียวกัน" in resp.json()["detail"]
