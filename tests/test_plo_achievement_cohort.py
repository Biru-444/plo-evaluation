"""
Smoke test สำหรับ GET /plo/achievement/cohort - endpoint นี้ไม่เคยมี test คลุมโดยตรงมาก่อนเลย
(มีแต่ test ของ /courses/{course_id}/enrolled-students?plo_id= ที่ใช้ _build_plo_requirements ตัว
เดียวกันทางอ้อม) ทำให้ตอนที่เปลี่ยนแกนคำนวณจาก clo_plo_mapping มาเป็น course_plo (ดู
_build_plo_requirements ใน plo_calculation.py) แล้วเกิดปัญหาที่หน้า "ภาพรวม PLO ทั้งหลักสูตร" เรียก
endpoint นี้ตรงๆ ไม่มี test ไหนคลุม endpoint นี้แบบ end-to-end เลยสักตัว

หมายเหตุ: ปัญหาที่เจอจริงตอนนั้นไม่ใช่ code bug (ยืนยันแล้วว่า _build_plo_requirements ทำงานถูกต้อง
ทั้งก่อนและหลัง - เพราะมันถูกเทสผ่าน test_courses_enrolled_students_mastery.py อยู่แล้ว) แต่เป็น
uvicorn --reload worker process ค้างจากก่อน merge ยังไม่ถูก restart จริง - เทสไฟล์นี้จึงไม่ได้เขียนมา
เพื่อ "จับบั๊กที่เจอ" (เทสจะจับ process ค้างไม่ได้อยู่แล้ว) แต่เพื่อปิดช่องว่างที่ endpoint ซึ่งเพิ่งมี
ปัญหาให้เห็นจริงกลับไม่มี test คลุมเลยสักตัว กันไม่ให้เกิดปัญหาจากโค้ดจริงๆ ในอนาคตแล้วไม่มีใครจับได้
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
)


def test_cohort_achievement_end_to_end_with_course_plo(client, db_session, admin_user):
    """สร้างหลักสูตร + วิชา + course_plo(primary) + CLO ที่นักศึกษาผ่านเกณฑ์ - ยิง GET
    /plo/achievement/cohort แล้วต้องได้ 200 พร้อมตัวเลขบรรลุที่ถูกต้อง (ไม่ error 500) นี่คือ endpoint
    ที่หน้า "ภาพรวม PLO ทั้งหลักสูตร" (PLODashboard.jsx) เรียกใช้ตรงๆ"""
    curriculum = Curriculum(name="Test Curriculum", year=2569)
    db_session.add(curriculum)
    db_session.flush()

    course = Course(
        curriculum_id=curriculum.id, course_code="TEST201", name_th="วิชาทดสอบ 2", credit=3
    )
    db_session.add(course)
    db_session.flush()

    plo = PLO(curriculum_id=curriculum.id, code="PLO1", description_th="ทดสอบ PLO")
    db_session.add(plo)
    db_session.flush()

    db_session.add(CoursePLO(course_id=course.id, plo_id=plo.id, responsibility_level="primary"))

    offering = CourseOffering(course_id=course.id, academic_year=2569, semester=1, section="1")
    db_session.add(offering)
    db_session.flush()

    student = Student(
        id="TEST001",
        curriculum_id=curriculum.id,
        first_name="ทดสอบ",
        last_name="นักศึกษา",
        cohort_year=69,
        current_year_level=1,
    )
    db_session.add(student)
    db_session.add(Enrollment(student_id=student.id, offering_id=offering.id))
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
    db_session.add(StudentScore(item_id=item.id, student_id=student.id, score_obtained=90.0))
    db_session.commit()

    resp = client.get(f"/plo/achievement/cohort?curriculum_id={curriculum.id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_students"] == 1
    plo_summary = next(p for p in body["plo_summary"] if p["plo_id"] == plo.id)
    assert plo_summary["achieved_student_count"] == 1
    assert plo_summary["achieved_rate_percent"] == 100.0


def test_cohort_achievement_curriculum_not_found_returns_404(client, db_session):
    resp = client.get("/plo/achievement/cohort?curriculum_id=999999")
    assert resp.status_code == 404
