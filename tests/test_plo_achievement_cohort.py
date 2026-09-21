"""
Smoke test สำหรับ GET /plo/achievement/cohort - endpoint นี้ไม่เคยมี test คลุมโดยตรงมาก่อนเลย
(มีแต่ test ของ /courses/{course_id}/enrolled-students?plo_id= ที่ใช้ _build_plo_requirements ตัว
เดียวกันทางอ้อม) ทำให้ถ้า _build_plo_requirements ใน plo_calculation.py มีปัญหา หน้า "ภาพรวม PLO
ทั้งหลักสูตร" ที่เรียก endpoint นี้ตรงๆ จะไม่มี test ไหนคลุมแบบ end-to-end เลยสักตัว

หมายเหตุ: เทสนี้เดิมสร้างข้อมูลผ่าน course_plo(responsibility_level='primary') เพราะตอนนั้น
_build_plo_requirements ยังอิงจาก course_plo อยู่ - ปัจจุบันเปลี่ยนมาผูก CLO กับ PLO โดยตรงผ่าน
clo_plo_mapping แล้ว (ตาม มคอ.3 ที่ยืนยันว่า CLO แต่ละข้อผูกกับ PLO เฉพาะบางข้อ ไม่ใช่ทุก CLO ของวิชาที่
ถูก mark primary ไว้กับ PLO ข้อนั้นหมด) เทสนี้จึงอัปเดตตามให้ตรงกับที่มาของข้อมูลใหม่
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


def test_cohort_achievement_end_to_end_with_clo_plo_mapping(client, db_session, admin_user):
    """สร้างหลักสูตร + วิชา + CLO ที่ผูกกับ PLO ผ่าน clo_plo_mapping โดยตรง + คะแนนที่ผ่านเกณฑ์ - ยิง GET
    /plo/achievement/cohort แล้วต้องได้ 200 พร้อมตัวเลขบรรลุที่ถูกต้อง (ไม่ error 500) นี่คือ endpoint
    ที่หน้า "ภาพรวม PLO ทั้งหลักสูตร" (PLODashboard.jsx) เรียกใช้ตรงๆ"""
    # --- เตรียมข้อมูล: หลักสูตร -> วิชา -> PLO -> วิชาเปิดสอน -> นักศึกษาลงทะเบียน -> CLO (ผูกกับ PLO
    # ผ่าน clo_plo_mapping) -> ชิ้นงาน -> ผูกชิ้นงานกับ CLO -> คะแนนที่ทำให้ผ่านเกณฑ์ (ครบสายที่
    # _build_plo_requirements ต้องไล่ผ่านทุกขั้นเพื่อคำนวณผลบรรลุ PLO ได้)
    curriculum = Curriculum(name="Test Curriculum", year=2569)
    db_session.add(curriculum)
    db_session.flush()

    course = Course(
        curriculum_id=curriculum.id, course_code="TEST201", name_th="วิชาทดสอบ 2", credit=3
    )
    db_session.add(course)
    db_session.flush()

    plo = PLO(curriculum_id=curriculum.id, code="PLO1", description_th="ทดสอบ PLO", category="ความรู้")
    db_session.add(plo)
    db_session.flush()

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
    db_session.add(CLOPLOMapping(clo_id=clo.id, plo_id=plo.id))

    item = AssessmentItem(offering_id=offering.id, name="item-1", type="quiz", total_score=100.0)
    db_session.add(item)
    db_session.flush()

    db_session.add(ItemCLO(item_id=item.id, clo_id=clo.id, weight_percent=100.00))
    # 90/100 = 90% >= เกณฑ์ผ่าน 60% ของ CLO1 -> ผ่าน CLO -> ผ่านวิชา -> บรรลุ PLO (all-or-nothing)
    db_session.add(StudentScore(item_id=item.id, student_id=student.id, score_obtained=90.0))
    db_session.commit()

    # --- เรียก endpoint จริงแล้วตรวจผลลัพธ์
    resp = client.get(f"/plo/achievement/cohort?curriculum_id={curriculum.id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_students"] == 1
    plo_summary = next(p for p in body["plo_summary"] if p["plo_id"] == plo.id)
    assert plo_summary["achieved_student_count"] == 1
    assert plo_summary["achieved_rate_percent"] == 100.0


def test_clos_of_same_course_mapped_to_different_plos_are_evaluated_independently(
    client, db_session, admin_user
):
    """Regression test ของบั๊กหลักที่ทั้ง phase นี้แก้: วิชาเดียวกันมี CLO 2 ตัว ผูกกับ PLO คนละข้อกัน
    (CLO-A -> PLO-A เท่านั้น, CLO-B -> PLO-B เท่านั้น ตาม มคอ.3 จริงที่ CLO แต่ละข้อไม่ได้ผูกกับ PLO
    เดียวกันหมด) นักศึกษาผ่าน CLO-A แต่ไม่ผ่าน CLO-B (คะแนนต่ำกว่าเกณฑ์) - ต้องบรรลุ PLO-A (มีแค่ CLO-A
    เป็นหลักฐาน ไม่เกี่ยวกับ CLO-B) แต่ไม่บรรลุ PLO-B (มีแค่ CLO-B เป็นหลักฐาน และไม่ผ่าน) ถ้าระบบยังใช้
    ตรรกะเดิม (course_plo primary = ทุก CLO ของวิชานับเป็นหลักฐานของทุก PLO ที่วิชานั้น primary) ผลจะผิด
    เป็น PLO-A ไม่บรรลุไปด้วย เพราะจะเอา CLO-B (ไม่ผ่าน) มานับรวมด้วยทั้งที่ไม่เกี่ยวกับ PLO-A เลย"""
    curriculum = Curriculum(name="Test Curriculum Isolation", year=2569)
    db_session.add(curriculum)
    db_session.flush()

    course = Course(
        curriculum_id=curriculum.id, course_code="TEST301", name_th="วิชาทดสอบ 3", credit=3
    )
    db_session.add(course)
    db_session.flush()

    plo_a = PLO(curriculum_id=curriculum.id, code="PLO-A", description_th="ทดสอบ PLO A", category="ความรู้")
    plo_b = PLO(curriculum_id=curriculum.id, code="PLO-B", description_th="ทดสอบ PLO B", category="ทักษะ")
    db_session.add_all([plo_a, plo_b])
    db_session.flush()

    offering = CourseOffering(course_id=course.id, academic_year=2569, semester=1, section="1")
    db_session.add(offering)
    db_session.flush()

    student = Student(
        id="TEST002",
        curriculum_id=curriculum.id,
        first_name="ทดสอบ",
        last_name="แยก PLO",
        cohort_year=69,
        current_year_level=1,
    )
    db_session.add(student)
    db_session.add(Enrollment(student_id=student.id, offering_id=offering.id))
    db_session.flush()

    clo_a = CLO(
        course_id=course.id,
        code="CLO-A",
        description="ทดสอบ CLO-A (ผูกกับ PLO-A เท่านั้น)",
        pass_threshold_percent=60.00,
        created_by=admin_user.id,
    )
    clo_b = CLO(
        course_id=course.id,
        code="CLO-B",
        description="ทดสอบ CLO-B (ผูกกับ PLO-B เท่านั้น)",
        pass_threshold_percent=60.00,
        created_by=admin_user.id,
    )
    db_session.add_all([clo_a, clo_b])
    db_session.flush()
    db_session.add(CLOPLOMapping(clo_id=clo_a.id, plo_id=plo_a.id))
    db_session.add(CLOPLOMapping(clo_id=clo_b.id, plo_id=plo_b.id))

    item_a = AssessmentItem(offering_id=offering.id, name="item-a", type="quiz", total_score=100.0)
    item_b = AssessmentItem(offering_id=offering.id, name="item-b", type="quiz", total_score=100.0)
    db_session.add_all([item_a, item_b])
    db_session.flush()

    db_session.add(ItemCLO(item_id=item_a.id, clo_id=clo_a.id, weight_percent=100.00))
    db_session.add(ItemCLO(item_id=item_b.id, clo_id=clo_b.id, weight_percent=100.00))
    # CLO-A: 90% >= เกณฑ์ 60% -> ผ่าน / CLO-B: 30% < เกณฑ์ 60% -> ไม่ผ่าน
    db_session.add(StudentScore(item_id=item_a.id, student_id=student.id, score_obtained=90.0))
    db_session.add(StudentScore(item_id=item_b.id, student_id=student.id, score_obtained=30.0))
    db_session.commit()

    resp = client.get(f"/plo/achievement/cohort?curriculum_id={curriculum.id}")
    assert resp.status_code == 200
    body = resp.json()

    plo_a_summary = next(p for p in body["plo_summary"] if p["plo_id"] == plo_a.id)
    plo_b_summary = next(p for p in body["plo_summary"] if p["plo_id"] == plo_b.id)
    assert plo_a_summary["achieved_student_count"] == 1
    assert plo_b_summary["achieved_student_count"] == 0


def test_cohort_achievement_curriculum_not_found_returns_404(client, db_session):
    """ขอผลบรรลุ PLO ของ curriculum_id ที่ไม่มีอยู่จริง - ต้องได้ 404 ไม่ใช่ 200 พร้อมข้อมูลว่างเปล่า
    หรือ 500 error ถ้าเทสนี้ fail แปลว่า endpoint ไม่ได้เช็คว่าหลักสูตรมีอยู่จริงก่อนคำนวณ (อาจ error
    หรือคืนผลลัพธ์ผิดๆ แทนที่จะบอกชัดเจนว่าไม่พบหลักสูตร)"""
    resp = client.get("/plo/achievement/cohort?curriculum_id=999999")
    assert resp.status_code == 404
