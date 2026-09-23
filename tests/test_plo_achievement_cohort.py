"""
Tests สำหรับ GET /plo/achievement/cohort - endpoint นี้ที่หน้า "ภาพรวม PLO ทั้งหลักสูตร"
(PLODashboard.jsx) เรียกใช้ตรงๆ ครอบคลุมทั้ง happy path เดิม (สร้างข้อมูลผ่าน clo_plo_mapping
โดยตรง) และสูตรถ่วงน้ำหนักใหม่ของ Workstream 3 (PLO_x = Σ(mastery×weight)/Σ(weight) - ดู
app/routes/plo_calculation.py module docstring)

หมายเหตุ: เทสนี้เดิมสร้างข้อมูลผ่าน course_plo(responsibility_level='primary') เพราะตอนนั้น
_build_plo_requirements ยังอิงจาก course_plo อยู่ - ต่อมาเปลี่ยนมาผูก CLO กับ PLO โดยตรงผ่าน
clo_plo_mapping (ตาม มคอ.3) แล้วล่าสุด Workstream 3 เปลี่ยนสูตรรวมจาก all-or-nothing (ต้องผ่านทุก
CLO ของทุกวิชาที่ผูกกับ PLO นั้น) เป็นค่าเฉลี่ยถ่วงน้ำหนักต่อเนื่อง ไม่จัดกลุ่มตามวิชาอีกต่อไป
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
    /plo/achievement/cohort แล้วต้องได้ 200 พร้อมตัวเลขบรรลุที่ถูกต้อง (ไม่ error 500)"""
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
    db_session.add(CLOPLOMapping(clo_id=clo.id, plo_id=plo.id, weight_percent=100.00))

    item = AssessmentItem(offering_id=offering.id, name="item-1", type="quiz", total_score=100.0)
    db_session.add(item)
    db_session.flush()

    db_session.add(ItemCLO(item_id=item.id, clo_id=clo.id, weight_percent=100.00))
    # 90/100 = 90% mastery, CLO เดียว weight=100 -> PLO_x = 90.0 >= เกณฑ์ 60.0 -> บรรลุ
    db_session.add(StudentScore(item_id=item.id, student_id=student.id, score_obtained=90.0))
    db_session.commit()

    resp = client.get(f"/plo/achievement/cohort?curriculum_id={curriculum.id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_students"] == 1
    plo_summary = next(p for p in body["plo_summary"] if p["plo_id"] == plo.id)
    assert plo_summary["achieved_student_count"] == 1
    assert plo_summary["achieved_rate_percent"] == 100.0
    assert plo_summary["average_achieved_percent"] == 90.0


def test_clos_of_same_course_mapped_to_different_plos_are_evaluated_independently(
    client, db_session, admin_user
):
    """วิชาเดียวกันมี CLO 2 ตัว ผูกกับ PLO คนละข้อกัน (CLO-A -> PLO-A เท่านั้น, CLO-B -> PLO-B เท่านั้น
    ตาม มคอ.3 จริงที่ CLO แต่ละข้อไม่ได้ผูกกับ PLO เดียวกันหมด) นักศึกษาได้คะแนนสูงใน CLO-A แต่คะแนนต่ำ
    ใน CLO-B - PLO-A ต้องได้คะแนนสูง (มีแค่ CLO-A เป็นหลักฐาน ไม่เกี่ยวกับ CLO-B) PLO-B ต้องได้คะแนนต่ำ
    (มีแค่ CLO-B เป็นหลักฐาน) - regression test กันไม่ให้ CLO ของวิชาเดียวกันแต่ผูกกับ PLO อื่นถูกนับรวม
    ผิดข้อ"""
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
    db_session.add(CLOPLOMapping(clo_id=clo_a.id, plo_id=plo_a.id, weight_percent=100.00))
    db_session.add(CLOPLOMapping(clo_id=clo_b.id, plo_id=plo_b.id, weight_percent=100.00))

    item_a = AssessmentItem(offering_id=offering.id, name="item-a", type="quiz", total_score=100.0)
    item_b = AssessmentItem(offering_id=offering.id, name="item-b", type="quiz", total_score=100.0)
    db_session.add_all([item_a, item_b])
    db_session.flush()

    db_session.add(ItemCLO(item_id=item_a.id, clo_id=clo_a.id, weight_percent=100.00))
    db_session.add(ItemCLO(item_id=item_b.id, clo_id=clo_b.id, weight_percent=100.00))
    # CLO-A: 90% >= เกณฑ์ 60% / CLO-B: 30% < เกณฑ์ 60%
    db_session.add(StudentScore(item_id=item_a.id, student_id=student.id, score_obtained=90.0))
    db_session.add(StudentScore(item_id=item_b.id, student_id=student.id, score_obtained=30.0))
    db_session.commit()

    resp = client.get(f"/plo/achievement/cohort?curriculum_id={curriculum.id}")
    assert resp.status_code == 200
    body = resp.json()

    plo_a_summary = next(p for p in body["plo_summary"] if p["plo_id"] == plo_a.id)
    plo_b_summary = next(p for p in body["plo_summary"] if p["plo_id"] == plo_b.id)
    assert plo_a_summary["average_achieved_percent"] == 90.0
    assert plo_a_summary["achieved_student_count"] == 1
    assert plo_b_summary["average_achieved_percent"] == 30.0
    assert plo_b_summary["achieved_student_count"] == 0


def test_cohort_achievement_curriculum_not_found_returns_404(client, db_session):
    """ขอผลบรรลุ PLO ของ curriculum_id ที่ไม่มีอยู่จริง - ต้องได้ 404 ไม่ใช่ 200 พร้อมข้อมูลว่างเปล่า
    หรือ 500 error ถ้าเทสนี้ fail แปลว่า endpoint ไม่ได้เช็คว่าหลักสูตรมีอยู่จริงก่อนคำนวณ (อาจ error
    หรือคืนผลลัพธ์ผิดๆ แทนที่จะบอกชัดเจนว่าไม่พบหลักสูตร)"""
    resp = client.get("/plo/achievement/cohort?curriculum_id=999999")
    assert resp.status_code == 404


class TestWeightedFormula:
    """Tests เฉพาะสูตรถ่วงน้ำหนักใหม่ (Workstream 3) - PLO_x = Σ(mastery×weight)/Σ(weight) ต่อ CLO-PLO
    pair ตรงๆ ไม่จัดกลุ่มตามวิชา, ไม่บังคับผลรวมน้ำหนักต่อ PLO ต้องเท่า 100, และ CLO ที่นักศึกษาไม่มี
    mastery เลยถูกข้ามไปทั้งตัวตั้งตัวหาร ไม่นับเป็น 0"""

    def _setup_curriculum_and_student(self, db_session):
        curriculum = Curriculum(name="Test Weighted Formula", year=2569)
        db_session.add(curriculum)
        db_session.flush()

        plo = PLO(
            curriculum_id=curriculum.id, code="PLO-W", description_th="ทดสอบถ่วงน้ำหนัก", category="ความรู้"
        )
        db_session.add(plo)
        db_session.flush()

        course = Course(curriculum_id=curriculum.id, course_code="TESTW1", name_th="วิชาทดสอบ", credit=3)
        db_session.add(course)
        db_session.flush()

        offering = CourseOffering(course_id=course.id, academic_year=2569, semester=1, section="1")
        db_session.add(offering)
        db_session.flush()

        student = Student(
            id="TESTW001",
            curriculum_id=curriculum.id,
            first_name="ทดสอบ",
            last_name="ถ่วงน้ำหนัก",
            cohort_year=69,
        )
        db_session.add(student)
        db_session.add(Enrollment(student_id=student.id, offering_id=offering.id))
        db_session.flush()

        return curriculum, plo, course, offering, student

    def _add_clo(self, db_session, *, course, offering, student, code, admin_user_id, score, weight_percent):
        clo = CLO(
            course_id=course.id,
            code=code,
            description=f"ทดสอบ {code}",
            pass_threshold_percent=60.00,
            created_by=admin_user_id,
        )
        db_session.add(clo)
        db_session.flush()

        item = AssessmentItem(offering_id=offering.id, name=f"item-{code}", type="quiz", total_score=100.0)
        db_session.add(item)
        db_session.flush()
        db_session.add(ItemCLO(item_id=item.id, clo_id=clo.id, weight_percent=100.00))
        if score is not None:
            db_session.add(StudentScore(item_id=item.id, student_id=student.id, score_obtained=score))
        return clo

    def test_two_clos_different_weights_computes_correct_weighted_average(
        self, client, db_session, admin_user
    ):
        """CLO-A (mastery 100%, weight 75) + CLO-B (mastery 20%, weight 25) ผูกกับ PLO เดียวกัน ->
        PLO_x = (100×75 + 20×25) / (75+25) = (7500+500)/100 = 80.0 (ไม่ใช่ค่าเฉลี่ยธรรมดา (100+20)/2=60
        ซึ่งจะพิสูจน์ว่าน้ำหนักมีผลจริง ไม่ใช่แค่เฉลี่ยเฉยๆ)"""
        curriculum, plo, course, offering, student = self._setup_curriculum_and_student(db_session)

        clo_a = self._add_clo(
            db_session, course=course, offering=offering, student=student,
            code="CLO-A", admin_user_id=admin_user.id, score=100.0, weight_percent=75,
        )
        clo_b = self._add_clo(
            db_session, course=course, offering=offering, student=student,
            code="CLO-B", admin_user_id=admin_user.id, score=20.0, weight_percent=25,
        )
        db_session.add(CLOPLOMapping(clo_id=clo_a.id, plo_id=plo.id, weight_percent=75))
        db_session.add(CLOPLOMapping(clo_id=clo_b.id, plo_id=plo.id, weight_percent=25))
        db_session.commit()

        resp = client.get(f"/plo/achievement/cohort?curriculum_id={curriculum.id}")
        assert resp.status_code == 200
        plo_summary = next(p for p in resp.json()["plo_summary"] if p["plo_id"] == plo.id)
        assert plo_summary["average_achieved_percent"] == 80.0
        assert plo_summary["achieved_student_count"] == 1  # 80 >= เกณฑ์ 60

    def test_weight_sum_not_required_to_equal_100(self, client, db_session, admin_user):
        """CLO-A weight=100 + CLO-B weight=50 (ผลรวม=150 ไม่เท่า 100) - สูตรหารด้วยผลรวมน้ำหนักเอง จึง
        ต้องไม่ error และได้ผลลัพธ์ถูกต้องตามสัดส่วนจริง (100×100 + 40×50)/150 = (10000+2000)/150 = 80.0"""
        curriculum, plo, course, offering, student = self._setup_curriculum_and_student(db_session)

        clo_a = self._add_clo(
            db_session, course=course, offering=offering, student=student,
            code="CLO-A", admin_user_id=admin_user.id, score=100.0, weight_percent=100,
        )
        clo_b = self._add_clo(
            db_session, course=course, offering=offering, student=student,
            code="CLO-B", admin_user_id=admin_user.id, score=40.0, weight_percent=50,
        )
        db_session.add(CLOPLOMapping(clo_id=clo_a.id, plo_id=plo.id, weight_percent=100))
        db_session.add(CLOPLOMapping(clo_id=clo_b.id, plo_id=plo.id, weight_percent=50))
        db_session.commit()

        resp = client.get(f"/plo/achievement/cohort?curriculum_id={curriculum.id}")
        assert resp.status_code == 200
        plo_summary = next(p for p in resp.json()["plo_summary"] if p["plo_id"] == plo.id)
        assert plo_summary["average_achieved_percent"] == 80.0

    def test_clo_without_any_score_excluded_not_counted_as_zero(self, client, db_session, admin_user):
        """CLO-A มีคะแนน (mastery 90%) + CLO-B ไม่มีคะแนนบันทึกไว้เลย (ยังไม่ประเมิน) ทั้งคู่ผูกกับ PLO
        เดียวกัน - PLO_x ต้องคำนวณจาก CLO-A อย่างเดียว (90.0) ไม่ใช่ (90+0)/2=45 ที่จะเกิดถ้า CLO ที่ไม่มี
        คะแนนถูกนับเป็น mastery=0 ผิดๆ"""
        curriculum, plo, course, offering, student = self._setup_curriculum_and_student(db_session)

        clo_a = self._add_clo(
            db_session, course=course, offering=offering, student=student,
            code="CLO-A", admin_user_id=admin_user.id, score=90.0, weight_percent=50,
        )
        clo_b = self._add_clo(
            db_session, course=course, offering=offering, student=student,
            code="CLO-B", admin_user_id=admin_user.id, score=None, weight_percent=50,
        )
        db_session.add(CLOPLOMapping(clo_id=clo_a.id, plo_id=plo.id, weight_percent=50))
        db_session.add(CLOPLOMapping(clo_id=clo_b.id, plo_id=plo.id, weight_percent=50))
        db_session.commit()

        resp = client.get(f"/plo/achievement/cohort?curriculum_id={curriculum.id}")
        assert resp.status_code == 200
        plo_summary = next(p for p in resp.json()["plo_summary"] if p["plo_id"] == plo.id)
        assert plo_summary["average_achieved_percent"] == 90.0

    def test_no_clo_has_any_score_gives_zero_not_error(self, client, db_session, admin_user):
        """CLO ผูกกับ PLO อยู่ แต่ไม่มีใครมีคะแนนบันทึกไว้เลยสักคน (Σweight ของ CLO ที่นับได้ = 0) -
        ต้องได้ 0.0 ไม่ error (หารด้วยศูนย์)"""
        curriculum, plo, course, offering, student = self._setup_curriculum_and_student(db_session)

        clo_a = self._add_clo(
            db_session, course=course, offering=offering, student=student,
            code="CLO-A", admin_user_id=admin_user.id, score=None, weight_percent=100,
        )
        db_session.add(CLOPLOMapping(clo_id=clo_a.id, plo_id=plo.id, weight_percent=100))
        db_session.commit()

        resp = client.get(f"/plo/achievement/cohort?curriculum_id={curriculum.id}")
        assert resp.status_code == 200
        plo_summary = next(p for p in resp.json()["plo_summary"] if p["plo_id"] == plo.id)
        # TASK-plo-denominator: เดิม average_achieved_percent == 0.0 (หารด้วยนักศึกษาทั้งหมด รวมคนไม่มี
        # ข้อมูลเป็น 0 ด้วย) ตอนนี้หารด้วยนักศึกษาที่มีข้อมูล (has_data=True) เท่านั้น - นักศึกษาคนเดียวใน
        # เทสนี้ไม่มีคะแนน CLO เลยสักตัว (weight_total คำนวณได้ = 0) จึง has_data=False ทำให้
        # student_count_with_data = 0 และ average เป็น None (หารไม่ได้ ไม่ใช่ 0%) - นี่คือพฤติกรรมที่
        # ตั้งใจเปลี่ยน ไม่ใช่บั๊ก
        assert plo_summary["average_achieved_percent"] is None
        assert plo_summary["achieved_student_count"] == 0
        assert plo_summary["student_count_with_data"] == 0

    def test_achieved_threshold_boundary_60_percent(self, client, db_session, admin_user):
        """PLO_x = 60.0 พอดี (เท่ากับเกณฑ์) ต้องนับว่าบรรลุ (>=  ไม่ใช่ >)"""
        curriculum, plo, course, offering, student = self._setup_curriculum_and_student(db_session)

        clo_a = self._add_clo(
            db_session, course=course, offering=offering, student=student,
            code="CLO-A", admin_user_id=admin_user.id, score=60.0, weight_percent=100,
        )
        db_session.add(CLOPLOMapping(clo_id=clo_a.id, plo_id=plo.id, weight_percent=100))
        db_session.commit()

        resp = client.get(f"/plo/achievement/cohort?curriculum_id={curriculum.id}")
        assert resp.status_code == 200
        plo_summary = next(p for p in resp.json()["plo_summary"] if p["plo_id"] == plo.id)
        assert plo_summary["average_achieved_percent"] == 60.0
        assert plo_summary["achieved_student_count"] == 1
