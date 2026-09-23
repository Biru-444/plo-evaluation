"""
Tests สำหรับ GET /plo/achievement/export - export รายงานภาพรวม PLO ↔ รายวิชาของหลักสูตรเดียวเป็น
Excel (7 ชีต) ครอบคลุมทั้งความถูกต้องของตัวเลข (ต้องตรงกับ GET /plo/achievement/cohort ที่ใช้
compute_cohort_plo_achievement() ตัวเดียวกันจาก plo_achievement_service.py), สิทธิ์การเข้าถึง (admin/
instructor), และความสอดคล้องของ curriculum mapping (course_plo vs clo_plo_mapping)

ใช้ fixture pattern เดียวกับ tests/test_export_clo_report.py และ tests/test_plo_achievement_cohort.py
(สร้างข้อมูลเองใน db_session ทุกเทส ไม่พึ่งข้อมูลที่มีอยู่ก่อน - rollback อัตโนมัติหลังจบเทสตาม
conftest.py)
"""
from __future__ import annotations

from io import BytesIO

import pytest
from fastapi.testclient import TestClient
from openpyxl import load_workbook

from app.auth import get_current_user
from app.database import get_db
from app.main import app
from app.models import (
    CLO,
    AssessmentItem,
    CLOPLOMapping,
    Course,
    CourseOffering,
    CoursePLO,
    Curriculum,
    Enrollment,
    ItemCLO,
    PLO,
    Student,
    StudentScore,
    StudyPlan,
    User,
)


@pytest.fixture()
def make_client(db_session):
    """เหมือน conftest.py's `client` fixture แต่รับ user ที่จะให้เป็น current_user ได้ (ไม่ hardcode
    admin_user) - ใช้ทดสอบสิทธิ์ที่ต้องสวมบทเป็น user คนอื่นที่ไม่ใช่ admin"""

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


ALL_SHEET_NAMES_NO_COHORT = [
    "คำอธิบาย", "สรุปการบรรลุ PLO", "แผนที่หลักสูตร PLO×รายวิชา", "CLO×PLO (น้ำหนัก)",
    "ย้อนรอยการคำนวณ", "เปรียบเทียบรายรุ่น", "รายบุคคล",
]
ALL_SHEET_NAMES_WITH_COHORT = [
    "คำอธิบาย", "สรุปการบรรลุ PLO", "แผนที่หลักสูตร PLO×รายวิชา", "CLO×PLO (น้ำหนัก)",
    "ย้อนรอยการคำนวณ", "รายบุคคล",
]


def _make_curriculum(db_session, name="Test Curriculum PLO Report"):
    curriculum = Curriculum(name=name, year=2569)
    db_session.add(curriculum)
    db_session.flush()
    return curriculum


def _make_course(db_session, curriculum, code="PLORPT1", category="วิชาแกน"):
    course = Course(
        curriculum_id=curriculum.id,
        course_code=code,
        name_th=f"วิชาทดสอบ {code}",
        credit=3,
        category=category,
    )
    db_session.add(course)
    db_session.flush()
    return course


def _make_offering(db_session, course, instructor=None, section="1"):
    offering = CourseOffering(
        course_id=course.id,
        instructor_id=instructor.id if instructor is not None else None,
        academic_year=2569,
        semester=1,
        section=section,
    )
    db_session.add(offering)
    db_session.flush()
    return offering


def _enroll_student(db_session, curriculum, offering, student_id, cohort_year=69):
    student = Student(
        id=student_id,
        curriculum_id=curriculum.id,
        first_name="ทดสอบ",
        last_name=student_id,
        cohort_year=cohort_year,
    )
    db_session.add(student)
    db_session.add(Enrollment(student_id=student.id, offering_id=offering.id))
    db_session.flush()
    return student


def _add_clo_plo(
    db_session, *, course, plo, offering, clo_code, admin_user_id, weight_percent, scores: dict
):
    """สร้าง CLO 1 ตัวผูกกับ PLO ที่ส่งมา + assessment_item 1 ชิ้น (เต็ม 100, weight 100% เข้า CLO) -
    scores คือ {student_id: score_obtained}"""
    clo = CLO(
        course_id=course.id,
        code=clo_code,
        description=f"ทดสอบ {clo_code}",
        pass_threshold_percent=60.00,
        created_by=admin_user_id,
    )
    db_session.add(clo)
    db_session.flush()
    db_session.add(CLOPLOMapping(clo_id=clo.id, plo_id=plo.id, weight_percent=weight_percent))

    item = AssessmentItem(offering_id=offering.id, name=f"item-{clo_code}", type="quiz", total_score=100.0)
    db_session.add(item)
    db_session.flush()
    db_session.add(ItemCLO(item_id=item.id, clo_id=clo.id, weight_percent=100.00))

    for student_id, score in scores.items():
        db_session.add(StudentScore(item_id=item.id, student_id=student_id, score_obtained=score))

    return clo


def _sheet_rows(wb, sheet_name, min_row=2):
    ws = wb[sheet_name]
    return list(ws.iter_rows(min_row=min_row, values_only=True))


def _plo_summary_row_by_code(wb, plo_code):
    for row in _sheet_rows(wb, "สรุปการบรรลุ PLO"):
        if row[0] == plo_code:
            return row
    return None


class TestExportSucceedsWithAllSheets:
    def test_no_cohort_filter_gives_seven_sheets_for_admin(self, client, db_session, admin_user):
        curriculum = _make_curriculum(db_session)
        plo = PLO(curriculum_id=curriculum.id, code="PLO1", description_th="ทดสอบ", category="ความรู้")
        db_session.add(plo)
        db_session.flush()
        course = _make_course(db_session, curriculum)
        offering = _make_offering(db_session, course)
        student = _enroll_student(db_session, curriculum, offering, "PLORPT-001")
        _add_clo_plo(
            db_session, course=course, plo=plo, offering=offering, clo_code="CLO1",
            admin_user_id=admin_user.id, weight_percent=100.0, scores={student.id: 90.0},
        )
        db_session.commit()

        resp = client.get(f"/plo/achievement/export?curriculum_id={curriculum.id}")
        assert resp.status_code == 200
        assert resp.headers["content-type"] == (
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        assert "plo_report_" in resp.headers["content-disposition"]

        wb = load_workbook(BytesIO(resp.content))
        assert wb.sheetnames == ALL_SHEET_NAMES_NO_COHORT

    def test_cohort_filter_gives_six_sheets_no_comparison_sheet(self, client, db_session, admin_user):
        curriculum = _make_curriculum(db_session)
        plo = PLO(curriculum_id=curriculum.id, code="PLO1", description_th="ทดสอบ", category="ความรู้")
        db_session.add(plo)
        db_session.flush()
        course = _make_course(db_session, curriculum)
        offering = _make_offering(db_session, course)
        student = _enroll_student(db_session, curriculum, offering, "PLORPT-002", cohort_year=69)
        _add_clo_plo(
            db_session, course=course, plo=plo, offering=offering, clo_code="CLO1",
            admin_user_id=admin_user.id, weight_percent=100.0, scores={student.id: 90.0},
        )
        db_session.commit()

        resp = client.get(f"/plo/achievement/export?curriculum_id={curriculum.id}&cohort_year=69")
        assert resp.status_code == 200
        wb = load_workbook(BytesIO(resp.content))
        assert wb.sheetnames == ALL_SHEET_NAMES_WITH_COHORT


class TestAccessControl:
    def test_instructor_also_has_personal_sheet(self, make_client, db_session, admin_user):
        """PLO ผลบรรลุเป็นข้อมูลระดับหลักสูตร (curriculum-level) ตั้งใจเปิดกว้างให้อาจารย์ทุกคนดูได้
        เท่า admin (ดู app/routes/plo_calculation.py::export_plo_report_excel) - ต่างจาก CLO export
        ระดับ offering ที่ยังจำกัดแค่เจ้าของวิชา"""
        curriculum = _make_curriculum(db_session)
        plo = PLO(curriculum_id=curriculum.id, code="PLO1", description_th="ทดสอบ", category="ความรู้")
        db_session.add(plo)
        db_session.flush()
        instructor = User(
            username="plorpt-instructor", password="x", first_name="อาจารย์", last_name="ทดสอบ",
            role="instructor",
        )
        db_session.add(instructor)
        db_session.commit()

        resp = make_client(instructor).get(f"/plo/achievement/export?curriculum_id={curriculum.id}")
        assert resp.status_code == 200
        wb = load_workbook(BytesIO(resp.content))
        assert "รายบุคคล" in wb.sheetnames

    def test_admin_has_personal_sheet(self, client, db_session):
        curriculum = _make_curriculum(db_session)
        db_session.commit()
        resp = client.get(f"/plo/achievement/export?curriculum_id={curriculum.id}")
        assert resp.status_code == 200
        wb = load_workbook(BytesIO(resp.content))
        assert "รายบุคคล" in wb.sheetnames

    def test_not_logged_in_returns_401(self, db_session):
        curriculum = _make_curriculum(db_session)
        db_session.commit()

        def _override_get_db():
            yield db_session

        app.dependency_overrides[get_db] = _override_get_db
        anonymous_client = TestClient(app)
        resp = anonymous_client.get(f"/plo/achievement/export?curriculum_id={curriculum.id}")
        assert resp.status_code == 401
        app.dependency_overrides.clear()

    def test_nonexistent_curriculum_returns_404(self, client):
        resp = client.get("/plo/achievement/export?curriculum_id=999999")
        assert resp.status_code == 404


class TestSheet2MatchesCohortEndpoint:
    def test_numbers_match_without_cohort_filter(self, client, db_session, admin_user):
        curriculum = _make_curriculum(db_session)
        plo = PLO(curriculum_id=curriculum.id, code="PLO1", description_th="ทดสอบ", category="ความรู้")
        db_session.add(plo)
        db_session.flush()
        course = _make_course(db_session, curriculum)
        offering = _make_offering(db_session, course)
        s1 = _enroll_student(db_session, curriculum, offering, "PLORPT-010")
        s2 = _enroll_student(db_session, curriculum, offering, "PLORPT-011")
        _add_clo_plo(
            db_session, course=course, plo=plo, offering=offering, clo_code="CLO1",
            admin_user_id=admin_user.id, weight_percent=100.0,
            scores={s1.id: 90.0, s2.id: 20.0},
        )
        db_session.commit()

        api_resp = client.get(f"/plo/achievement/cohort?curriculum_id={curriculum.id}")
        api_summary = next(p for p in api_resp.json()["plo_summary"] if p["plo_code"] == "PLO1")

        export_resp = client.get(f"/plo/achievement/export?curriculum_id={curriculum.id}")
        wb = load_workbook(BytesIO(export_resp.content))
        row = _plo_summary_row_by_code(wb, "PLO1")

        # TASK-plo-denominator: เพิ่มคอลัมน์ "ความครอบคลุมข้อมูล (%)" เป็นคอลัมน์ที่ 8 (index 7) ทำให้
        # คอลัมน์ที่เหลือขยับไปคนละ 1 ตำแหน่งจากเดิม (คะแนนเฉลี่ย 7->8, บรรลุ(คน) 8->9, ร้อยละที่บรรลุ 9->10)
        assert row[8] == api_summary["average_achieved_percent"]  # คะแนน PLO เฉลี่ย (%)
        assert row[9] == api_summary["achieved_student_count"]  # บรรลุ (คน)
        assert row[10] == api_summary["achieved_rate_percent"]  # ร้อยละที่บรรลุ (หารด้วยผู้มีข้อมูล)

        all_achieved_row = _sheet_rows(wb, "สรุปการบรรลุ PLO")[-2]
        assert (
            f"{api_resp.json()['all_plo_achieved_count']} คน"
            in all_achieved_row[1]
        )

    def test_numbers_match_with_cohort_filter(self, client, db_session, admin_user):
        curriculum = _make_curriculum(db_session)
        plo = PLO(curriculum_id=curriculum.id, code="PLO1", description_th="ทดสอบ", category="ความรู้")
        db_session.add(plo)
        db_session.flush()
        course = _make_course(db_session, curriculum)
        offering = _make_offering(db_session, course)
        s1 = _enroll_student(db_session, curriculum, offering, "PLORPT-020", cohort_year=69)
        s2 = _enroll_student(db_session, curriculum, offering, "PLORPT-021", cohort_year=70)
        _add_clo_plo(
            db_session, course=course, plo=plo, offering=offering, clo_code="CLO1",
            admin_user_id=admin_user.id, weight_percent=100.0,
            scores={s1.id: 90.0, s2.id: 20.0},
        )
        db_session.commit()

        api_resp = client.get(f"/plo/achievement/cohort?curriculum_id={curriculum.id}&cohort_year=69")
        api_summary = next(p for p in api_resp.json()["plo_summary"] if p["plo_code"] == "PLO1")
        assert api_resp.json()["total_students"] == 1

        export_resp = client.get(
            f"/plo/achievement/export?curriculum_id={curriculum.id}&cohort_year=69"
        )
        wb = load_workbook(BytesIO(export_resp.content))
        row = _plo_summary_row_by_code(wb, "PLO1")
        assert row[5] == 1  # นักศึกษาทั้งหมด - เฉพาะรุ่น 69
        # TASK-plo-denominator: คอลัมน์ขยับ 7->8/8->9/9->10 เหมือนเทสข้างบน (เพิ่มคอลัมน์ coverage)
        assert row[8] == api_summary["average_achieved_percent"]
        assert row[9] == api_summary["achieved_student_count"]
        assert row[10] == api_summary["achieved_rate_percent"]


class TestDenominatorAndCoverage:
    """TASK-plo-denominator: average/rate หลักหารด้วยนักศึกษาที่มีข้อมูล (ไม่ใช่ทั้งหมด) แล้ว - เทสนี้
    เดิมชื่อ TestAchievedRateWithDataColumn ทดสอบคอลัมน์เสริม "ร้อยละที่บรรลุ (จากผู้มีข้อมูล)" ที่ถูกลบ
    ทิ้งไปแล้ว (ตัวหารหลักเปลี่ยนไปใช้ค่าเดียวกันนั้นแทน) เขียนใหม่ให้ตรงพฤติกรรมปัจจุบัน"""

    def test_computed_correctly_when_some_students_have_no_data(self, client, db_session, admin_user):
        curriculum = _make_curriculum(db_session)
        plo = PLO(curriculum_id=curriculum.id, code="PLO1", description_th="ทดสอบ", category="ความรู้")
        db_session.add(plo)
        db_session.flush()
        course = _make_course(db_session, curriculum)
        offering = _make_offering(db_session, course)
        s1 = _enroll_student(db_session, curriculum, offering, "PLORPT-030")
        s2 = _enroll_student(db_session, curriculum, offering, "PLORPT-031")
        s3 = _enroll_student(db_session, curriculum, offering, "PLORPT-032")
        # s3 ไม่มีคะแนนเลย -> ไม่มีข้อมูล (student_count_with_data = 2, ไม่ใช่ 3)
        _add_clo_plo(
            db_session, course=course, plo=plo, offering=offering, clo_code="CLO1",
            admin_user_id=admin_user.id, weight_percent=100.0,
            scores={s1.id: 90.0, s2.id: 20.0},
        )
        db_session.commit()

        resp = client.get(f"/plo/achievement/export?curriculum_id={curriculum.id}")
        wb = load_workbook(BytesIO(resp.content))
        row = _plo_summary_row_by_code(wb, "PLO1")

        assert row[5] == 3  # นักศึกษาทั้งหมด
        assert row[6] == 2  # มีข้อมูล
        # ความครอบคลุมข้อมูล = 2/3*100 = 66.7 (คอลัมน์ใหม่ index 7)
        assert row[7] == pytest.approx(66.7, abs=0.1)
        # ค่าเฉลี่ยหลัก (index 8) หารด้วยผู้มีข้อมูล 2 คนเท่านั้น: (90+20)/2 = 55.0
        assert row[8] == pytest.approx(55.0, abs=0.1)
        # ร้อยละที่บรรลุหลัก (index 10) หารด้วยผู้มีข้อมูล 2 คน ไม่ใช่ทั้งหมด 3 คน: บรรลุ 1 คน (s1) จาก
        # 2 คนที่มีข้อมูล -> 50.0 (เดิมก่อน TASK-plo-denominator ค่านี้จะเป็น 33.3 เพราะหารด้วย 3 คน
        # ทั้งหมด - นี่คือการเปลี่ยนแปลงหลักของ task นี้)
        assert row[10] == pytest.approx(50.0, abs=0.1)


class TestStatusChangesWithTargetRate:
    def test_status_flips_and_unmapped_plo_shows_no_clo_linked(self, client, db_session, admin_user):
        curriculum = _make_curriculum(db_session)
        plo_mapped = PLO(curriculum_id=curriculum.id, code="PLO1", description_th="ผูกแล้ว", category="ความรู้")
        plo_unmapped = PLO(curriculum_id=curriculum.id, code="PLO2", description_th="ยังไม่ผูก", category="ทักษะ")
        db_session.add_all([plo_mapped, plo_unmapped])
        db_session.flush()
        course = _make_course(db_session, curriculum)
        offering = _make_offering(db_session, course)
        s1 = _enroll_student(db_session, curriculum, offering, "PLORPT-040")
        s2 = _enroll_student(db_session, curriculum, offering, "PLORPT-041")
        # 1 บรรลุ 1 ไม่บรรลุ -> achieved_rate_percent = 50.0
        _add_clo_plo(
            db_session, course=course, plo=plo_mapped, offering=offering, clo_code="CLO1",
            admin_user_id=admin_user.id, weight_percent=100.0,
            scores={s1.id: 90.0, s2.id: 20.0},
        )
        db_session.commit()

        low_resp = client.get(
            f"/plo/achievement/export?curriculum_id={curriculum.id}&target_rate=40"
        )
        high_resp = client.get(
            f"/plo/achievement/export?curriculum_id={curriculum.id}&target_rate=90"
        )

        low_wb = load_workbook(BytesIO(low_resp.content))
        high_wb = load_workbook(BytesIO(high_resp.content))

        assert _plo_summary_row_by_code(low_wb, "PLO1")[-1] == "บรรลุ"
        assert _plo_summary_row_by_code(high_wb, "PLO1")[-1] == "ไม่บรรลุ"
        assert _plo_summary_row_by_code(low_wb, "PLO2")[-1] == "ยังไม่มี CLO ผูก"


class TestCurriculumMapConsistencyHighlighting:
    def test_both_mismatch_cases_detected(self, client, db_session, admin_user):
        curriculum = _make_curriculum(db_session)
        plo_a = PLO(curriculum_id=curriculum.id, code="PLO-A", description_th="A", category="ความรู้")
        plo_b = PLO(curriculum_id=curriculum.id, code="PLO-B", description_th="B", category="ทักษะ")
        db_session.add_all([plo_a, plo_b])
        db_session.flush()

        # วิชา A: course_plo บอกว่ารับผิดชอบ PLO-A แต่ไม่มี CLO ผูกกับ PLO-A เลย (mismatch: ไม่มี CLO)
        course_a = _make_course(db_session, curriculum, code="MISMATCH-A")
        db_session.add(CoursePLO(course_id=course_a.id, plo_id=plo_a.id, responsibility_level="primary"))

        # วิชา B: มี CLO ผูกกับ PLO-B จริงผ่าน clo_plo_mapping แต่ไม่มีแถว course_plo เลย (mismatch:
        # ไม่มี course_plo)
        course_b = _make_course(db_session, curriculum, code="MISMATCH-B")
        offering_b = _make_offering(db_session, course_b)
        clo_b = CLO(
            course_id=course_b.id, code="CLO-B1", description="ทดสอบ",
            pass_threshold_percent=60.0, created_by=admin_user.id,
        )
        db_session.add(clo_b)
        db_session.flush()
        db_session.add(CLOPLOMapping(clo_id=clo_b.id, plo_id=plo_b.id, weight_percent=100.0))
        db_session.commit()

        resp = client.get(f"/plo/achievement/export?curriculum_id={curriculum.id}")
        wb = load_workbook(BytesIO(resp.content))
        ws = wb["แผนที่หลักสูตร PLO×รายวิชา"]

        rows_by_course = {row[0]: row for row in _sheet_rows(wb, "แผนที่หลักสูตร PLO×รายวิชา")}
        # คอลัมน์: รหัสวิชา, ชื่อวิชา, หน่วยกิต, ชั้นปี, ภาค, PLO-A, PLO-B, จำนวน PLO ต่อวิชา
        course_a_row = rows_by_course["MISMATCH-A"]
        course_b_row = rows_by_course["MISMATCH-B"]
        assert course_a_row[5] == "ไม่มี CLO"  # คอลัมน์ PLO-A ของวิชา A
        assert course_b_row[6] == "1"  # คอลัมน์ PLO-B ของวิชา B (มี 1 CLO ผูกแต่ไม่มี course_plo)

        # หาแถวจริงใน worksheet เพื่อเช็ค fill สี (openpyxl cell object ต้อง query ตรง ไม่ใช่จาก tuple)
        header = [c.value for c in ws[1]]
        col_a = header.index("PLO-A") + 1
        col_b = header.index("PLO-B") + 1
        row_a_idx = next(
            r for r in range(2, ws.max_row + 1) if ws.cell(row=r, column=1).value == "MISMATCH-A"
        )
        row_b_idx = next(
            r for r in range(2, ws.max_row + 1) if ws.cell(row=r, column=1).value == "MISMATCH-B"
        )
        assert ws.cell(row=row_a_idx, column=col_a).fill.start_color.rgb == "00FFF3CD"
        assert ws.cell(row=row_b_idx, column=col_b).fill.start_color.rgb == "00FCE4D6"


class TestWeightSheets:
    def test_weights_match_clo_plo_mapping_and_shares_sum_to_100(self, client, db_session, admin_user):
        curriculum = _make_curriculum(db_session)
        plo = PLO(curriculum_id=curriculum.id, code="PLO1", description_th="ทดสอบ", category="ความรู้")
        db_session.add(plo)
        db_session.flush()
        course = _make_course(db_session, curriculum)
        offering = _make_offering(db_session, course)
        s1 = _enroll_student(db_session, curriculum, offering, "PLORPT-050")

        # 2 CLO ผูกกับ PLO เดียวกัน คนละน้ำหนัก (60/40) - ผลรวมน้ำหนักไม่ครบ 100 ตั้งใจ (ไม่บังคับ)
        _add_clo_plo(
            db_session, course=course, plo=plo, offering=offering, clo_code="CLO-W1",
            admin_user_id=admin_user.id, weight_percent=60.0, scores={s1.id: 80.0},
        )
        _add_clo_plo(
            db_session, course=course, plo=plo, offering=offering, clo_code="CLO-W2",
            admin_user_id=admin_user.id, weight_percent=40.0, scores={s1.id: 50.0},
        )
        db_session.commit()

        resp = client.get(f"/plo/achievement/export?curriculum_id={curriculum.id}")
        wb = load_workbook(BytesIO(resp.content))

        weight_rows = {row[2]: row for row in _sheet_rows(wb, "CLO×PLO (น้ำหนัก)")}
        assert weight_rows["CLO-W1"][4] == 60.0  # คอลัมน์ PLO1
        assert weight_rows["CLO-W2"][4] == 40.0

        trace_rows = {row[2]: row for row in _sheet_rows(wb, "ย้อนรอยการคำนวณ")}
        assert trace_rows["CLO-W1"][3] == 60.0  # น้ำหนัก (%)
        assert trace_rows["CLO-W2"][3] == 40.0
        share_sum = trace_rows["CLO-W1"][4] + trace_rows["CLO-W2"][4]  # สัดส่วนน้ำหนักใน PLO นี้ (%)
        assert share_sum == pytest.approx(100.0, abs=0.1)


class TestCohortComparisonSheet:
    def test_values_match_per_cohort_endpoint_calls(self, client, db_session, admin_user):
        curriculum = _make_curriculum(db_session)
        plo = PLO(curriculum_id=curriculum.id, code="PLO1", description_th="ทดสอบ", category="ความรู้")
        db_session.add(plo)
        db_session.flush()
        course = _make_course(db_session, curriculum)
        offering = _make_offering(db_session, course)
        s1 = _enroll_student(db_session, curriculum, offering, "PLORPT-060", cohort_year=69)
        s2 = _enroll_student(db_session, curriculum, offering, "PLORPT-061", cohort_year=70)
        _add_clo_plo(
            db_session, course=course, plo=plo, offering=offering, clo_code="CLO1",
            admin_user_id=admin_user.id, weight_percent=100.0,
            scores={s1.id: 90.0, s2.id: 20.0},
        )
        db_session.commit()

        cohort69_resp = client.get(
            f"/plo/achievement/cohort?curriculum_id={curriculum.id}&cohort_year=69"
        )
        cohort70_resp = client.get(
            f"/plo/achievement/cohort?curriculum_id={curriculum.id}&cohort_year=70"
        )
        cohort69_summary = next(p for p in cohort69_resp.json()["plo_summary"] if p["plo_code"] == "PLO1")
        cohort70_summary = next(p for p in cohort70_resp.json()["plo_summary"] if p["plo_code"] == "PLO1")

        export_resp = client.get(f"/plo/achievement/export?curriculum_id={curriculum.id}")
        wb = load_workbook(BytesIO(export_resp.content))
        ws = wb["เปรียบเทียบรายรุ่น"]
        header = [c.value for c in ws[1]]

        col_69_avg = next(i for i, h in enumerate(header) if h.startswith("รุ่น 69") and "เฉลี่ย" in h) + 1
        col_69_rate = next(i for i, h in enumerate(header) if h.startswith("รุ่น 69") and "บรรลุ" in h) + 1
        col_70_avg = next(i for i, h in enumerate(header) if h.startswith("รุ่น 70") and "เฉลี่ย" in h) + 1
        col_70_rate = next(i for i, h in enumerate(header) if h.startswith("รุ่น 70") and "บรรลุ" in h) + 1

        row_idx = next(
            r for r in range(2, ws.max_row + 1) if ws.cell(row=r, column=1).value == "PLO1"
        )
        assert ws.cell(row=row_idx, column=col_69_avg).value == cohort69_summary["average_achieved_percent"]
        assert ws.cell(row=row_idx, column=col_69_rate).value == cohort69_summary["achieved_rate_percent"]
        assert ws.cell(row=row_idx, column=col_70_avg).value == cohort70_summary["average_achieved_percent"]
        assert ws.cell(row=row_idx, column=col_70_rate).value == cohort70_summary["achieved_rate_percent"]
