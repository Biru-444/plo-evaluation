"""Tests สำหรับ assessment_item.domain (ด้านการเรียนรู้ของงานประเมิน - ค่าชุดเดียวกับ clo.domain)"""
from __future__ import annotations

import pytest

from app.models import Course, CourseOffering, Curriculum


@pytest.fixture()
def offering(db_session):
    curriculum = Curriculum(name="Test Curriculum Item Domain", year=2569)
    db_session.add(curriculum)
    db_session.flush()
    course = Course(curriculum_id=curriculum.id, course_code="TESTDOM1", name_th="วิชาทดสอบประเภทงาน", credit=3)
    db_session.add(course)
    db_session.flush()
    offering = CourseOffering(course_id=course.id, academic_year=2569, semester=1, section="1")
    db_session.add(offering)
    db_session.commit()
    return offering


def _payload(offering_id: int, **overrides):
    body = {"offering_id": offering_id, "name": "สอบกลางภาค", "type": "midterm", "total_score": 30}
    body.update(overrides)
    return body


def test_create_with_domain_returns_it(client, offering):
    resp = client.post("/assessment-items", json=_payload(offering.id, domain="skills"))
    assert resp.status_code == 201
    assert resp.json()["domain"] == "skills"


def test_create_without_domain_is_null(client, offering):
    resp = client.post("/assessment-items", json=_payload(offering.id))
    assert resp.status_code == 201
    assert resp.json()["domain"] is None


def test_create_rejects_unknown_domain(client, offering):
    resp = client.post("/assessment-items", json=_payload(offering.id, domain="ความรู้"))
    assert resp.status_code == 422


def test_update_domain(client, offering):
    item_id = client.post("/assessment-items", json=_payload(offering.id, domain="knowledge")).json()["id"]
    resp = client.put(f"/assessment-items/{item_id}", json={"domain": "ethics"})
    assert resp.status_code == 200
    assert resp.json()["domain"] == "ethics"
