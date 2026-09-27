"""Tests สำหรับพฤติกรรมใหม่ของ /roster-import ตอนไม่พบวิชาในระบบ (ผู้ใช้ระบุ 2026-09-27): เดิม
_apply_roster_import() คืน error แล้วหยุดทั้งหมดทันที (ไม่มี preview รายชื่อนักศึกษาเลย) - เปลี่ยนเป็นนำเข้า
เฉพาะรายชื่อนักศึกษา (สร้าง/อัปเดตตามปกติ) โดยไม่สร้างวิชา/course_offering/enrollment ให้ ต้องมี
curriculum_id ที่ผู้ใช้เลือกเอง (แทน course.curriculum_id ที่ปกติได้มาจากวิชา) ก่อนถึง commit ได้จริง

ทดสอบเรียก _apply_roster_import() ตรงๆ ด้วย ParsedRoster ที่สร้างขึ้นเอง (ไม่ผ่านการ parse ไฟล์ .xls จริง)
ตามแพทเทิร์นเดียวกับ tests/test_domain_category_check.py::TestAddDomainCategoryMismatchFlags"""
from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.models import Course, CourseOffering, Curriculum, Enrollment, Student
from app.routes.roster_import import ParsedRoster, _apply_roster_import


def _make_parsed(course_code: str = "NOEXIST101", students=None) -> ParsedRoster:
    return ParsedRoster(
        course_code=course_code,
        course_name="วิชาที่ไม่มีในระบบ",
        section="01",
        academic_year=2569,
        semester=1,
        cohort_year=66,
        instructor_names=["อาจารย์ สมชาย ใจดี"],
        students=students if students is not None else [
            ("66011223001", "นาย", "ทดสอบ", "หนึ่ง"),
            ("66011223002", "นางสาว", "ทดสอบ", "สอง"),
        ],
    )


@pytest.fixture()
def curriculum(db_session):
    c = Curriculum(name="Test Curriculum Roster No-Course", year=2569)
    db_session.add(c)
    db_session.commit()
    db_session.refresh(c)
    return c


class TestCommitWithoutCourse:
    def test_missing_curriculum_id_returns_422(self, db_session):
        parsed = _make_parsed()
        with pytest.raises(HTTPException) as exc_info:
            _apply_roster_import(db_session, parsed, commit=True, curriculum_id=None)
        assert exc_info.value.status_code == 422

    def test_invalid_curriculum_id_returns_422(self, db_session):
        parsed = _make_parsed()
        with pytest.raises(HTTPException) as exc_info:
            _apply_roster_import(db_session, parsed, commit=True, curriculum_id=999999)
        assert exc_info.value.status_code == 422

    def test_creates_students_only_no_course_offering_or_enrollment(self, db_session, curriculum):
        parsed = _make_parsed()
        result = _apply_roster_import(db_session, parsed, commit=True, curriculum_id=curriculum.id)

        assert result.course_found is False
        assert result.offering_action == "skipped_no_course"
        assert result.offering_id is None
        assert result.needs_curriculum_id is False

        assert db_session.get(Student, "66011223001") is not None
        assert db_session.get(Student, "66011223002") is not None
        assert db_session.get(Student, "66011223001").curriculum_id == curriculum.id
        assert db_session.query(Course).filter(Course.course_code == parsed.course_code).count() == 0
        assert db_session.query(CourseOffering).count() == 0
        assert db_session.query(Enrollment).count() == 0
        assert result.summary["enrollments_skipped_no_course"] == 2
        assert result.summary["enrollments_added"] == 0

    def test_existing_student_not_duplicated(self, db_session, curriculum):
        # title/section ต้องตรงกับที่ _make_parsed() จะส่งมาเป๊ะๆ (title="นาย", section="01") ไม่งั้น
        # จะกลายเป็น action="update_info" (ก็ยังไม่ใช่ "create" ซ้ำอยู่ดี แต่ทดสอบ "unchanged" ให้ตรงเป้า
        # กว่า)
        db_session.add(
            Student(
                id="66011223001", curriculum_id=curriculum.id, first_name="ทดสอบ", last_name="หนึ่ง",
                title="นาย", section="01", cohort_year=66,
            )
        )
        db_session.commit()

        parsed = _make_parsed()
        result = _apply_roster_import(db_session, parsed, commit=True, curriculum_id=curriculum.id)

        assert db_session.query(Student).filter(Student.id == "66011223001").count() == 1
        row = next(r for r in result.students if r.student_id == "66011223001")
        assert row.action == "unchanged"


class TestPreviewWithoutCourse:
    def test_dry_run_without_curriculum_id_still_shows_students(self, db_session):
        parsed = _make_parsed()
        result = _apply_roster_import(db_session, parsed, commit=False, curriculum_id=None)

        assert result.course_found is False
        assert result.needs_curriculum_id is True
        assert len(result.students) == 2
        assert {r.student_id for r in result.students} == {"66011223001", "66011223002"}
        # dry-run ไม่บันทึกจริง - ต้องไม่มีอะไรถูกสร้างเลย
        assert db_session.query(Student).count() == 0

    def test_dry_run_with_curriculum_id_no_longer_needs_it(self, db_session, curriculum):
        parsed = _make_parsed()
        result = _apply_roster_import(db_session, parsed, commit=False, curriculum_id=curriculum.id)

        assert result.needs_curriculum_id is False
        assert db_session.query(Student).count() == 0  # dry-run ยังไม่บันทึกจริง


class TestCourseFoundUnaffected:
    """วิชามีในระบบ - ต้องทำงานเหมือนเดิมทุกอย่าง (regression guard สำหรับการเปลี่ยนแปลงนี้)"""

    def test_creates_course_offering_and_enrollment_as_before(self, db_session, curriculum):
        course = Course(
            curriculum_id=curriculum.id, course_code="EXISTS101", name_th="วิชาที่มีอยู่แล้ว", credit=3,
        )
        db_session.add(course)
        db_session.commit()

        parsed = _make_parsed(course_code="EXISTS101")
        # ส่ง curriculum_id ที่ไม่เกี่ยวข้องมาด้วย (ของหลักสูตรอื่นก็ได้) - ต้องถูกละเลยเพราะมีวิชาอยู่แล้ว
        result = _apply_roster_import(db_session, parsed, commit=True, curriculum_id=999999)

        assert result.course_found is True
        assert result.offering_action == "created"
        assert result.offering_id is not None
        assert result.needs_curriculum_id is False
        assert db_session.query(CourseOffering).count() == 1
        assert db_session.query(Enrollment).count() == 2
        student = db_session.get(Student, "66011223001")
        assert student is not None
        assert student.curriculum_id == curriculum.id  # ใช้ course.curriculum_id ไม่ใช่ 999999 ที่ส่งมา
