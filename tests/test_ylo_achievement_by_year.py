"""
Regression test สำหรับ GET /ylo/achievement/by-year - endpoint นี้ไม่เคยมี test คลุมมาก่อนเลย
(ตรงกับที่ user แจ้งบั๊กมา: หน้า "YLO ตามชั้นปี" กดชั้นปีที่ N แล้วเห็นนักศึกษาที่ยังเรียนไม่ถึงปี N
ปนเข้ามาในตาราง/ตัวเลขสรุปด้วย)

สาเหตุที่ยืนยันแล้ว (รอบแรก): students_query ใน get_ylo_achievement เดิมกรองแค่ curriculum_id (และ
cohort_year ถ้ามี) ไม่เคยเอา year_level ที่รับมาไปเทียบกับชั้นปีจริงของนักศึกษาเลย - เทสนี้จำลองเคสที่มี
นักศึกษาต่างชั้นปีกันในหลักสูตรเดียวกัน (ปี 1 กับปี 3) แล้วยืนยันว่า query year_level=3 ต้องไม่มี
นักศึกษาปี 1 หลุดเข้ามาทั้งในตัวเลขสรุปและใน students list

สาเหตุที่ยืนยันแล้ว (รอบสอง, 2026-09-23): ชั้นปีเคยเก็บเป็น Student.current_year_level column ตายตัว
ตั้งค่าครั้งเดียวตอน import แล้วไม่เคยอัปเดตอีกเลย ข้ามปีการศึกษาไปนักศึกษาก็ยังค้างชั้นปีเดิม - เปลี่ยน
มาคำนวณสดจาก cohort_year ทุกครั้ง (ดู app/services/year_level.py) เทสในไฟล์นี้ล็อก "วันนี้" ด้วย
monkeypatch (app.services.year_level._today) แทนการพึ่งวันที่จริงของเครื่องที่รันเทส - ให้ผลลัพธ์คงที่
ไม่ว่าจะรันวันไหนก็ตาม
"""
from __future__ import annotations

from datetime import date

from app.models import (
    CLO,
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
    StudyPlan,
    YLO,
    YLOPLOMapping,
)

# "วันนี้" คงที่สำหรับทุกเทสในไฟล์นี้ (กันยายน พ.ศ. 2569 - หลัง cutoff มิถุนายนของปีการศึกษา 2569) - ตรง
# กับที่คอมเมนต์เดิมในระบบ (เช่น scripts/backfill_enrollment_from_study_plan.py) สมมติไว้ว่า "วันนี้"
# ของระบบทดสอบคือปีการศึกษา 2569 ทำให้ cohort_year=66/67/69 ให้ชั้นปี 4/3/1 ตามลำดับเหมือนเดิมทุกประการ
FIXED_TODAY = date(2026, 9, 1)


def _freeze_today(monkeypatch, today=FIXED_TODAY):
    import app.services.year_level as year_level_module

    monkeypatch.setattr(year_level_module, "_today", lambda: today)


def test_by_year_excludes_students_who_have_not_reached_that_year_level(
    client, db_session, admin_user, monkeypatch
):
    """เทสหลักของไฟล์นี้ (regression test ของบั๊กที่ user แจ้งมา - ดู docstring หัวไฟล์) - สร้าง
    นักศึกษา 2 คนในหลักสูตรเดียวกัน (ปี 1 กับปี 3) แล้วขอ /ylo/achievement/by-year?year_level=3
    ถ้า fail แปลว่า endpoint กลับไปนับนักศึกษาที่ยังเรียนไม่ถึง year_level ที่ขอปนเข้ามาในตัวเลขสรุป
    (total_students/achieved_student_count/achieved_rate_percent) และ/หรือ students list อีกครั้ง"""
    _freeze_today(monkeypatch)
    curriculum = Curriculum(name="Test Curriculum YLO", year=2569)
    db_session.add(curriculum)
    db_session.flush()

    course = Course(
        curriculum_id=curriculum.id, course_code="TESTY301", name_th="วิชาทดสอบ YLO ปี 3", credit=3
    )
    db_session.add(course)
    db_session.flush()

    plo = PLO(curriculum_id=curriculum.id, code="PLO1", description_th="ทดสอบ PLO", category="ความรู้")
    db_session.add(plo)
    db_session.flush()

    db_session.add(CoursePLO(course_id=course.id, plo_id=plo.id, responsibility_level="primary"))

    ylo_year3 = YLO(curriculum_id=curriculum.id, year_level=3, description="เป้าหมายชั้นปีที่ 3")
    db_session.add(ylo_year3)
    db_session.flush()
    db_session.add(YLOPLOMapping(ylo_id=ylo_year3.id, plo_id=plo.id))

    db_session.add(
        StudyPlan(
            curriculum_id=curriculum.id,
            course_id=course.id,
            year_level=3,
            semester=1,
            cohort_year=None,
        )
    )

    offering = CourseOffering(course_id=course.id, academic_year=2569, semester=1, section="1")
    db_session.add(offering)
    db_session.flush()

    # นักศึกษาปี 1 - ยังไม่ถึงชั้นปีที่ 3 เลย ต้องไม่ถูกนับ/แสดงเมื่อขอ year_level=3
    student_year1 = Student(
        id="TESTY1",
        curriculum_id=curriculum.id,
        first_name="ปีหนึ่ง",
        last_name="ยังไม่ถึง",
        cohort_year=69,
    )
    # นักศึกษาปี 3 - ถึงชั้นปีที่ 3 แล้ว ต้องถูกนับ
    student_year3 = Student(
        id="TESTY3",
        curriculum_id=curriculum.id,
        first_name="ปีสาม",
        last_name="ถึงแล้ว",
        cohort_year=67,
    )
    db_session.add_all([student_year1, student_year3])
    db_session.add(Enrollment(student_id=student_year3.id, offering_id=offering.id))
    db_session.flush()

    clo = CLO(
        course_id=course.id,
        code="CLO1",
        description="ทดสอบ CLO1",
        pass_threshold_percent=60.00,
        created_by=admin_user.id,
    )
    db_session.add(clo)
    db_session.flush()

    item = AssessmentItem(offering_id=offering.id, name="item-1", type="quiz", total_score=100.0)
    db_session.add(item)
    db_session.flush()

    db_session.add(ItemCLO(item_id=item.id, clo_id=clo.id, weight_percent=100.00))
    # นักศึกษาปี 3 ได้ 90/100 = 90% >= เกณฑ์ 60% -> ผ่าน CLO -> ผ่านวิชาบังคับของ YLO ปี 3 -> บรรลุ YLO
    # (นักศึกษาปี 1 ไม่มีคะแนนเลยเพราะไม่ได้ลงทะเบียนวิชานี้ด้วย - แค่กัน current_year_level อย่างเดียว
    # ก็ต้องพอที่จะตัดออกจากผลลัพธ์แล้ว ไม่ต้องพึ่งว่าไม่มีคะแนน)
    db_session.add(StudentScore(item_id=item.id, student_id=student_year3.id, score_obtained=90.0))
    db_session.commit()

    resp = client.get(f"/ylo/achievement/by-year?curriculum_id={curriculum.id}&year_level=3")
    assert resp.status_code == 200
    body = resp.json()

    # นักศึกษาปี 1 ต้องไม่ถูกนับในฐานเลย ไม่ใช่แค่ไม่โผล่ใน list
    assert body["total_students"] == 1
    assert body["achieved_student_count"] == 1
    assert body["achieved_rate_percent"] == 100.0

    student_ids = {s["student_id"] for s in body["students"]}
    assert student_ids == {student_year3.id}
    assert student_year1.id not in student_ids


def test_by_year_1_still_includes_students_at_every_year_level(client, db_session, admin_user, monkeypatch):
    """กดชั้นปีที่ 1 ต้องเห็นนักศึกษาทุกชั้นปี (1-4) เพราะทุกคนเรียนถึงปี 1 มาแล้วแน่นอน - กันไม่ให้
    การแก้ไขบั๊ก (เพิ่มเงื่อนไขชั้นปี >= year_level) เข้มงวดเกินไปจนตัดนักศึกษาปีสูงกว่าออกด้วย"""
    _freeze_today(monkeypatch)
    curriculum = Curriculum(name="Test Curriculum YLO Year1", year=2569)
    db_session.add(curriculum)
    db_session.flush()

    ylo_year1 = YLO(curriculum_id=curriculum.id, year_level=1, description="เป้าหมายชั้นปีที่ 1")
    db_session.add(ylo_year1)

    student_year1 = Student(
        id="TESTA1",
        curriculum_id=curriculum.id,
        first_name="ปีหนึ่ง",
        last_name="ก",
        cohort_year=69,
    )
    student_year4 = Student(
        id="TESTA4",
        curriculum_id=curriculum.id,
        first_name="ปีสี่",
        last_name="ข",
        cohort_year=66,
    )
    db_session.add_all([student_year1, student_year4])
    db_session.commit()

    resp = client.get(f"/ylo/achievement/by-year?curriculum_id={curriculum.id}&year_level=1")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_students"] == 2
    student_ids = {s["student_id"] for s in body["students"]}
    assert student_ids == {student_year1.id, student_year4.id}


def test_by_year_includes_student_in_year_2_once_the_date_passes(client, db_session, admin_user, monkeypatch):
    """Regression test ตรงๆ ของบั๊กเดิม (Student.current_year_level เป็น column ตายตัว ตั้งครั้งเดียว
    ตอน import แล้วไม่เคยอัปเดต - นักศึกษาปี 1 จะค้างเป็นปี 1 ตลอดไปแม้ข้ามปีการศึกษาไปแล้วจริง) - สร้าง
    นักศึกษา cohort_year เดียว ไม่แตะฐานข้อมูลเลยระหว่างสองการเรียก เปลี่ยนแค่ "วันนี้" (monkeypatch
    _today) ให้ข้ามปีการศึกษาไป 1 ปี แล้วยืนยันว่านักศึกษาคนเดิมขยับจาก "ยังไม่ถึงปี 2" เป็น "ถึงปี 2
    แล้ว" เองอัตโนมัติ - ถ้า fail (นักศึกษาไม่ขยับ) แปลว่าระบบกลับไปพึ่ง column ตายตัวอีกครั้ง"""
    curriculum = Curriculum(name="Test Curriculum YLO Advance", year=2569)
    db_session.add(curriculum)
    db_session.flush()

    ylo_year2 = YLO(curriculum_id=curriculum.id, year_level=2, description="เป้าหมายชั้นปีที่ 2")
    db_session.add(ylo_year2)

    # cohort 69 - ที่ FIXED_TODAY (กันยายน 2569) ยังเป็นปี 1 (เข้าปีการศึกษา 2569 พอดี) ยังไม่ถึงปี 2
    student = Student(
        id="TESTADV1",
        curriculum_id=curriculum.id,
        first_name="ก้าวหน้า",
        last_name="ทดสอบ",
        cohort_year=69,
    )
    db_session.add(student)
    db_session.commit()

    _freeze_today(monkeypatch)
    resp_before = client.get(f"/ylo/achievement/by-year?curriculum_id={curriculum.id}&year_level=2")
    assert resp_before.status_code == 200
    body_before = resp_before.json()
    assert body_before["total_students"] == 0
    assert student.id not in {s["student_id"] for s in body_before["students"]}

    # ข้ามไป 1 ปีการศึกษา (กันยายนปีถัดไป ผ่าน cutoff มิถุนายนมาแล้ว) - ไม่แตะฐานข้อมูลเลย แค่เปลี่ยน
    # "วันนี้" - นักศึกษาคนเดิมต้องกลายเป็นปี 2 เอง
    _freeze_today(monkeypatch, today=date(FIXED_TODAY.year + 1, FIXED_TODAY.month, FIXED_TODAY.day))
    resp_after = client.get(f"/ylo/achievement/by-year?curriculum_id={curriculum.id}&year_level=2")
    assert resp_after.status_code == 200
    body_after = resp_after.json()
    assert body_after["total_students"] == 1
    assert student.id in {s["student_id"] for s in body_after["students"]}
