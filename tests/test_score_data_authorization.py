"""
Tests: course-level score data authorization policy (2026-09 audit decision) -
GET /clo-achievement, GET /clo-achievement/student-course, GET /student-scores, GET /enrollments,
GET /enrollments/{id} -> admin or the offering's instructor only (403 for any other instructor).
Contrast with curriculum-level endpoints (PLO/YLO achievement dashboards), which stay open to any
authenticated admin/instructor on purpose - see the "สิทธิ์" docstring lines added to each endpoint
in app/routes/plo_calculation.py and app/routes/ylo_calculation.py for the reasoning.

make_client fixture is the same pattern as test_clo_plo_mapping.py's - conftest.py's `client` fixture
is hardcoded to admin_user, so ownership checks need a way to impersonate a specific non-admin user.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.auth import get_current_user
from app.database import get_db
from app.main import app
from app.models import (
    CLO,
    AssessmentItem,
    Course,
    CourseOffering,
    Curriculum,
    Enrollment,
    ItemCLO,
    Student,
    StudentScore,
    User,
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


def _make_fixtures(db_session):
    """หลักสูตร + วิชา + offering เดียว (เจ้าของ = owner) + อาจารย์อีกคนที่ไม่เกี่ยว (other) +
    นักศึกษา 1 คนลงทะเบียนแล้ว พร้อม CLO/assessment_item/item_clo/คะแนน 1 รายการ"""
    curriculum = Curriculum(name="Test Curriculum ScoreAuth", year=2569)
    db_session.add(curriculum)
    db_session.flush()

    course = Course(curriculum_id=curriculum.id, course_code="TESTSA1", name_th="วิชาทดสอบสิทธิ์", credit=3)
    db_session.add(course)
    db_session.flush()

    owner = User(
        username="scoreauth-owner", password="x", first_name="เจ้าของ", last_name="วิชา", role="instructor"
    )
    other = User(
        username="scoreauth-other", password="x", first_name="คนอื่น", last_name="ไม่เกี่ยว", role="instructor"
    )
    db_session.add_all([owner, other])
    db_session.flush()

    offering = CourseOffering(
        course_id=course.id, instructor_id=owner.id, academic_year=2569, semester=1, section="1"
    )
    db_session.add(offering)
    db_session.flush()

    student = Student(
        id="SATEST01", curriculum_id=curriculum.id, first_name="ทดสอบ", last_name="สิทธิ์", cohort_year=69
    )
    db_session.add(student)
    db_session.add(Enrollment(student_id=student.id, offering_id=offering.id))
    db_session.flush()

    clo = CLO(
        course_id=course.id, code="CLO1", description="ทดสอบ", pass_threshold_percent=60.0, created_by=owner.id
    )
    db_session.add(clo)
    db_session.flush()

    item = AssessmentItem(offering_id=offering.id, name="quiz1", type="quiz", total_score=100.0)
    db_session.add(item)
    db_session.flush()

    db_session.add(ItemCLO(item_id=item.id, clo_id=clo.id, weight_percent=100.0))
    db_session.add(StudentScore(item_id=item.id, student_id=student.id, score_obtained=80.0))
    db_session.flush()

    return {
        "curriculum": curriculum,
        "course": course,
        "owner": owner,
        "other": other,
        "offering": offering,
        "student": student,
        "clo": clo,
        "item": item,
    }


class TestCLOAchievement:
    def test_owner_instructor_can_view(self, make_client, db_session):
        fx = _make_fixtures(db_session)
        db_session.commit()
        resp = make_client(fx["owner"]).get(f"/clo-achievement?offering_id={fx['offering'].id}")
        assert resp.status_code == 200

    def test_admin_can_view(self, client, db_session):
        fx = _make_fixtures(db_session)
        db_session.commit()
        resp = client.get(f"/clo-achievement?offering_id={fx['offering'].id}")
        assert resp.status_code == 200

    def test_non_owner_instructor_gets_403(self, make_client, db_session):
        fx = _make_fixtures(db_session)
        db_session.commit()
        resp = make_client(fx["other"]).get(f"/clo-achievement?offering_id={fx['offering'].id}")
        assert resp.status_code == 403


class TestCLOStudentCourseBreakdown:
    def test_owner_instructor_can_view(self, make_client, db_session):
        fx = _make_fixtures(db_session)
        db_session.commit()
        resp = make_client(fx["owner"]).get(
            f"/clo-achievement/student-course?student_id={fx['student'].id}&course_id={fx['course'].id}"
        )
        assert resp.status_code == 200

    def test_admin_can_view(self, client, db_session):
        fx = _make_fixtures(db_session)
        db_session.commit()
        resp = client.get(
            f"/clo-achievement/student-course?student_id={fx['student'].id}&course_id={fx['course'].id}"
        )
        assert resp.status_code == 200

    def test_non_owner_instructor_gets_403(self, make_client, db_session):
        fx = _make_fixtures(db_session)
        db_session.commit()
        resp = make_client(fx["other"]).get(
            f"/clo-achievement/student-course?student_id={fx['student'].id}&course_id={fx['course'].id}"
        )
        assert resp.status_code == 403

    def test_never_enrolled_allows_any_instructor(self, make_client, db_session):
        """ไม่มี offering ให้เช็คความเป็นเจ้าของ (นักศึกษาไม่เคยลงทะเบียนวิชานี้เลย) - ไม่มีคะแนนให้
        รั่วอยู่แล้ว (mastery_percent เป็น None ทุกข้อ) ปล่อยผ่านได้"""
        fx = _make_fixtures(db_session)
        other_student = Student(
            id="SATEST02",
            curriculum_id=fx["curriculum"].id,
            first_name="ไม่ได้ลง",
            last_name="ทะเบียน",
            cohort_year=69,
        )
        db_session.add(other_student)
        db_session.commit()
        resp = make_client(fx["other"]).get(
            f"/clo-achievement/student-course?student_id={other_student.id}&course_id={fx['course'].id}"
        )
        assert resp.status_code == 200
        assert resp.json()["offering_id"] is None


class TestStudentScores:
    def test_owner_instructor_can_view_by_offering(self, make_client, db_session):
        fx = _make_fixtures(db_session)
        db_session.commit()
        resp = make_client(fx["owner"]).get(f"/student-scores?offering_id={fx['offering'].id}")
        assert resp.status_code == 200

    def test_admin_can_view_by_offering(self, client, db_session):
        fx = _make_fixtures(db_session)
        db_session.commit()
        resp = client.get(f"/student-scores?offering_id={fx['offering'].id}")
        assert resp.status_code == 200

    def test_non_owner_instructor_gets_403_by_offering(self, make_client, db_session):
        fx = _make_fixtures(db_session)
        db_session.commit()
        resp = make_client(fx["other"]).get(f"/student-scores?offering_id={fx['offering'].id}")
        assert resp.status_code == 403

    def test_non_owner_instructor_by_student_id_sees_empty_not_403(self, make_client, db_session):
        """student_id เดี่ยวๆ ไม่ 403 ทั้ง request (คะแนนอาจกระจายหลาย offering คนละอาจารย์ - ไม่มี
        "เจ้าของ" เดียวให้เช็คตรงๆ) แต่กรองแถวผลลัพธ์เหลือเฉพาะ offering ที่ตัวเองสอนแทน - คนที่ไม่ได้
        สอนวิชานี้เลยจึงเห็นลิสต์ว่างเปล่า ไม่ใช่ error"""
        fx = _make_fixtures(db_session)
        db_session.commit()
        resp = make_client(fx["other"]).get(f"/student-scores?student_id={fx['student'].id}")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_owner_instructor_by_student_id_sees_own_offering_scores(self, make_client, db_session):
        fx = _make_fixtures(db_session)
        db_session.commit()
        resp = make_client(fx["owner"]).get(f"/student-scores?student_id={fx['student'].id}")
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    def test_admin_by_student_id_sees_all(self, client, db_session):
        fx = _make_fixtures(db_session)
        db_session.commit()
        resp = client.get(f"/student-scores?student_id={fx['student'].id}")
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    def test_no_params_returns_400(self, client):
        resp = client.get("/student-scores")
        assert resp.status_code == 400


class TestEnrollments:
    def test_owner_instructor_can_list_by_offering(self, make_client, db_session):
        fx = _make_fixtures(db_session)
        db_session.commit()
        resp = make_client(fx["owner"]).get(f"/enrollments?offering_id={fx['offering'].id}")
        assert resp.status_code == 200

    def test_admin_can_list_by_offering(self, client, db_session):
        fx = _make_fixtures(db_session)
        db_session.commit()
        resp = client.get(f"/enrollments?offering_id={fx['offering'].id}")
        assert resp.status_code == 200

    def test_non_owner_instructor_gets_403_by_offering(self, make_client, db_session):
        fx = _make_fixtures(db_session)
        db_session.commit()
        resp = make_client(fx["other"]).get(f"/enrollments?offering_id={fx['offering'].id}")
        assert resp.status_code == 403

    def test_instructor_gets_403_for_student_id_only(self, make_client, db_session):
        """ไม่ระบุ offering_id เลย (ไม่ว่าจะระบุ student_id หรือไม่ก็ตาม) - จำกัดแค่ admin เพราะผลลัพธ์
        อาจกระจายข้าม offering คนละอาจารย์ ไม่มี "เจ้าของ" เดียวให้ 403 ตรงๆ ได้ (ต่างจาก /student-scores
        ที่เลือกกรองแถวแทน - ที่นี่เลือกบล็อกทั้ง request เพราะผู้เรียกจริงตอนนี้ (AdminEnrollments.jsx)
        เป็นหน้า admin-only อยู่แล้ว ไม่มี workflow ของอาจารย์ทั่วไปที่ต้องพึ่ง endpoint นี้แบบนี้)"""
        fx = _make_fixtures(db_session)
        db_session.commit()
        resp = make_client(fx["owner"]).get(f"/enrollments?student_id={fx['student'].id}")
        assert resp.status_code == 403

    def test_admin_can_query_by_student_id_only(self, client, db_session):
        fx = _make_fixtures(db_session)
        db_session.commit()
        resp = client.get(f"/enrollments?student_id={fx['student'].id}")
        assert resp.status_code == 200

    def test_get_single_enrollment_owner_succeeds(self, make_client, db_session):
        fx = _make_fixtures(db_session)
        enrollment = db_session.query(Enrollment).filter(Enrollment.student_id == fx["student"].id).first()
        db_session.commit()
        resp = make_client(fx["owner"]).get(f"/enrollments/{enrollment.id}")
        assert resp.status_code == 200

    def test_get_single_enrollment_admin_succeeds(self, client, db_session):
        fx = _make_fixtures(db_session)
        enrollment = db_session.query(Enrollment).filter(Enrollment.student_id == fx["student"].id).first()
        db_session.commit()
        resp = client.get(f"/enrollments/{enrollment.id}")
        assert resp.status_code == 200

    def test_get_single_enrollment_non_owner_gets_403(self, make_client, db_session):
        fx = _make_fixtures(db_session)
        enrollment = db_session.query(Enrollment).filter(Enrollment.student_id == fx["student"].id).first()
        db_session.commit()
        resp = make_client(fx["other"]).get(f"/enrollments/{enrollment.id}")
        assert resp.status_code == 403


class TestCurriculumLevelStaysOpen:
    """Smoke check: curriculum-level endpoints stay open to any authenticated admin/instructor,
    including one that teaches nothing in this curriculum - intentional contrast with the
    course-level 403s above (see the "สิทธิ์" docstring lines in plo_calculation.py/ylo_calculation.py)."""

    def test_plo_achievement_cohort_open_to_any_instructor(self, make_client, db_session):
        fx = _make_fixtures(db_session)
        db_session.commit()
        resp = make_client(fx["other"]).get(f"/plo/achievement/cohort?curriculum_id={fx['curriculum'].id}")
        assert resp.status_code == 200

    def test_plo_achievement_individual_open_to_any_instructor(self, make_client, db_session):
        fx = _make_fixtures(db_session)
        db_session.commit()
        resp = make_client(fx["other"]).get(f"/plo/achievement?student_id={fx['student'].id}")
        assert resp.status_code == 200

    def test_ylo_achievement_by_year_open_to_any_instructor(self, make_client, db_session):
        fx = _make_fixtures(db_session)
        db_session.commit()
        resp = make_client(fx["other"]).get(
            f"/ylo/achievement/by-year?curriculum_id={fx['curriculum'].id}&year_level=1"
        )
        assert resp.status_code == 200

    def test_ylo_achievement_student_open_to_any_instructor(self, make_client, db_session):
        fx = _make_fixtures(db_session)
        db_session.commit()
        resp = make_client(fx["other"]).get(f"/ylo/achievement/student?student_id={fx['student'].id}")
        assert resp.status_code == 200
