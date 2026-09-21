"""
Tests สำหรับ /clo-plo-mapping (list/create/delete) ที่คืนกลับมาใหม่ (ดู
app/routes/clo_plo_mapping.py) รวมถึง plo_ids เสริมที่ POST/PUT /clo รับได้ในคำขอเดียวกัน (ดู
app/routes/clo.py) - ครอบคลุมทั้ง happy path, ownership check (admin ผ่านเสมอ / อาจารย์เจ้าของวิชา
ผ่านได้ / อาจารย์คนอื่นโดน 403), 404, และ 409 (ซ้ำ/อ้าง PLO ที่ไม่มีจริง)

ownership check ต้องทดสอบด้วย current_user ที่ไม่ใช่ admin - conftest.py's `client` fixture ผูกกับ
admin_user ตรงๆ จึงมี `make_client` fixture ของไฟล์นี้เองที่สร้าง TestClient ใหม่ override
get_current_user เป็น user ที่ระบุได้ (เหมือน `client` fixture ทุกประการ แต่พารามิเตอร์ user ได้)
"""
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
    PLO,
    User,
)


@pytest.fixture()
def make_client(db_session):
    """เหมือน conftest.py's `client` fixture แต่รับ user ที่จะให้เป็น current_user ได้ (ไม่ hardcode
    admin_user) - ใช้ทดสอบ ownership check ที่ต้องสวมบทเป็นอาจารย์คนอื่นที่ไม่ใช่แอดมิน"""

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


def _make_fixtures(db_session):
    """หลักสูตร + วิชา + PLO 2 ข้อ + อาจารย์เจ้าของวิชา (owner) + อาจารย์อีกคนที่ไม่ได้สอนวิชานี้
    (other) + CLO 1 ตัวของวิชานั้น - คืน dict ให้ประกอบต่อในแต่ละเทส"""
    curriculum = Curriculum(name="Test Curriculum CPM", year=2569)
    db_session.add(curriculum)
    db_session.flush()

    course = Course(curriculum_id=curriculum.id, course_code="TESTCPM1", name_th="วิชาทดสอบ", credit=3)
    db_session.add(course)
    db_session.flush()

    plo_a = PLO(curriculum_id=curriculum.id, code="PLO-A", description_th="ทดสอบ PLO A", category="ความรู้")
    plo_b = PLO(curriculum_id=curriculum.id, code="PLO-B", description_th="ทดสอบ PLO B", category="ทักษะ")
    db_session.add_all([plo_a, plo_b])
    db_session.flush()

    owner = User(username="owner-instr", password="x", first_name="เจ้าของ", last_name="วิชา", role="instructor")
    other = User(username="other-instr", password="x", first_name="คนอื่น", last_name="ไม่เกี่ยว", role="instructor")
    db_session.add_all([owner, other])
    db_session.flush()

    offering = CourseOffering(
        course_id=course.id, instructor_id=owner.id, academic_year=2569, semester=1, section="1"
    )
    db_session.add(offering)
    db_session.flush()

    clo = CLO(
        course_id=course.id,
        code="CLO1",
        description="ทดสอบ CLO1",
        pass_threshold_percent=60.00,
        created_by=owner.id,
    )
    db_session.add(clo)
    db_session.flush()

    return {
        "curriculum": curriculum,
        "course": course,
        "plo_a": plo_a,
        "plo_b": plo_b,
        "owner": owner,
        "other": other,
        "clo": clo,
    }


def test_create_as_admin_succeeds(client, db_session):
    fx = _make_fixtures(db_session)
    db_session.commit()

    resp = client.post("/clo-plo-mapping", json={"clo_id": fx["clo"].id, "plo_id": fx["plo_a"].id})
    assert resp.status_code == 201
    body = resp.json()
    assert body["clo_id"] == fx["clo"].id
    assert body["plo_id"] == fx["plo_a"].id


def test_create_as_owning_instructor_succeeds(make_client, db_session):
    fx = _make_fixtures(db_session)
    db_session.commit()

    resp = make_client(fx["owner"]).post(
        "/clo-plo-mapping", json={"clo_id": fx["clo"].id, "plo_id": fx["plo_a"].id}
    )
    assert resp.status_code == 201


def test_create_as_non_owning_instructor_returns_403(make_client, db_session):
    fx = _make_fixtures(db_session)
    db_session.commit()

    resp = make_client(fx["other"]).post(
        "/clo-plo-mapping", json={"clo_id": fx["clo"].id, "plo_id": fx["plo_a"].id}
    )
    assert resp.status_code == 403


def test_create_duplicate_returns_409(client, db_session):
    fx = _make_fixtures(db_session)
    db_session.add(CLOPLOMapping(clo_id=fx["clo"].id, plo_id=fx["plo_a"].id))
    db_session.commit()

    resp = client.post("/clo-plo-mapping", json={"clo_id": fx["clo"].id, "plo_id": fx["plo_a"].id})
    assert resp.status_code == 409


def test_create_invalid_plo_id_returns_409(client, db_session):
    fx = _make_fixtures(db_session)
    db_session.commit()

    resp = client.post("/clo-plo-mapping", json={"clo_id": fx["clo"].id, "plo_id": 999999})
    assert resp.status_code == 409


def test_create_invalid_clo_id_returns_404(client, db_session):
    fx = _make_fixtures(db_session)
    db_session.commit()

    resp = client.post("/clo-plo-mapping", json={"clo_id": 999999, "plo_id": fx["plo_a"].id})
    assert resp.status_code == 404


def test_list_filters_by_clo_id_and_plo_id(client, db_session):
    fx = _make_fixtures(db_session)
    db_session.add_all(
        [
            CLOPLOMapping(clo_id=fx["clo"].id, plo_id=fx["plo_a"].id),
            CLOPLOMapping(clo_id=fx["clo"].id, plo_id=fx["plo_b"].id),
        ]
    )
    db_session.commit()

    resp = client.get(f"/clo-plo-mapping?clo_id={fx['clo'].id}")
    assert resp.status_code == 200
    assert {row["plo_id"] for row in resp.json()} == {fx["plo_a"].id, fx["plo_b"].id}

    resp = client.get(f"/clo-plo-mapping?plo_id={fx['plo_a'].id}")
    assert resp.status_code == 200
    assert [row["plo_id"] for row in resp.json()] == [fx["plo_a"].id]


def test_delete_as_admin_succeeds(client, db_session):
    fx = _make_fixtures(db_session)
    mapping = CLOPLOMapping(clo_id=fx["clo"].id, plo_id=fx["plo_a"].id)
    db_session.add(mapping)
    db_session.commit()
    mapping_id = mapping.id

    resp = client.delete(f"/clo-plo-mapping/{mapping_id}")
    assert resp.status_code == 204
    assert db_session.get(CLOPLOMapping, mapping_id) is None


def test_delete_as_non_owning_instructor_returns_403(make_client, db_session):
    fx = _make_fixtures(db_session)
    mapping = CLOPLOMapping(clo_id=fx["clo"].id, plo_id=fx["plo_a"].id)
    db_session.add(mapping)
    db_session.commit()

    resp = make_client(fx["other"]).delete(f"/clo-plo-mapping/{mapping.id}")
    assert resp.status_code == 403


def test_delete_nonexistent_returns_404(client, db_session):
    resp = client.delete("/clo-plo-mapping/999999")
    assert resp.status_code == 404


def test_create_clo_with_plo_ids_maps_in_one_request(client, db_session, admin_user):
    """POST /clo พร้อม plo_ids - ต้องสร้าง CLO และแถว clo_plo_mapping ให้ครบทุก plo_id ในคำขอเดียว"""
    fx = _make_fixtures(db_session)
    db_session.commit()

    resp = client.post(
        "/clo",
        json={
            "course_id": fx["course"].id,
            "code": "CLO2",
            "description": "ทดสอบ CLO2",
            "plo_ids": [fx["plo_a"].id, fx["plo_b"].id],
        },
    )
    assert resp.status_code == 201
    clo_id = resp.json()["id"]

    mapped_plo_ids = {
        row.plo_id
        for row in db_session.query(CLOPLOMapping).filter(CLOPLOMapping.clo_id == clo_id).all()
    }
    assert mapped_plo_ids == {fx["plo_a"].id, fx["plo_b"].id}


def test_update_clo_plo_ids_replaces_existing_mapping(client, db_session):
    """PUT /clo/{id} พร้อม plo_ids ใหม่ - ต้องแทนที่ mapping เดิมทั้งหมด (ถอด PLO-A ออก เหลือแค่ PLO-B)"""
    fx = _make_fixtures(db_session)
    db_session.add(CLOPLOMapping(clo_id=fx["clo"].id, plo_id=fx["plo_a"].id))
    db_session.commit()

    resp = client.put(f"/clo/{fx['clo'].id}", json={"plo_ids": [fx["plo_b"].id]})
    assert resp.status_code == 200

    mapped_plo_ids = {
        row.plo_id
        for row in db_session.query(CLOPLOMapping).filter(CLOPLOMapping.clo_id == fx["clo"].id).all()
    }
    assert mapped_plo_ids == {fx["plo_b"].id}


def test_update_clo_without_plo_ids_leaves_mapping_untouched(client, db_session):
    """PUT /clo/{id} ที่ไม่ส่ง plo_ids มาเลย (แก้แค่ description) - mapping เดิมต้องไม่ถูกแตะ"""
    fx = _make_fixtures(db_session)
    db_session.add(CLOPLOMapping(clo_id=fx["clo"].id, plo_id=fx["plo_a"].id))
    db_session.commit()

    resp = client.put(f"/clo/{fx['clo'].id}", json={"description": "แก้คำอธิบายอย่างเดียว"})
    assert resp.status_code == 200

    mapped_plo_ids = {
        row.plo_id
        for row in db_session.query(CLOPLOMapping).filter(CLOPLOMapping.clo_id == fx["clo"].id).all()
    }
    assert mapped_plo_ids == {fx["plo_a"].id}
