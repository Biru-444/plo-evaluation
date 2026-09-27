"""
Tests สำหรับ GET /plo/{plo_id}/linked-courses (app/routes/plo.py) - รายวิชาที่เชื่อมกับ PLO ผ่าน
clo_plo_mapping โดยตรง (คนละที่มากับ course-plan ที่มาจาก course_plo/มคอ.2) ใช้แสดงในหน้ารายละเอียด PLO
(PLODetailPage.jsx) แทนที่ "วิชาตามแผนหลักสูตร (มคอ.2)" เดิม (2026-09)
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.database import get_db
from app.main import app
from app.models import CLO, CLOPLOMapping, Course, Curriculum, PLO


def _make_curriculum_and_plo(db_session, plo_code="PLO1"):
    curriculum = Curriculum(name="Test Curriculum LinkedCourses", year=2569)
    db_session.add(curriculum)
    db_session.flush()

    plo = PLO(curriculum_id=curriculum.id, code=plo_code, description_th="ทดสอบ PLO", category="ความรู้")
    db_session.add(plo)
    db_session.flush()

    return curriculum, plo


def _make_course_with_clo(
    db_session, curriculum_id, course_code, name_th, clo_code, created_by, description="ทดสอบ CLO"
):
    course = Course(curriculum_id=curriculum_id, course_code=course_code, name_th=name_th, credit=3)
    db_session.add(course)
    db_session.flush()

    clo = CLO(
        course_id=course.id,
        code=clo_code,
        description=description,
        pass_threshold_percent=60.0,
        created_by=created_by,
    )
    db_session.add(clo)
    db_session.flush()

    return course, clo


def test_plo_with_no_linked_courses_returns_empty_list(client, db_session):
    _curriculum, plo = _make_curriculum_and_plo(db_session)
    db_session.commit()

    resp = client.get(f"/plo/{plo.id}/linked-courses")
    assert resp.status_code == 200
    assert resp.json() == []


def test_two_courses_linked_to_same_plo(client, db_session, admin_user):
    """ตัวอย่างจากคำสั่ง: ภาษาไทยมี CLO1 เชื่อม PLO1 และคณิตศาสตร์มี CLO2 เชื่อม PLO1"""
    curriculum, plo = _make_curriculum_and_plo(db_session)
    thai_course, thai_clo = _make_course_with_clo(
        db_session, curriculum.id, "THAI101", "ภาษาไทย", "CLO1", admin_user.id, "อธิบายหลักภาษาไทยได้"
    )
    math_course, math_clo = _make_course_with_clo(
        db_session, curriculum.id, "MATH101", "คณิตศาสตร์", "CLO2", admin_user.id, "คำนวณเลขพื้นฐานได้"
    )
    db_session.add_all(
        [
            CLOPLOMapping(clo_id=thai_clo.id, plo_id=plo.id, weight_percent=100),
            CLOPLOMapping(clo_id=math_clo.id, plo_id=plo.id, weight_percent=100),
        ]
    )
    db_session.commit()

    resp = client.get(f"/plo/{plo.id}/linked-courses")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 2
    # เรียงตามรหัสวิชา (MATH101 < THAI101)
    assert body[0]["course_code"] == "MATH101"
    assert body[0]["clos"][0]["clo_code"] == "CLO2"
    assert body[1]["course_code"] == "THAI101"
    assert body[1]["clos"][0]["clo_code"] == "CLO1"


def test_course_with_multiple_clos_linked_to_same_plo_groups_into_one_course(client, db_session, admin_user):
    curriculum, plo = _make_curriculum_and_plo(db_session)
    course = Course(curriculum_id=curriculum.id, course_code="SCI101", name_th="วิทยาศาสตร์", credit=3)
    db_session.add(course)
    db_session.flush()

    clo1 = CLO(
        course_id=course.id, code="CLO1", description="ทดสอบ CLO1", pass_threshold_percent=60.0,
        created_by=admin_user.id,
    )
    clo2 = CLO(
        course_id=course.id, code="CLO2", description="ทดสอบ CLO2", pass_threshold_percent=60.0,
        created_by=admin_user.id,
    )
    db_session.add_all([clo1, clo2])
    db_session.flush()

    db_session.add_all(
        [
            CLOPLOMapping(clo_id=clo1.id, plo_id=plo.id, weight_percent=50),
            CLOPLOMapping(clo_id=clo2.id, plo_id=plo.id, weight_percent=50),
        ]
    )
    db_session.commit()

    resp = client.get(f"/plo/{plo.id}/linked-courses")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["course_code"] == "SCI101"
    assert len(body[0]["clos"]) == 2
    assert [c["clo_code"] for c in body[0]["clos"]] == ["CLO1", "CLO2"]


def test_clo_linked_to_a_different_plo_does_not_appear(client, db_session, admin_user):
    curriculum, plo = _make_curriculum_and_plo(db_session, plo_code="PLO1")
    other_plo = PLO(
        curriculum_id=curriculum.id, code="PLO2", description_th="ทดสอบ PLO อื่น", category="ทักษะ"
    )
    db_session.add(other_plo)
    db_session.flush()

    _course, clo = _make_course_with_clo(
        db_session, curriculum.id, "ENG101", "ภาษาอังกฤษ", "CLO1", admin_user.id
    )
    db_session.add(CLOPLOMapping(clo_id=clo.id, plo_id=other_plo.id, weight_percent=100))
    db_session.commit()

    resp = client.get(f"/plo/{plo.id}/linked-courses")
    assert resp.status_code == 200
    assert resp.json() == []


def test_not_logged_in_returns_401(db_session):
    _curriculum, plo = _make_curriculum_and_plo(db_session)
    db_session.commit()

    def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    anonymous_client = TestClient(app)
    resp = anonymous_client.get(f"/plo/{plo.id}/linked-courses")
    assert resp.status_code == 401
    app.dependency_overrides.clear()


def test_nonexistent_plo_returns_404(client):
    resp = client.get("/plo/999999/linked-courses")
    assert resp.status_code == 404
