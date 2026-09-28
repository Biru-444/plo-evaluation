"""Tests สำหรับ DELETE /clo/{id} ที่บล็อกด้วย 409 ถ้า CLO ผูกกับ item_clo หรือ clo_plo_mapping อยู่
(2026-09-28) - กฎเดียวกันทุก role รวมแอดมินด้วย (ผู้ใช้ยืนยันแล้ว) - เดิม cascade ลบเงียบๆ ไม่เตือนเลย

ใช้แพทเทิร์นเดียวกับ tests/test_clo_plo_mapping.py (make_client fixture ทดสอบ ownership)"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.auth import get_current_user
from app.database import get_db
from app.main import app
from app.models import (
    CLO,
    CLOPLOMapping,
    Course,
    CourseOffering,
    Curriculum,
    ItemCLO,
    AssessmentItem,
    PLO,
    User,
)


@pytest.fixture()
def make_client(db_session):
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


@pytest.fixture()
def fx(db_session):
    curriculum = Curriculum(name="Test Curriculum CLO Delete Guard", year=2569)
    db_session.add(curriculum)
    db_session.flush()

    course = Course(curriculum_id=curriculum.id, course_code="TESTDEL1", name_th="วิชาทดสอบ", credit=3)
    db_session.add(course)
    db_session.flush()

    owner = User(username="owner-del", password="x", first_name="เจ้าของ", last_name="วิชา", role="instructor")
    other = User(username="other-del", password="x", first_name="คนอื่น", last_name="ไม่เกี่ยว", role="instructor")
    admin = User(username="admin-del", password="x", first_name="แอดมิน", last_name="ทดสอบ", role="admin")
    db_session.add_all([owner, other, admin])
    db_session.flush()

    offering = CourseOffering(
        course_id=course.id, instructor_id=owner.id, academic_year=2569, semester=1, section="1",
    )
    db_session.add(offering)
    db_session.flush()

    plo = PLO(curriculum_id=curriculum.id, code="PLO-DEL", description_th="ทดสอบ", category="ความรู้")
    db_session.add(plo)
    db_session.flush()

    clo_unused = CLO(course_id=course.id, code="CLO1", description="ยังไม่ถูกใช้", created_by=owner.id)
    clo_with_item = CLO(course_id=course.id, code="CLO2", description="ผูกงานประเมินแล้ว", created_by=owner.id)
    clo_with_plo = CLO(course_id=course.id, code="CLO3", description="ผูก PLO แล้ว", created_by=owner.id)
    db_session.add_all([clo_unused, clo_with_item, clo_with_plo])
    db_session.flush()

    item = AssessmentItem(offering_id=offering.id, name="สอบกลางภาค", type="midterm", total_score=100)
    db_session.add(item)
    db_session.flush()
    db_session.add(ItemCLO(item_id=item.id, clo_id=clo_with_item.id, weight_percent=100))
    db_session.add(CLOPLOMapping(clo_id=clo_with_plo.id, plo_id=plo.id, weight_percent=100))
    db_session.commit()

    return {
        "curriculum": curriculum, "course": course, "offering": offering, "plo": plo,
        "owner": owner, "other": other, "admin": admin,
        "clo_unused": clo_unused, "clo_with_item": clo_with_item, "clo_with_plo": clo_with_plo,
    }


class TestDeleteUnusedCLO:
    def test_owning_instructor_can_delete(self, make_client, fx):
        client = make_client(fx["owner"])
        resp = client.delete(f"/clo/{fx['clo_unused'].id}")
        assert resp.status_code == 204

    def test_admin_can_delete(self, make_client, fx):
        client = make_client(fx["admin"])
        resp = client.delete(f"/clo/{fx['clo_unused'].id}")
        assert resp.status_code == 204

    def test_non_owning_instructor_returns_403(self, make_client, fx):
        client = make_client(fx["other"])
        resp = client.delete(f"/clo/{fx['clo_unused'].id}")
        assert resp.status_code == 403

    def test_nonexistent_returns_404(self, make_client, fx):
        client = make_client(fx["owner"])
        resp = client.delete("/clo/999999")
        assert resp.status_code == 404


class TestDeleteUsedCLOBlocked:
    def test_used_by_item_clo_returns_409_for_instructor(self, make_client, fx, db_session):
        client = make_client(fx["owner"])
        resp = client.delete(f"/clo/{fx['clo_with_item'].id}")
        assert resp.status_code == 409
        assert "งานประเมิน" in resp.json()["detail"]
        assert db_session.get(CLO, fx["clo_with_item"].id) is not None

    def test_used_by_item_clo_returns_409_for_admin(self, make_client, fx):
        client = make_client(fx["admin"])
        resp = client.delete(f"/clo/{fx['clo_with_item'].id}")
        assert resp.status_code == 409

    def test_used_by_plo_mapping_returns_409_for_instructor(self, make_client, fx):
        client = make_client(fx["owner"])
        resp = client.delete(f"/clo/{fx['clo_with_plo'].id}")
        assert resp.status_code == 409
        assert "PLO" in resp.json()["detail"]

    def test_used_by_plo_mapping_returns_409_for_admin(self, make_client, fx):
        client = make_client(fx["admin"])
        resp = client.delete(f"/clo/{fx['clo_with_plo'].id}")
        assert resp.status_code == 409

    def test_non_owning_instructor_still_gets_403_not_409(self, make_client, fx):
        """403 (ไม่ใช่เจ้าของวิชา) ต้องมาก่อน 409 (ถูกใช้แล้ว) เสมอ - ไม่รั่วข้อมูลว่า CLO ถูกใช้อยู่หรือไม่
        ให้คนที่ไม่มีสิทธิ์เห็น"""
        client = make_client(fx["other"])
        resp = client.delete(f"/clo/{fx['clo_with_item'].id}")
        assert resp.status_code == 403
