"""
Tests สำหรับ GET /courses/{course_id}/enrolled-students และ plo_id (optional) query param ใหม่ -
ครอบคลุมทั้งพฤติกรรมเดิม (ไม่ส่ง plo_id ต้องเหมือนเดิมทุกประการ ไม่กระทบ caller เดิม) และพฤติกรรมใหม่
(clo_mastery_percent) รวมถึง edge case คะแนนไม่ครบ/ไม่มีเลย

ทุกเทสสร้างข้อมูลของตัวเองใน db_session (rollback อัตโนมัติหลังจบเทสตาม conftest.py) ไม่พึ่งข้อมูลที่มี
อยู่ก่อนในฐานข้อมูลทดสอบเลย เพื่อไม่ให้เทสตัวหนึ่งกระทบอีกตัว
"""
from __future__ import annotations

from app.models import (
    CLO,
    CLOPLOMapping,
    Course,
    CoursePLO,
    CourseOffering,
    Curriculum,
    Enrollment,
    AssessmentItem,
    ItemCLO,
    PLO,
    Student,
    StudentScore,
)


def _make_base_fixtures(db_session, *, primary_for_plo: bool = True):
    """สร้าง curriculum + course + PLO + course_plo(primary) + course_offering ตัวตั้งต้นที่ใช้ร่วมกัน
    ทุกเทสในไฟล์นี้ - คืน dict ของ object ที่สร้างไว้ให้ประกอบต่อ"""
    curriculum = Curriculum(name="Test Curriculum", year=2569)
    db_session.add(curriculum)
    db_session.flush()

    course = Course(
        curriculum_id=curriculum.id, course_code="TEST101", name_th="วิชาทดสอบ", credit=3
    )
    db_session.add(course)
    db_session.flush()

    plo = PLO(curriculum_id=curriculum.id, code="PLO1", description_th="ทดสอบ PLO")
    db_session.add(plo)
    db_session.flush()

    if primary_for_plo:
        db_session.add(
            CoursePLO(course_id=course.id, plo_id=plo.id, responsibility_level="primary")
        )

    offering = CourseOffering(
        course_id=course.id, academic_year=2569, semester=1, section="1"
    )
    db_session.add(offering)
    db_session.flush()

    return {"curriculum": curriculum, "course": course, "plo": plo, "offering": offering}


def _enroll_student(db_session, *, curriculum_id: int, offering_id: int, student_id: str) -> Student:
    student = Student(
        id=student_id,
        curriculum_id=curriculum_id,
        first_name="ทดสอบ",
        last_name=student_id,
        cohort_year=69,
        current_year_level=1,
    )
    db_session.add(student)
    db_session.add(Enrollment(student_id=student.id, offering_id=offering_id))
    db_session.flush()
    return student


def _add_clo_with_score(
    db_session,
    *,
    course_id: int,
    offering_id: int,
    plo_id: int,
    clo_code: str,
    admin_user_id: int,
    student_id: str | None,
    score_obtained: float | None,
    total_score: float = 100.0,
) -> CLO:
    """สร้าง CLO 1 ตัวผูกกับ plo_id ที่ให้มา พร้อม assessment_item+item_clo 1 ชุด - ถ้า student_id +
    score_obtained ไม่ใช่ None จะกรอกคะแนนให้นักศึกษาคนนั้นด้วย (ไม่กรอก = จำลอง "ยังไม่มีคะแนนเลย")"""
    clo = CLO(
        course_id=course_id,
        code=clo_code,
        description=f"ทดสอบ {clo_code}",
        pass_threshold_percent=60.00,
        created_by=admin_user_id,
    )
    db_session.add(clo)
    db_session.flush()

    db_session.add(CLOPLOMapping(clo_id=clo.id, plo_id=plo_id, weight_percent=100.00))

    item = AssessmentItem(
        offering_id=offering_id, name=f"item-{clo_code}", type="quiz", total_score=total_score
    )
    db_session.add(item)
    db_session.flush()

    db_session.add(ItemCLO(item_id=item.id, clo_id=clo.id, weight_percent=100.00))

    if student_id is not None and score_obtained is not None:
        db_session.add(
            StudentScore(item_id=item.id, student_id=student_id, score_obtained=score_obtained)
        )

    db_session.flush()
    return clo


def test_without_plo_id_mastery_is_always_null(client, db_session):
    """ไม่ส่ง plo_id เลย - ต้องเหมือนพฤติกรรมเดิมทุกประการ (clo_mastery_percent เป็น null ทุกคน)"""
    fx = _make_base_fixtures(db_session)
    _enroll_student(
        db_session,
        curriculum_id=fx["curriculum"].id,
        offering_id=fx["offering"].id,
        student_id="TEST001",
    )
    db_session.commit()

    resp = client.get(f"/courses/{fx['course'].id}/enrolled-students")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["id"] == "TEST001"
    assert body[0]["clo_mastery_percent"] is None


def test_full_score_data_averages_correctly(client, db_session, admin_user):
    """คะแนนครบทุก CLO ที่ผูกกับ PLO นี้ (2 CLO, 90% กับ 70%) -> เฉลี่ย = 80.0"""
    fx = _make_base_fixtures(db_session)
    _enroll_student(
        db_session,
        curriculum_id=fx["curriculum"].id,
        offering_id=fx["offering"].id,
        student_id="TEST001",
    )
    _add_clo_with_score(
        db_session,
        course_id=fx["course"].id,
        offering_id=fx["offering"].id,
        plo_id=fx["plo"].id,
        clo_code="CLO-A",
        admin_user_id=admin_user.id,
        student_id="TEST001",
        score_obtained=90.0,
    )
    _add_clo_with_score(
        db_session,
        course_id=fx["course"].id,
        offering_id=fx["offering"].id,
        plo_id=fx["plo"].id,
        clo_code="CLO-B",
        admin_user_id=admin_user.id,
        student_id="TEST001",
        score_obtained=70.0,
    )
    db_session.commit()

    resp = client.get(f"/courses/{fx['course'].id}/enrolled-students?plo_id={fx['plo'].id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body[0]["clo_mastery_percent"] == 80.0


def test_partial_score_data_skips_missing_clo_not_zero(client, db_session, admin_user):
    """มีคะแนนแค่ 1 ใน 2 CLO ที่ผูกกับ PLO นี้ (60% กับไม่มีคะแนนเลย) -> เฉลี่ยแค่ตัวที่มีข้อมูล = 60.0
    (ไม่ใช่ (60+0)/2=30 - CLO ที่ไม่มีคะแนนเลยต้องไม่ถูกนับเป็น 0)"""
    fx = _make_base_fixtures(db_session)
    _enroll_student(
        db_session,
        curriculum_id=fx["curriculum"].id,
        offering_id=fx["offering"].id,
        student_id="TEST001",
    )
    _add_clo_with_score(
        db_session,
        course_id=fx["course"].id,
        offering_id=fx["offering"].id,
        plo_id=fx["plo"].id,
        clo_code="CLO-A",
        admin_user_id=admin_user.id,
        student_id="TEST001",
        score_obtained=60.0,
    )
    _add_clo_with_score(
        db_session,
        course_id=fx["course"].id,
        offering_id=fx["offering"].id,
        plo_id=fx["plo"].id,
        clo_code="CLO-B",
        admin_user_id=admin_user.id,
        student_id=None,
        score_obtained=None,
    )
    db_session.commit()

    resp = client.get(f"/courses/{fx['course'].id}/enrolled-students?plo_id={fx['plo'].id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body[0]["clo_mastery_percent"] == 60.0


def test_no_score_data_at_all_is_null_not_zero(client, db_session, admin_user):
    """ไม่มีคะแนนใน CLO ไหนของวิชานี้เลย (มี CLO ผูกกับ PLO อยู่ แค่ยังไม่กรอกคะแนน) -> null ไม่ใช่ 0"""
    fx = _make_base_fixtures(db_session)
    _enroll_student(
        db_session,
        curriculum_id=fx["curriculum"].id,
        offering_id=fx["offering"].id,
        student_id="TEST001",
    )
    _add_clo_with_score(
        db_session,
        course_id=fx["course"].id,
        offering_id=fx["offering"].id,
        plo_id=fx["plo"].id,
        clo_code="CLO-A",
        admin_user_id=admin_user.id,
        student_id=None,
        score_obtained=None,
    )
    db_session.commit()

    resp = client.get(f"/courses/{fx['course'].id}/enrolled-students?plo_id={fx['plo'].id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body[0]["clo_mastery_percent"] is None


def test_plo_with_no_clo_plo_mapping_at_all_returns_null_no_error(client, db_session):
    """วิชานี้ไม่มี CLO ผูกกับ PLO ข้อนี้เลย (ไม่มี clo_plo_mapping เข้าเงื่อนไข) - ต้อง null ทุกคน ไม่ error"""
    fx = _make_base_fixtures(db_session)
    _enroll_student(
        db_session,
        curriculum_id=fx["curriculum"].id,
        offering_id=fx["offering"].id,
        student_id="TEST001",
    )
    db_session.commit()

    resp = client.get(f"/courses/{fx['course'].id}/enrolled-students?plo_id={fx['plo'].id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body[0]["clo_mastery_percent"] is None


def test_secondary_course_plo_excluded_same_as_null(client, db_session, admin_user):
    """วิชานี้มี CLO ผูกกับ PLO จริง (clo_plo_mapping) แต่ course_plo เป็น 'secondary' ไม่ใช่ 'primary' -
    ต้องนับเหมือนไม่มีการเชื่อมโยง (null) ตาม _build_plo_requirements ที่นับเฉพาะ primary"""
    fx = _make_base_fixtures(db_session, primary_for_plo=False)
    db_session.add(
        CoursePLO(course_id=fx["course"].id, plo_id=fx["plo"].id, responsibility_level="secondary")
    )
    _enroll_student(
        db_session,
        curriculum_id=fx["curriculum"].id,
        offering_id=fx["offering"].id,
        student_id="TEST001",
    )
    _add_clo_with_score(
        db_session,
        course_id=fx["course"].id,
        offering_id=fx["offering"].id,
        plo_id=fx["plo"].id,
        clo_code="CLO-A",
        admin_user_id=admin_user.id,
        student_id="TEST001",
        score_obtained=95.0,
    )
    db_session.commit()

    resp = client.get(f"/courses/{fx['course'].id}/enrolled-students?plo_id={fx['plo'].id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body[0]["clo_mastery_percent"] is None


def test_invalid_plo_id_returns_404(client, db_session):
    fx = _make_base_fixtures(db_session)
    db_session.commit()

    resp = client.get(f"/courses/{fx['course'].id}/enrolled-students?plo_id=999999")
    assert resp.status_code == 404


def test_invalid_course_id_still_returns_404(client, db_session):
    """course_id ไม่มีจริง ต้อง 404 เหมือนพฤติกรรมเดิม (ก่อนมี plo_id param) ไม่ว่าจะส่ง plo_id มาด้วยหรือไม่"""
    resp = client.get("/courses/999999/enrolled-students")
    assert resp.status_code == 404

    resp2 = client.get("/courses/999999/enrolled-students?plo_id=1")
    assert resp2.status_code == 404


def test_batch_query_count_does_not_scale_per_student(client, db_session, admin_user):
    """ยืนยันว่าคำนวณแบบ batch จริง (จำนวน SQL query คงที่ ไม่ขึ้นกับจำนวนนักศึกษาใน roster) - นับจำนวน
    query ระหว่างเรียก endpoint ด้วย SQLAlchemy event, roster 5 คนต้อง query จำนวนเท่าเดิมไม่ใช่ 5 เท่า"""
    from sqlalchemy import event

    fx = _make_base_fixtures(db_session)
    for i in range(5):
        _enroll_student(
            db_session,
            curriculum_id=fx["curriculum"].id,
            offering_id=fx["offering"].id,
            student_id=f"TEST00{i}",
        )
    _add_clo_with_score(
        db_session,
        course_id=fx["course"].id,
        offering_id=fx["offering"].id,
        plo_id=fx["plo"].id,
        clo_code="CLO-A",
        admin_user_id=admin_user.id,
        student_id="TEST000",
        score_obtained=80.0,
    )
    db_session.commit()

    query_count = 0

    def _count(*args, **kwargs):
        nonlocal query_count
        query_count += 1

    engine_conn = db_session.get_bind()
    event.listen(engine_conn, "before_cursor_execute", _count)
    try:
        resp = client.get(f"/courses/{fx['course'].id}/enrolled-students?plo_id={fx['plo'].id}")
    finally:
        event.remove(engine_conn, "before_cursor_execute", _count)

    assert resp.status_code == 200
    assert len(resp.json()) == 5
    # roster query + plo_requirements query + enrollment/assessment_item/item_clo/student_score
    # batch queries รวมกันไม่กี่ตัว ไม่ใช่หลักสิบ (ซึ่งจะเกิดถ้า query ทีละคนในลูป)
    assert query_count < 10, f"expected a small constant number of batch queries, got {query_count}"
