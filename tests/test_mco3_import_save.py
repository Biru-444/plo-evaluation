"""
Tests สำหรับ POST /courses/import-from-mco3/save (Phase 2 ของฟีเจอร์ "นำเข้าข้อมูลวิชาจาก มคอ.3
ด้วย AI" - ดู app/routes/course_import.py) บันทึก Course + CLO + CLOPLOMapping + StudyPlan (แผน
มาตรฐาน cohort_year=NULL) จริงจากผลลัพธ์ที่แอดมินตรวจ/แก้ไขแล้วใน Phase 3 (test เหล่านี้ยิง JSON ตรง
เหมือนเป็นผลลัพธ์ที่ผ่านการตรวจแล้ว - year_level/semester คือค่าที่แอดมินยืนยันแล้วจากการเดา
semester_display อัตโนมัติฝั่ง frontend, ดู module docstring ของ app/schemas/course_import.py)

ต่างจาก tests/test_mco3_import_extended.py (Phase 1) ตรงที่ endpoint นี้ไม่เรียก Gemini เลย - เป็น
DB write ธรรมดา จึง deterministic เต็มร้อย ไม่ต้อง skip ตาม GEMINI_API_KEY
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.auth import get_current_user
from app.database import get_db
from app.main import app
from app.models import CLO, CLOPLOMapping, Course, Curriculum, PLO, StudyPlan, User


@pytest.fixture()
def curriculum(db_session):
    curriculum = Curriculum(name="Test Curriculum MCO3 Save", year=2569)
    db_session.add(curriculum)
    db_session.commit()
    db_session.refresh(curriculum)
    return curriculum


@pytest.fixture()
def make_client(db_session):
    """เหมือน conftest.py's `client` fixture แต่รับ user ที่จะให้เป็น current_user ได้ (ไม่ hardcode
    admin_user) - ใช้ทดสอบว่า non-admin โดน 403 (ก๊อปจาก test_clo_plo_mapping.py's fixture เดียวกัน
    เพราะ pytest fixture ไม่แชร์ข้ามไฟล์นอก conftest.py)"""

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
def plos(db_session, curriculum):
    """PLO1/PLO2 ของหลักสูตรทดสอบนี้ - ใช้ทดสอบ clo_plo_mapping ที่ resolve ผ่าน plo_code จริง"""
    rows = [
        PLO(curriculum_id=curriculum.id, code="PLO1", description_th="ทดสอบ PLO1", category="ความรู้"),
        PLO(curriculum_id=curriculum.id, code="PLO2", description_th="ทดสอบ PLO2", category="ทักษะ"),
    ]
    db_session.add_all(rows)
    db_session.commit()
    for r in rows:
        db_session.refresh(r)
    return rows


def _payload(curriculum_id: int, course_code: str = "TEST101", **overrides):
    body = {
        "curriculum_id": curriculum_id,
        "course_code": course_code,
        "name_th": "วิชาทดสอบ",
        "name_en": "Test Course",
        "credit": 3,
        "category": "วิชาแกน",
        "clos": [
            {"code": "CLO1", "description": "คำอธิบาย CLO1", "domain": "knowledge"},
            {"code": "CLO2", "description": "คำอธิบาย CLO2", "domain": "skills"},
        ],
        "clo_plo_mapping": [
            {"clo_code": "CLO1", "plo_code": "PLO1", "weight_percent": 100},
            {"clo_code": "CLO2", "plo_code": "PLO2", "weight_percent": 100},
        ],
        "year_level": 1,
        "semester": 1,
    }
    body.update(overrides)
    return body


def test_save_creates_course_clos_and_mapping(client, db_session, curriculum, plos):
    resp = client.post("/courses/import-from-mco3/save", json=_payload(curriculum.id))
    assert resp.status_code == 201
    body = resp.json()

    assert body["course"]["course_code"] == "TEST101"
    assert body["course"]["curriculum_id"] == curriculum.id
    assert len(body["clos"]) == 2
    clo_codes = {c["code"] for c in body["clos"]}
    assert clo_codes == {"CLO1", "CLO2"}
    domains = {c["code"]: c["domain"] for c in body["clos"]}
    assert domains == {"CLO1": "knowledge", "CLO2": "skills"}

    # ยืนยันในฐานข้อมูลจริงด้วย ไม่ใช่แค่เชื่อ response
    course = db_session.query(Course).filter(Course.course_code == "TEST101").first()
    assert course is not None
    clos_in_db = db_session.query(CLO).filter(CLO.course_id == course.id).all()
    assert len(clos_in_db) == 2
    mappings_in_db = (
        db_session.query(CLOPLOMapping).filter(CLOPLOMapping.clo_id.in_([c.id for c in clos_in_db])).all()
    )
    assert len(mappings_in_db) == 2


def test_save_creates_standard_study_plan_from_year_level_and_semester(client, db_session, curriculum, plos):
    """study_plan ต้องถูกสร้างคู่กับ course เสมอในคำขอเดียวกัน - cohort_year เป็น NULL เสมอ (แผน
    มาตรฐาน มคอ.3 ไม่มีแนวคิด "รุ่นนักศึกษา") year_level/semester ตรงกับค่าที่ส่งมาเป๊ะ"""
    resp = client.post(
        "/courses/import-from-mco3/save",
        json=_payload(curriculum.id, course_code="TEST105", year_level=2, semester=1),
    )
    assert resp.status_code == 201
    body = resp.json()

    assert body["study_plan"]["curriculum_id"] == curriculum.id
    assert body["study_plan"]["cohort_year"] is None
    assert body["study_plan"]["year_level"] == 2
    assert body["study_plan"]["semester"] == 1
    assert body["study_plan"]["course_id"] == body["course"]["id"]

    course = db_session.query(Course).filter(Course.course_code == "TEST105").first()
    study_plan_in_db = db_session.query(StudyPlan).filter(StudyPlan.course_id == course.id).one()
    assert study_plan_in_db.cohort_year is None
    assert study_plan_in_db.year_level == 2
    assert study_plan_in_db.semester == 1


@pytest.mark.parametrize("bad_year_level", [0, 5])
def test_save_rejects_year_level_out_of_range_with_422(client, curriculum, plos, bad_year_level):
    resp = client.post(
        "/courses/import-from-mco3/save",
        json=_payload(curriculum.id, course_code="TEST106", year_level=bad_year_level),
    )
    assert resp.status_code == 422


@pytest.mark.parametrize("bad_semester", [0, 4])
def test_save_rejects_semester_out_of_range_with_422(client, curriculum, plos, bad_semester):
    resp = client.post(
        "/courses/import-from-mco3/save",
        json=_payload(curriculum.id, course_code="TEST107", semester=bad_semester),
    )
    assert resp.status_code == 422


def test_save_rejects_duplicate_course_code_with_409_naming_existing_course_id(
    client, db_session, curriculum, plos
):
    first = client.post("/courses/import-from-mco3/save", json=_payload(curriculum.id))
    assert first.status_code == 201
    existing_course_id = first.json()["course"]["id"]

    second = client.post("/courses/import-from-mco3/save", json=_payload(curriculum.id))
    assert second.status_code == 409
    assert str(existing_course_id) in second.json()["detail"]


def test_save_rejects_unknown_clo_code_in_mapping_with_400(client, curriculum, plos):
    payload = _payload(curriculum.id, course_code="TEST102")
    payload["clo_plo_mapping"] = [
        {"clo_code": "CLO_NOT_IN_LIST", "plo_code": "PLO1", "weight_percent": 100}
    ]
    resp = client.post("/courses/import-from-mco3/save", json=payload)
    assert resp.status_code == 400
    assert "CLO_NOT_IN_LIST" in resp.json()["detail"]


def test_save_rejects_unknown_plo_code_in_mapping_with_400(client, curriculum, plos):
    payload = _payload(curriculum.id, course_code="TEST103")
    payload["clo_plo_mapping"] = [
        {"clo_code": "CLO1", "plo_code": "PLO_DOES_NOT_EXIST", "weight_percent": 100}
    ]
    resp = client.post("/courses/import-from-mco3/save", json=payload)
    assert resp.status_code == 400
    assert "PLO_DOES_NOT_EXIST" in resp.json()["detail"]


def test_save_rejects_invalid_curriculum_id_with_404(client):
    resp = client.post("/courses/import-from-mco3/save", json=_payload(999999))
    assert resp.status_code == 404


def test_save_is_atomic_nothing_persists_when_clo_codes_collide_within_payload(
    client, db_session, curriculum, plos
):
    """สองรายการใน clos ใช้ code ซ้ำกันเอง ('CLO1' ทั้งคู่) - ผ่านการเช็ค clo_plo_mapping reference ไป
    ได้ (เพราะ 'CLO1' มีอยู่ใน clo_codes_in_payload จริง) แต่จะชน UniqueConstraint(course_id, code)
    ตอน flush ตัวที่สอง - ต้อง rollback ทั้งก้อน ไม่เหลือ course ค้างในฐานข้อมูลเลย"""
    # เก็บ id ไว้ก่อนยิง request เสมอ - db.rollback() ฝั่ง route (ภายใน try/except IntegrityError) ทำให้
    # object ของเทสนี้ (สร้างผ่าน db_session เดียวกัน) หลุดสถานะ expired ไปด้วย เข้าถึง .id ใหม่หลังจากนี้
    # จะ raise ObjectDeletedError (สะท้อนพฤติกรรมจริงของ nested transaction ไม่ใช่บั๊ก)
    curriculum_id = curriculum.id
    payload = _payload(curriculum_id, course_code="TEST104")
    payload["clos"] = [
        {"code": "CLO1", "description": "อันแรก", "domain": None},
        {"code": "CLO1", "description": "อันที่สอง รหัสซ้ำ", "domain": None},
    ]
    payload["clo_plo_mapping"] = []

    resp = client.post("/courses/import-from-mco3/save", json=payload)
    assert resp.status_code == 409

    # atomic จริง - course ที่ควรจะถูกสร้างก่อนหน้าต้องไม่ค้างอยู่ในฐานข้อมูล (การชนเกิดตอนสร้าง CLO ตัว
    # ที่สอง ก่อนถึงขั้นตอนสร้าง study_plan ด้วยซ้ำ - แต่ยืนยันด้วยว่าไม่มี study_plan กำพร้าหลงเหลืออยู่
    # เลยเช่นกัน สะท้อนว่าทั้งทรานแซกชัน rollback จริง ไม่ใช่แค่ course)
    orphaned_course = db_session.query(Course).filter(Course.course_code == "TEST104").first()
    assert orphaned_course is None
    assert db_session.query(StudyPlan).filter(StudyPlan.curriculum_id == curriculum_id).count() == 0


def test_save_requires_admin(make_client, db_session, curriculum, plos):
    instructor = User(
        username="test-instructor-mco3-save",
        password="unused-in-tests",
        first_name="Test",
        last_name="Instructor",
        role="instructor",
    )
    db_session.add(instructor)
    db_session.commit()
    db_session.refresh(instructor)

    instructor_client = make_client(instructor)
    resp = instructor_client.post("/courses/import-from-mco3/save", json=_payload(curriculum.id))
    assert resp.status_code == 403
