"""
Tests สำหรับ GET /export/course/{course_id} และ GET /export/student/{student_id} (app/routes/export.py)
— เปิดไฟล์ .xlsx ที่ได้กลับมาด้วย openpyxl แล้วตรวจชื่อชีท + ค่าในเซลล์จริง ว่าผ่าน/ไม่ผ่าน CLO และ
ผลบรรลุ PLO ตรงกับกฎเดียวกับหน้าเว็บ (เกณฑ์ผ่าน CLO 60%, เกณฑ์บรรลุ PLO 60%) และเคารพนโยบายสิทธิ์:
อาจารย์เห็นผล CLO เฉพาะกลุ่มเรียนที่ตัวเองสอน

ทุกเทสสร้างข้อมูลของตัวเองใน db_session (rollback อัตโนมัติหลังจบเทสตาม conftest.py)
"""
from __future__ import annotations

import io

import pytest
from fastapi.testclient import TestClient
from openpyxl import load_workbook

from app.auth import get_current_user
from app.database import get_db
from app.main import app
from app.models import (
    AssessmentItem,
    CLO,
    CLOPLOMapping,
    Course,
    CourseOffering,
    Curriculum,
    Enrollment,
    ItemCLO,
    PLO,
    Student,
    StudentScore,
    User,
)


@pytest.fixture()
def make_client(db_session):
    def _make(user: User) -> TestClient:
        def _override_get_db():
            yield db_session

        app.dependency_overrides[get_db] = _override_get_db
        app.dependency_overrides[get_current_user] = lambda: user
        return TestClient(app)

    yield _make
    app.dependency_overrides.clear()


def _sheet_values(ws) -> list[list[object]]:
    return [list(row) for row in ws.iter_rows(values_only=True)]


def _find_row(rows: list[list[object]], first_cell: object) -> list[object]:
    return next(row for row in rows if row and row[0] == first_cell)


def _find_row_containing(rows: list[list[object]], value: object) -> list[object]:
    return next(row for row in rows if value in row)


def _all_cells(rows: list[list[object]]) -> list[object]:
    return [cell for row in rows for cell in row]


def _make_fixtures(db_session, admin_user_id: int):
    """1 หลักสูตร, 1 วิชา (2 CLO ผูกกับ PLO1 ทั้งคู่), 1 กลุ่มเรียนของอาจารย์ "สมชาย", นักศึกษา 2 คน:
    - EXP001 ได้ 90% ทั้ง 2 CLO -> ผ่านทุก CLO -> PLO1 = 90% บรรลุ
    - EXP002 ได้ 40% ใน CLO-A, ไม่มีคะแนน CLO-B -> ไม่ผ่าน / ไม่มีข้อมูล -> PLO1 = 40% ยังไม่บรรลุ
    PLO2 ไม่มี CLO ผูกอยู่เลย -> ทุกคน "ยังไม่มีข้อมูล"
    มีอาจารย์ "อื่น" อีกคนที่ไม่ได้สอนวิชานี้ ไว้ทดสอบสิทธิ์"""
    curriculum = Curriculum(name="หลักสูตรทดสอบ Export", year=2569)
    db_session.add(curriculum)
    db_session.flush()

    course = Course(
        curriculum_id=curriculum.id, course_code="EXP101", name_th="วิชาทดสอบส่งออก", credit=3
    )
    plo1 = PLO(curriculum_id=curriculum.id, code="PLO1", description_th="PLO หนึ่ง", category="ความรู้")
    plo2 = PLO(curriculum_id=curriculum.id, code="PLO2", description_th="PLO สอง", category="ทักษะ")
    owner = User(
        username="exp-owner", password="unused", first_name="สมชาย", last_name="ใจดี", role="instructor"
    )
    other = User(
        username="exp-other", password="unused", first_name="อื่น", last_name="ไม่เกี่ยว", role="instructor"
    )
    db_session.add_all([course, plo1, plo2, owner, other])
    db_session.flush()

    offering = CourseOffering(
        course_id=course.id, instructor_id=owner.id, academic_year=2569, semester=1, section="1"
    )
    db_session.add(offering)
    db_session.flush()

    for sid in ("EXP001", "EXP002"):
        db_session.add(
            Student(id=sid, curriculum_id=curriculum.id, first_name="ทดสอบ", last_name=sid, cohort_year=69)
        )
    db_session.flush()
    for sid in ("EXP001", "EXP002"):
        db_session.add(Enrollment(student_id=sid, offering_id=offering.id, final_grade="A"))

    scores = {"CLO-A": {"EXP001": 90, "EXP002": 40}, "CLO-B": {"EXP001": 90}}
    for clo_code, score_by_student in scores.items():
        clo = CLO(
            course_id=course.id,
            code=clo_code,
            description=f"คำอธิบาย {clo_code}",
            pass_threshold_percent=60.00,
            created_by=admin_user_id,
        )
        db_session.add(clo)
        db_session.flush()
        db_session.add(CLOPLOMapping(clo_id=clo.id, plo_id=plo1.id, weight_percent=50.00))
        item = AssessmentItem(offering_id=offering.id, name=f"item-{clo_code}", type="quiz", total_score=100)
        db_session.add(item)
        db_session.flush()
        db_session.add(ItemCLO(item_id=item.id, clo_id=clo.id, weight_percent=100.00))
        for sid, score in score_by_student.items():
            db_session.add(StudentScore(item_id=item.id, student_id=sid, score_obtained=score))

    db_session.commit()
    return {"course": course, "offering": offering, "owner": owner, "other": other}


def test_course_export_has_course_info_and_clo_results(client, db_session, admin_user):
    fx = _make_fixtures(db_session, admin_user.id)

    resp = client.get(f"/export/course/{fx['course'].id}")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith(
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    assert 'filename="course_EXP101.xlsx"' in resp.headers["content-disposition"]

    wb = load_workbook(io.BytesIO(resp.content))
    assert wb.sheetnames == ["ข้อมูลรายวิชา", "ผล CLO นักศึกษา"]

    info = _sheet_values(wb["ข้อมูลรายวิชา"])
    assert _find_row(info, "รหัสวิชา")[1] == "EXP101"
    assert _find_row(info, "ชื่อวิชา (ไทย)")[1] == "วิชาทดสอบส่งออก"
    assert _find_row(info, "อาจารย์ผู้สอน")[1] == "สมชาย ใจดี"
    assert _find_row(info, "CLO-A")[3] == "PLO1"
    # PLO ของรายวิชามีแค่ PLO1 (PLO2 ไม่มี CLO ของวิชานี้ผูกอยู่)
    assert _find_row(info, "PLO1")[3] == "CLO-A, CLO-B"
    assert not any(row and row[0] == "PLO2" for row in info)
    # ไม่มี Sec ในไฟล์ (ผู้ใช้ขอให้เอาออก)
    assert not any("Sec" in str(cell) for cell in _all_cells(info))

    results = _sheet_values(wb["ผล CLO นักศึกษา"])
    header = _find_row_containing(results, "รหัสนักศึกษา")
    clo_a, clo_b, summary = header.index("CLO-A"), header.index("CLO-B"), header.index("ผ่าน CLO")
    row1 = _find_row_containing(results, "EXP001")
    row2 = _find_row_containing(results, "EXP002")
    assert (row1[clo_a], row1[clo_b], row1[summary]) == ("ผ่าน", "ผ่าน", "2/2")
    assert (row2[clo_a], row2[clo_b], row2[summary]) == ("ไม่ผ่าน", "ไม่มีข้อมูล", "0/2")
    assert row1[header.index("ภาคเรียนที่เรียน")] == "2569/1"
    # ไม่มีคะแนนชิ้นงานในไฟล์ (ผู้ใช้ขอแค่ผล ผ่าน/ไม่ผ่าน)
    assert "item-CLO-A" not in _all_cells(results)


def test_course_export_retake_is_one_row_per_enrollment(client, db_session, admin_user):
    """ลงเรียนวิชาเดิมซ้ำคนละภาคเรียน -> แยกแถวตามครั้งที่เรียน ผล CLO คิดจากคะแนนของครั้งนั้นๆ"""
    fx = _make_fixtures(db_session, admin_user.id)
    retake = CourseOffering(
        course_id=fx["course"].id, instructor_id=fx["owner"].id, academic_year=2570, semester=1, section="1"
    )
    db_session.add(retake)
    db_session.flush()
    db_session.add(Enrollment(student_id="EXP002", offering_id=retake.id))
    db_session.commit()

    wb = load_workbook(io.BytesIO(client.get(f"/export/course/{fx['course'].id}").content))
    results = _sheet_values(wb["ผล CLO นักศึกษา"])
    exp002_rows = [row for row in results if "EXP002" in row]
    assert [row[4] for row in exp002_rows] == ["2569/1", "2570/1"]
    # ครั้งที่ 2 ยังไม่มีคะแนนเลย -> ไม่มีข้อมูลทุก CLO (ไม่ปนคะแนนของครั้งแรก)
    assert exp002_rows[1][5:7] == ["ไม่มีข้อมูล", "ไม่มีข้อมูล"]


def test_course_export_owner_instructor_sees_clo_results(make_client, db_session, admin_user):
    fx = _make_fixtures(db_session, admin_user.id)
    resp = make_client(fx["owner"]).get(f"/export/course/{fx['course'].id}")
    assert resp.status_code == 200
    results = _sheet_values(load_workbook(io.BytesIO(resp.content))["ผล CLO นักศึกษา"])
    assert "EXP001" in _all_cells(results)


def test_course_export_non_owner_instructor_sees_no_student_results(make_client, db_session, admin_user):
    """อาจารย์ที่ไม่ได้สอนกลุ่มเรียนไหนของวิชานี้ ได้ไฟล์ (ข้อมูลรายวิชาไม่ใช่ข้อมูลคะแนน) แต่ไม่เห็นผล
    CLO ของนักศึกษาคนไหนเลย - นโยบายเดียวกับ GET /clo-achievement"""
    fx = _make_fixtures(db_session, admin_user.id)
    resp = make_client(fx["other"]).get(f"/export/course/{fx['course'].id}")
    assert resp.status_code == 200
    wb = load_workbook(io.BytesIO(resp.content))
    info = _sheet_values(wb["ข้อมูลรายวิชา"])
    assert _find_row(info, "รหัสวิชา")[1] == "EXP101"
    results = _all_cells(_sheet_values(wb["ผล CLO นักศึกษา"]))
    assert "EXP001" not in results and "EXP002" not in results
    assert "* แสดงผล CLO เฉพาะกลุ่มเรียนที่คุณเป็นผู้สอน" in results


def test_student_export_has_profile_plo_and_courses(client, db_session, admin_user):
    _make_fixtures(db_session, admin_user.id)

    resp = client.get("/export/student/EXP001")
    assert resp.status_code == 200
    assert 'filename="student_EXP001.xlsx"' in resp.headers["content-disposition"]

    wb = load_workbook(io.BytesIO(resp.content))
    assert wb.sheetnames == ["ข้อมูลนักศึกษา", "รายวิชาที่เรียน"]

    info = _sheet_values(wb["ข้อมูลนักศึกษา"])
    assert _find_row(info, "รหัสนักศึกษา")[1] == "EXP001"
    assert _find_row(info, "ชื่อ-นามสกุล")[1] == "ทดสอบ EXP001"
    assert _find_row(info, "รุ่น")[1] == 69
    assert _find_row(info, "หลักสูตร")[1] == "หลักสูตรทดสอบ Export (2569)"
    plo1 = _find_row(info, "PLO1")
    assert (plo1[3], plo1[4]) == (90.0, "บรรลุ")
    # PLO2 ไม่มี CLO ผูกอยู่เลย -> ยังไม่มีข้อมูล (แยกจาก "ยังไม่บรรลุ" เหมือนหน้าเว็บ)
    assert _find_row(info, "PLO2")[4] == "ยังไม่มีข้อมูล"
    assert _find_row(info, "บรรลุ PLO")[1] == "1/2 ข้อ"

    courses = _sheet_values(wb["รายวิชาที่เรียน"])
    header = _find_row_containing(courses, "รหัสวิชา")
    assert "Sec" not in header and "เกรด" not in header
    course_row = _find_row_containing(courses, "EXP101")
    assert course_row[3] == "วิชาทดสอบส่งออก"
    assert course_row[5] == "สมชาย ใจดี"
    assert course_row[6] == "2/2"
    assert "A" not in course_row


def test_student_export_not_achieved(client, db_session, admin_user):
    _make_fixtures(db_session, admin_user.id)

    wb = load_workbook(io.BytesIO(client.get("/export/student/EXP002").content))
    plo1 = _find_row(_sheet_values(wb["ข้อมูลนักศึกษา"]), "PLO1")
    assert (plo1[3], plo1[4]) == (40.0, "ยังไม่บรรลุ")
    assert _find_row_containing(_sheet_values(wb["รายวิชาที่เรียน"]), "EXP101")[6] == "0/2"


def test_student_export_non_owner_instructor_sees_plo_but_not_clo(make_client, db_session, admin_user):
    """ผล PLO (ระดับหลักสูตร) เปิดให้อาจารย์ทุกคน แต่ "ผ่าน CLO" ของวิชาที่ไม่ได้สอนต้องเป็น "-" """
    fx = _make_fixtures(db_session, admin_user.id)
    resp = make_client(fx["other"]).get("/export/student/EXP001")
    assert resp.status_code == 200
    wb = load_workbook(io.BytesIO(resp.content))
    assert _find_row(_sheet_values(wb["ข้อมูลนักศึกษา"]), "PLO1")[4] == "บรรลุ"
    courses = _sheet_values(wb["รายวิชาที่เรียน"])
    assert _find_row_containing(courses, "EXP101")[6] == "-"
    assert "* แสดงผล CLO เฉพาะกลุ่มเรียนที่คุณเป็นผู้สอน" in _all_cells(courses)


def test_export_not_found_returns_404(client, db_session):
    assert client.get("/export/course/999999").status_code == 404
    assert client.get("/export/student/NOPE999").status_code == 404
