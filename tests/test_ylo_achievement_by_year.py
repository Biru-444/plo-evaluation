"""
Regression test สำหรับ GET /ylo/achievement/by-year - endpoint นี้ไม่เคยมี test คลุมมาก่อนเลย
(ตรงกับที่ user แจ้งบั๊กมา: หน้า "YLO ตามชั้นปี" กดชั้นปีที่ N แล้วเห็นนักศึกษาที่ current_year_level
ยังไม่ถึง N ปนเข้ามาในตาราง/ตัวเลขสรุปด้วย)

สาเหตุที่ยืนยันแล้ว: students_query ใน get_ylo_achievement เดิมกรองแค่ curriculum_id (และ cohort_year
ถ้ามี) ไม่เคยเอา year_level ที่รับมาไปเทียบกับ Student.current_year_level เลย - เทสนี้จำลองเคสที่มี
นักศึกษาต่างชั้นปีกันในหลักสูตรเดียวกัน (ปี 1 กับปี 3) แล้วยืนยันว่า query year_level=3 ต้องไม่มี
นักศึกษาปี 1 หลุดเข้ามาทั้งในตัวเลขสรุปและใน students list
"""
from __future__ import annotations

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


def test_by_year_excludes_students_who_have_not_reached_that_year_level(
    client, db_session, admin_user
):
    curriculum = Curriculum(name="Test Curriculum YLO", year=2569)
    db_session.add(curriculum)
    db_session.flush()

    course = Course(
        curriculum_id=curriculum.id, course_code="TESTY301", name_th="วิชาทดสอบ YLO ปี 3", credit=3
    )
    db_session.add(course)
    db_session.flush()

    plo = PLO(curriculum_id=curriculum.id, code="PLO1", description_th="ทดสอบ PLO")
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
        current_year_level=1,
    )
    # นักศึกษาปี 3 - ถึงชั้นปีที่ 3 แล้ว ต้องถูกนับ
    student_year3 = Student(
        id="TESTY3",
        curriculum_id=curriculum.id,
        first_name="ปีสาม",
        last_name="ถึงแล้ว",
        cohort_year=67,
        current_year_level=3,
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


def test_by_year_1_still_includes_students_at_every_year_level(client, db_session, admin_user):
    """กดชั้นปีที่ 1 ต้องเห็นนักศึกษาทุกชั้นปี (1-4) เพราะทุกคนเรียนถึงปี 1 มาแล้วแน่นอน - กันไม่ให้
    การแก้ไขบั๊ก (เพิ่ม current_year_level >= year_level) เข้มงวดเกินไปจนตัดนักศึกษาปีสูงกว่าออกด้วย"""
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
        current_year_level=1,
    )
    student_year4 = Student(
        id="TESTA4",
        curriculum_id=curriculum.id,
        first_name="ปีสี่",
        last_name="ข",
        cohort_year=66,
        current_year_level=4,
    )
    db_session.add_all([student_year1, student_year4])
    db_session.commit()

    resp = client.get(f"/ylo/achievement/by-year?curriculum_id={curriculum.id}&year_level=1")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_students"] == 2
    student_ids = {s["student_id"] for s in body["students"]}
    assert student_ids == {student_year1.id, student_year4.id}
