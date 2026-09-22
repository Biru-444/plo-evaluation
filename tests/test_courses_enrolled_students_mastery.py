"""
Tests สำหรับ GET /courses/{course_id}/enrolled-students และ plo_id (optional) query param ใหม่ -
ครอบคลุมทั้งพฤติกรรมเดิม (ไม่ส่ง plo_id ต้องเหมือนเดิมทุกประการ ไม่กระทบ caller เดิม) และพฤติกรรมใหม่
(plo_achieved: bool | None - ผ่าน/ไม่ผ่านวิชานี้สำหรับ PLO ข้อนี้ แบบ all-or-nothing ต่อ CLO เดียวกับ
_student_passed_course_for_plo ใน plo_calculation.py ไม่ใช่ % เฉลี่ยแบบเดิม) รวมถึง edge case คะแนน
ไม่ครบ/ไม่มีเลย

ผูกกับ PLO เป็นรายตัวต่อ CLO ผ่านตาราง clo_plo_mapping โดยตรง (ไม่ใช่ระดับวิชาแบบ course_plo อีกต่อไป -
ดู _build_plo_requirements ใน plo_calculation.py) - CLO ตัวไหนไม่ได้ผูกกับ PLO ข้อนี้ไว้ใน
clo_plo_mapping จะไม่ถูกนับเข้าการคำนวณเลย แม้จะอยู่ในวิชาเดียวกับ CLO ที่ผูกไว้ก็ตาม (นี่คือเหตุผลที่
เปลี่ยนมาใช้ clo_plo_mapping แทน course_plo - วิชาหนึ่งอาจมี CLO ที่ผูกกับ PLO คนละข้อกัน)

plo_achieved เป็น null ("ยังไม่มีข้อมูลให้ประเมิน") ใน 2 กรณี: (1) วิชานี้ไม่มี CLO ตัวไหนผูกกับ PLO
ข้อนี้ผ่าน clo_plo_mapping เลย (ไม่มี CLO เลย หรือมี CLO แต่ไม่ได้ผูกกับ PLO นี้) หรือ (2) มี CLO ผูกอยู่
แต่นักศึกษายังไม่มี record คะแนนบันทึกไว้เลยสักรายการสำหรับ CLO ที่ผูกไว้เหล่านั้น (ต่างจากได้คะแนน 0
จริงซึ่งนับเป็นข้อมูลแล้ว) - False เกิดเฉพาะเมื่อมี record คะแนนอยู่แล้วอย่างน้อย 1 รายการในกลุ่ม CLO ที่
ผูกกับ PLO นี้ แล้วคำนวณตามเกณฑ์ผ่านของแต่ละ CLO ออกมาว่าไม่ถึง (รวมถึง CLO อื่นในกลุ่มที่ยังไม่มี record
เลยก็ยังนับเป็นไม่ผ่านตาม all-or-nothing ปกติ ตราบใดที่มีอย่างน้อย 1 CLO ในกลุ่มที่มี record แล้ว)

ทุกเทสสร้างข้อมูลของตัวเองใน db_session (rollback อัตโนมัติหลังจบเทสตาม conftest.py) ไม่พึ่งข้อมูลที่มี
อยู่ก่อนในฐานข้อมูลทดสอบเลย เพื่อไม่ให้เทสตัวหนึ่งกระทบอีกตัว
"""
from __future__ import annotations

from app.models import (
    CLO,
    CLOPLOMapping,
    Course,
    CourseOffering,
    Curriculum,
    Enrollment,
    AssessmentItem,
    ItemCLO,
    PLO,
    Student,
    StudentScore,
)


def _make_base_fixtures(db_session):
    """สร้าง curriculum + course + PLO + course_offering ตัวตั้งต้นที่ใช้ร่วมกันทุกเทสในไฟล์นี้ - คืน
    dict ของ object ที่สร้างไว้ให้ประกอบต่อ (การผูก CLO กับ PLO ทำทีละตัวผ่าน _add_clo_with_score
    ด้านล่าง ไม่ได้ทำที่ระดับวิชาแบบนี้อีกต่อไป)"""
    curriculum = Curriculum(name="Test Curriculum", year=2569)
    db_session.add(curriculum)
    db_session.flush()

    course = Course(
        curriculum_id=curriculum.id, course_code="TEST101", name_th="วิชาทดสอบ", credit=3
    )
    db_session.add(course)
    db_session.flush()

    plo = PLO(curriculum_id=curriculum.id, code="PLO1", description_th="ทดสอบ PLO", category="ความรู้")
    db_session.add(plo)
    db_session.flush()

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
    clo_code: str,
    admin_user_id: int,
    student_id: str | None,
    score_obtained: float | None,
    total_score: float = 100.0,
    plo_id: int | None = None,
) -> CLO:
    """สร้าง CLO 1 ตัวของวิชานี้ พร้อม assessment_item+item_clo 1 ชุด (pass_threshold_percent 60.00) -
    ผูก CLO ตัวนี้กับ PLO ที่ระบุผ่าน clo_plo_mapping โดยตรงถ้าส่ง plo_id มา (ไม่ส่ง/None = ไม่ผูก จำลอง
    "มี CLO อยู่แต่ไม่ได้ผูกกับ PLO นี้") ถ้า student_id + score_obtained ไม่ใช่ None จะกรอกคะแนนให้
    นักศึกษาคนนั้นด้วย (ไม่กรอก = จำลอง "ยังไม่มีคะแนนเลย")"""
    clo = CLO(
        course_id=course_id,
        code=clo_code,
        description=f"ทดสอบ {clo_code}",
        pass_threshold_percent=60.00,
        created_by=admin_user_id,
    )
    db_session.add(clo)
    db_session.flush()

    if plo_id is not None:
        # weight_percent ไม่มีผลต่อ endpoint นี้เลย (courses.py::get_course_enrolled_students ยังเป็น
        # all-or-nothing ต่อวิชาเหมือนเดิม ไม่ได้เปลี่ยนตาม Workstream 3 - ดู plo_calculation.py module
        # docstring) ใส่ค่าคงที่ไปเพื่อผ่าน NOT NULL เฉยๆ
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


def test_without_plo_id_achieved_is_always_null(client, db_session):
    """ไม่ส่ง plo_id เลย - ต้องเหมือนพฤติกรรมเดิมทุกประการ (plo_achieved เป็น null ทุกคน)"""
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
    assert body[0]["plo_achieved"] is None


def test_all_clos_passed_returns_achieved_true(client, db_session, admin_user):
    """คะแนนผ่านเกณฑ์ทุก CLO ของวิชานี้ (2 CLO, 90% กับ 70%, เกณฑ์ผ่าน 60%) -> plo_achieved True"""
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
        clo_code="CLO-A",
        admin_user_id=admin_user.id,
        student_id="TEST001",
        score_obtained=90.0,
        plo_id=fx["plo"].id,
    )
    _add_clo_with_score(
        db_session,
        course_id=fx["course"].id,
        offering_id=fx["offering"].id,
        clo_code="CLO-B",
        admin_user_id=admin_user.id,
        student_id="TEST001",
        score_obtained=70.0,
        plo_id=fx["plo"].id,
    )
    db_session.commit()

    resp = client.get(f"/courses/{fx['course'].id}/enrolled-students?plo_id={fx['plo'].id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body[0]["plo_achieved"] is True


def test_one_clo_without_score_makes_achieved_false(client, db_session, admin_user):
    """มีคะแนนบันทึกแล้วอย่างน้อย 1 ใน 2 CLO ของวิชานี้ (CLO-A ได้ 60% ผ่านเกณฑ์ กับ CLO-B ยังไม่มี
    record คะแนนเลย) -> plo_achieved False ไม่ใช่ None (มี record คะแนนอยู่แล้วอย่างน้อย 1 รายการในกลุ่ม
    จึงคำนวณได้ - all-or-nothing ต้องผ่านทุก CLO ของวิชานี้ CLO-B ที่ยังไม่มี record ถือว่าไม่ผ่านเกณฑ์
    ทำให้ทั้งกลุ่มไม่ผ่าน)"""
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
        clo_code="CLO-A",
        admin_user_id=admin_user.id,
        student_id="TEST001",
        score_obtained=60.0,
        plo_id=fx["plo"].id,
    )
    _add_clo_with_score(
        db_session,
        course_id=fx["course"].id,
        offering_id=fx["offering"].id,
        clo_code="CLO-B",
        admin_user_id=admin_user.id,
        student_id=None,
        score_obtained=None,
        plo_id=fx["plo"].id,
    )
    db_session.commit()

    resp = client.get(f"/courses/{fx['course'].id}/enrolled-students?plo_id={fx['plo'].id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body[0]["plo_achieved"] is False


def test_no_recorded_score_at_all_is_null_not_false(client, db_session, admin_user):
    """วิชานี้มี CLO อยู่ แต่นักศึกษาคนนี้ยังไม่มี record คะแนนบันทึกไว้เลยสักรายการ (อาจารย์ยังไม่กรอก
    คะแนน - ไม่ใช่สอบตกจริง) -> plo_achieved ต้องเป็น None ("ยังไม่มีข้อมูลให้ประเมิน") ไม่ใช่ False
    (False สงวนไว้เฉพาะกรณีมี record คะแนนแล้วแต่ไม่ถึงเกณฑ์ - ดู test_recorded_score_below_threshold_
    returns_false ที่ใช้ CLO เดี่ยวเหมือนกันแต่มี record คะแนนจริงเทียบกัน)"""
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
        clo_code="CLO-A",
        admin_user_id=admin_user.id,
        student_id=None,
        score_obtained=None,
        plo_id=fx["plo"].id,
    )
    db_session.commit()

    resp = client.get(f"/courses/{fx['course'].id}/enrolled-students?plo_id={fx['plo'].id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body[0]["plo_achieved"] is None


def test_recorded_score_below_threshold_returns_false(client, db_session, admin_user):
    """มี record คะแนนบันทึกไว้จริง (ไม่ใช่ไม่มีข้อมูล) แต่ได้ 40% ซึ่งต่ำกว่าเกณฑ์ผ่าน 60% ของ CLO นี้ ->
    plo_achieved ต้องเป็น False ไม่ใช่ None (คนละเคสกับ test_no_recorded_score_at_all_is_null_not_false
    ที่ใช้ CLO เดี่ยวเหมือนกันแต่ไม่มี record คะแนนเลย ต้องแยกผลลัพธ์กันชัดเจน)"""
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
        clo_code="CLO-A",
        admin_user_id=admin_user.id,
        student_id="TEST001",
        score_obtained=40.0,
        plo_id=fx["plo"].id,
    )
    db_session.commit()

    resp = client.get(f"/courses/{fx['course'].id}/enrolled-students?plo_id={fx['plo'].id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body[0]["plo_achieved"] is False


def test_recorded_score_of_zero_is_data_not_missing(client, db_session, admin_user):
    """record คะแนนที่บันทึกไว้เป็น 0 จริง (นักศึกษาสอบได้ 0 คะแนน) ต้องนับเป็น "มีข้อมูลแล้ว" (record
    มีอยู่จริง แค่ค่าเป็น 0) ไม่ใช่ "ไม่มีข้อมูล" - ผลลัพธ์ต้องเป็น False (ไม่ถึงเกณฑ์ผ่าน) ไม่ใช่ None
    (ยืนยันว่า _clo_mastery_for_students_batch แยก "ไม่มี StudentScore row" ออกจาก "มี row ค่า 0" ถูกต้อง)"""
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
        clo_code="CLO-A",
        admin_user_id=admin_user.id,
        student_id="TEST001",
        score_obtained=0.0,
        plo_id=fx["plo"].id,
    )
    db_session.commit()

    resp = client.get(f"/courses/{fx['course'].id}/enrolled-students?plo_id={fx['plo'].id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body[0]["plo_achieved"] is False


def test_course_with_zero_clo_returns_null_no_error(client, db_session):
    """วิชานี้ยังไม่มี CLO เลยสักตัว - ต้อง null ทุกคน ไม่ error (ไม่มี CLO ให้ผูกกับ PLO นี้ผ่าน
    clo_plo_mapping ได้เลย จึงไม่มีอะไรให้คำนวณ)"""
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
    assert body[0]["plo_achieved"] is None


def test_clo_not_mapped_to_this_plo_excluded_same_as_null(client, db_session, admin_user):
    """วิชานี้มี CLO อยู่จริง และนักศึกษาผ่านเกณฑ์คะแนนสูงมาก (95%) แต่ CLO ตัวนี้ไม่ได้ผูกกับ PLO ข้อนี้
    เลยผ่าน clo_plo_mapping (plo_id=None ใน _add_clo_with_score) - ต้องนับเหมือนไม่มีข้อมูล (null) ไม่ใช่
    True แม้คะแนนจะสูงก็ตาม เพราะ CLO นี้ไม่ใช่หลักฐานของ PLO ข้อนี้ นี่คือ regression test ของบั๊กที่
    ระบบเดิม (course_plo responsibility_level='primary') เคยพลาด - เคยถือว่า CLO ทุกตัวของวิชาที่ primary
    กับ PLO ข้อไหนก็นับเป็นหลักฐานของ PLO ข้อนั้นหมด ทั้งที่ มคอ.3 จริงผูก CLO กับ PLO เป็นรายข้อ"""
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
        clo_code="CLO-A",
        admin_user_id=admin_user.id,
        student_id="TEST001",
        score_obtained=95.0,
        plo_id=None,
    )
    db_session.commit()

    resp = client.get(f"/courses/{fx['course'].id}/enrolled-students?plo_id={fx['plo'].id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body[0]["plo_achieved"] is None


def test_invalid_plo_id_returns_404(client, db_session):
    """ส่ง plo_id ที่ไม่มีอยู่จริงมาเป็น query param - ต้อง 404 ทันที (ไม่ใช่ 200 พร้อม
    plo_achieved เป็น null ทุกคนอย่างเงียบๆ) เพื่อให้ frontend รู้ชัดว่าเรียกผิดพลาด ไม่ใช่วิชานี้
    ไม่มีข้อมูลให้ประเมินจริง"""
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


def test_offering_id_is_included_in_response(client, db_session):
    """response ต้องมี offering_id ของ course_offering ที่นักศึกษาลงทะเบียนอยู่ (ใช้ต่อยอดเรียก
    GET /clo-achievement?offering_id=... จากฝั่ง frontend)"""
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
    assert body[0]["offering_id"] == fx["offering"].id


def test_offering_id_picks_latest_enrollment_when_multiple_offerings(client, db_session):
    """ถ้านักศึกษาคนเดียวลงทะเบียนวิชานี้มากกว่า 1 course_offering (เช่น ลงเรียนซ้ำคนละเทอม) ต้อง
    ได้ offering_id ของ enrollment ล่าสุด (Enrollment.id มากสุด) มา ไม่ error/ไม่สุ่มเลือก - จำลองด้วย
    การสร้าง offering ที่สองแล้ว enroll เข้า offering แรกก่อน (Enrollment.id น้อยกว่า) แล้วค่อย enroll
    เข้า offering ที่สอง (Enrollment.id มากกว่า)"""
    fx = _make_base_fixtures(db_session)
    second_offering = CourseOffering(
        course_id=fx["course"].id, academic_year=2570, semester=1, section="1"
    )
    db_session.add(second_offering)
    db_session.flush()

    student = Student(
        id="TEST001",
        curriculum_id=fx["curriculum"].id,
        first_name="ทดสอบ",
        last_name="ลงซ้ำ",
        cohort_year=69,
        current_year_level=1,
    )
    db_session.add(student)
    db_session.add(Enrollment(student_id=student.id, offering_id=fx["offering"].id))
    db_session.flush()
    db_session.add(Enrollment(student_id=student.id, offering_id=second_offering.id))
    db_session.flush()
    db_session.commit()

    resp = client.get(f"/courses/{fx['course'].id}/enrolled-students")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["offering_id"] == second_offering.id


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
        clo_code="CLO-A",
        admin_user_id=admin_user.id,
        student_id="TEST000",
        score_obtained=80.0,
        plo_id=fx["plo"].id,
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
