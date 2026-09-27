"""Tests สำหรับ POST /course-offerings/{id}/roster-import (2026-09-28) - นำเข้ารายชื่อนักศึกษาจากไฟล์
Excel มหาวิทยาลัยเข้า offering ที่ระบุตรงๆ ให้อาจารย์เจ้าของวิชาใช้เอง (ต่างจาก POST /roster-import เดิม
ที่ admin เท่านั้นและหา/สร้าง course_offering จากไฟล์เอง)

เรียก _apply_roster_import_to_offering() ตรงๆ ด้วย ParsedRoster ที่สร้างขึ้นเอง (ไม่ผ่านการ parse ไฟล์
.xls จริง) สำหรับเทสพฤติกรรมการนำเข้า และเรียกผ่าน HTTP client จริงสำหรับเทสสิทธิ์ (403/ownership) ที่อยู่
ในตัว route เอง - ตามแพทเทิร์นเดียวกับ tests/test_roster_import_no_course.py"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.auth import get_current_user
from app.database import get_db
from app.main import app
from app.models import Course, CourseOffering, Curriculum, Enrollment, Student, User
from app.routes.roster_import import ParsedRoster, _apply_roster_import_to_offering


def _make_parsed(course_code="TESTOFF1", section="1", academic_year=2569, semester=1, students=None):
    return ParsedRoster(
        course_code=course_code,
        course_name="วิชาทดสอบ",
        section=section,
        academic_year=academic_year,
        semester=semester,
        cohort_year=66,
        instructor_names=["อาจารย์ ไม่ควรถูกแตะ เลย"],
        students=students if students is not None else [
            ("66011223001", "นาย", "ทดสอบ", "หนึ่ง"),
            ("66011223002", "นางสาว", "ทดสอบ", "สอง"),
        ],
    )


@pytest.fixture()
def make_client(db_session):
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
def fx(db_session):
    curriculum = Curriculum(name="Test Curriculum Offering Roster", year=2569)
    db_session.add(curriculum)
    db_session.flush()

    course = Course(curriculum_id=curriculum.id, course_code="TESTOFF1", name_th="วิชาทดสอบ", credit=3)
    db_session.add(course)
    db_session.flush()

    owner = User(username="owner-roster", password="x", first_name="เจ้าของ", last_name="วิชา", role="instructor")
    other = User(username="other-roster", password="x", first_name="คนอื่น", last_name="ไม่เกี่ยว", role="instructor")
    admin = User(username="admin-roster", password="x", first_name="แอดมิน", last_name="ทดสอบ", role="admin")
    db_session.add_all([owner, other, admin])
    db_session.flush()

    offering = CourseOffering(
        course_id=course.id, instructor_id=owner.id, academic_year=2569, semester=1, section="1",
    )
    db_session.add(offering)
    db_session.commit()
    db_session.refresh(offering)

    return {
        "curriculum": curriculum, "course": course, "offering": offering,
        "owner": owner, "other": other, "admin": admin,
    }


class TestOwnership:
    def test_owning_instructor_succeeds(self, make_client, fx):
        client = make_client(fx["owner"])
        resp = client.post(
            f"/course-offerings/{fx['offering'].id}/roster-import",
            files={"file": ("x.xls", b"dummy")},
            data={"dry_run": "true"},
        )
        # ผ่านสิทธิ์แล้ว แต่ dummy bytes parse ไม่ผ่าน (400) - แค่ยืนยันว่าไม่ใช่ 403/404
        assert resp.status_code != 403
        assert resp.status_code != 404

    def test_other_instructor_returns_403(self, make_client, fx):
        client = make_client(fx["other"])
        resp = client.post(
            f"/course-offerings/{fx['offering'].id}/roster-import",
            files={"file": ("x.xls", b"dummy")},
            data={"dry_run": "true"},
        )
        assert resp.status_code == 403

    def test_admin_succeeds(self, make_client, fx):
        client = make_client(fx["admin"])
        resp = client.post(
            f"/course-offerings/{fx['offering'].id}/roster-import",
            files={"file": ("x.xls", b"dummy")},
            data={"dry_run": "true"},
        )
        assert resp.status_code != 403
        assert resp.status_code != 404

    def test_nonexistent_offering_returns_404(self, make_client, fx):
        client = make_client(fx["owner"])
        resp = client.post(
            "/course-offerings/999999/roster-import",
            files={"file": ("x.xls", b"dummy")},
            data={"dry_run": "true"},
        )
        assert resp.status_code == 404


class TestApplyLogic:
    def test_new_students_created_and_enrolled(self, db_session, fx):
        parsed = _make_parsed()
        result = _apply_roster_import_to_offering(db_session, parsed, commit=True, offering=fx["offering"])

        assert result.course_mismatch_warning is None
        assert result.offering_id == fx["offering"].id
        assert result.offering_action == "matched_existing"
        assert result.instructors == []
        assert result.new_instructor_credentials == []

        assert db_session.get(Student, "66011223001") is not None
        assert db_session.get(Student, "66011223001").curriculum_id == fx["curriculum"].id
        enrolled = {
            r[0] for r in db_session.query(Enrollment.student_id)
            .filter(Enrollment.offering_id == fx["offering"].id).all()
        }
        assert enrolled == {"66011223001", "66011223002"}

    def test_offering_and_instructor_untouched(self, db_session, fx):
        parsed = _make_parsed()  # instructor_names=["อาจารย์ ไม่ควรถูกแตะ เลย"]
        _apply_roster_import_to_offering(db_session, parsed, commit=True, offering=fx["offering"])

        assert db_session.query(CourseOffering).count() == 1
        refreshed = db_session.get(CourseOffering, fx["offering"].id)
        assert refreshed.instructor_id == fx["owner"].id  # ไม่เปลี่ยนตามชื่อในไฟล์
        assert db_session.query(User).filter(User.role == "instructor").count() == 2  # owner, other เท่านั้น

    def test_mismatched_course_and_section_still_enrolls_with_warning(self, db_session, fx):
        parsed = _make_parsed(course_code="OTHERCODE", section="2", academic_year=2570, semester=2)
        result = _apply_roster_import_to_offering(db_session, parsed, commit=True, offering=fx["offering"])

        assert result.course_mismatch_warning is not None
        assert "OTHERCODE" in result.course_mismatch_warning
        assert "sec 2" in result.course_mismatch_warning
        assert fx["course"].course_code in result.course_mismatch_warning
        # ยังลงทะเบียนเข้า offering ที่ระบุ (ไม่ใช่ไปหา/สร้าง offering ของ OTHERCODE)
        enrolled = {
            r[0] for r in db_session.query(Enrollment.student_id)
            .filter(Enrollment.offering_id == fx["offering"].id).all()
        }
        assert enrolled == {"66011223001", "66011223002"}
        assert db_session.query(Course).filter(Course.course_code == "OTHERCODE").count() == 0

    def test_existing_student_not_duplicated_or_double_enrolled(self, db_session, fx):
        db_session.add(
            Student(
                id="66011223001", curriculum_id=fx["curriculum"].id, first_name="ทดสอบ", last_name="หนึ่ง",
                title="นาย", section="1", cohort_year=66,
            )
        )
        db_session.add(Enrollment(student_id="66011223001", offering_id=fx["offering"].id))
        db_session.commit()

        parsed = _make_parsed()
        result = _apply_roster_import_to_offering(db_session, parsed, commit=True, offering=fx["offering"])

        assert db_session.query(Student).filter(Student.id == "66011223001").count() == 1
        assert db_session.query(Enrollment).filter(
            Enrollment.student_id == "66011223001", Enrollment.offering_id == fx["offering"].id
        ).count() == 1
        row = next(r for r in result.students if r.student_id == "66011223001")
        assert row.action == "unchanged"
        assert result.enrollments_already == 1
        assert result.enrollments_added == 1  # แค่คนที่สอง (66011223002) เป็นคนใหม่

    def test_data_differs_from_file_becomes_update_info(self, db_session, fx):
        db_session.add(
            Student(
                id="66011223001", curriculum_id=fx["curriculum"].id, first_name="ชื่อเก่า", last_name="นามสกุลเก่า",
                cohort_year=66,
            )
        )
        db_session.commit()

        parsed = _make_parsed()
        result = _apply_roster_import_to_offering(db_session, parsed, commit=True, offering=fx["offering"])

        row = next(r for r in result.students if r.student_id == "66011223001")
        assert row.action == "update_info"
        assert "ชื่อเก่า" in row.detail
        updated = db_session.get(Student, "66011223001")
        assert updated.first_name == "ทดสอบ"
        assert updated.last_name == "หนึ่ง"

    def test_dry_run_does_not_persist_anything(self, db_session, fx):
        parsed = _make_parsed()
        _apply_roster_import_to_offering(db_session, parsed, commit=False, offering=fx["offering"])

        assert db_session.query(Student).count() == 0
        assert db_session.query(Enrollment).count() == 0
