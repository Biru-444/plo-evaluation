"""
Tests สำหรับ Workstream 4 (แผนการแก้ไขครั้งใหญ่-PLO-CLO.md): คำเตือน CLO domain ไม่ตรง PLO category

ครอบคลุม 3 ชั้น:
1. check_domain_category_mismatch() ตรงๆ (pure function, ไม่มี DB) - ตรวจตรรกะเทียบเอง
2. GET /clo-plo-mapping/domain-check - จุดที่แอดมินเรียก real-time ตอนผูก CLO-PLO เองด้วยมือ
3. _add_domain_category_mismatch_flags() (app/routes/course_import.py) - จุดที่ระบบเติม flag ให้เอง
   หลัง Gemini ตอบกลับมาแล้ว (Phase 1 ของ มคอ.3 import)

ทั้ง 2 และ 3 ไม่เรียก Gemini เลย (2 เป็น DB query ล้วนๆ, 3 ทดสอบด้วยการสร้าง
CourseImportFromMCO3Response ปลอมขึ้นมาเองแทนที่จะอัปโหลดไฟล์จริง) เพื่อไม่ให้ test พึ่งพา Gemini API
ที่บางครั้งไม่เสถียร (ดู tests/test_mco3_import_extended.py ที่ต้องพึ่ง Gemini จริง)
"""
from __future__ import annotations

import pytest

from app.models import CLO, Course, Curriculum, PLO
from app.routes.course_import import _add_domain_category_mismatch_flags
from app.schemas.course_import import (
    CourseImportFromMCO3Response,
    MCO3CLOItem,
    MCO3CLOPLOMappingItem,
)
from app.services.domain_category_check import check_domain_category_mismatch


class TestCheckDomainCategoryMismatch:
    def test_matching_domain_and_category_returns_none(self):
        assert check_domain_category_mismatch("knowledge", "ความรู้") is None
        assert check_domain_category_mismatch("skills", "ทักษะ") is None
        assert check_domain_category_mismatch("ethics", "จริยธรรม") is None
        assert check_domain_category_mismatch("character", "ลักษณะบุคคล") is None

    def test_mismatched_domain_and_category_returns_message(self):
        message = check_domain_category_mismatch("knowledge", "ทักษะ")
        assert message is not None
        assert "ความรู้" in message
        assert "ทักษะ" in message

    def test_category_not_matching_any_fixed_option_is_a_mismatch(self):
        # PLO category เป็น "อื่นๆ"/ข้อความอิสระ ที่ไม่ตรงกับ 4 ค่ามาตรฐานเลย - ถือว่าไม่ตรง (เทียบไม่ได้
        # ว่าตรงกันจริง จึงไม่ปล่อยผ่านเงียบๆ)
        message = check_domain_category_mismatch("knowledge", "หมวดที่แต่งเอง")
        assert message is not None

    def test_none_domain_returns_none_not_a_mismatch(self):
        # ยังไม่ได้ระบุ domain ของ CLO นี้ - ไม่มีข้อมูลพอจะเทียบ ไม่ใช่ความขัดแย้ง
        assert check_domain_category_mismatch(None, "ความรู้") is None
        assert check_domain_category_mismatch(None, "หมวดอะไรก็ได้") is None


@pytest.fixture()
def curriculum(db_session):
    curriculum = Curriculum(name="Test Curriculum Domain Check", year=2569)
    db_session.add(curriculum)
    db_session.commit()
    db_session.refresh(curriculum)
    return curriculum


@pytest.fixture()
def plo_knowledge(db_session, curriculum):
    plo = PLO(curriculum_id=curriculum.id, code="PLO1", description_th="ทดสอบ", category="ความรู้")
    db_session.add(plo)
    db_session.commit()
    db_session.refresh(plo)
    return plo


@pytest.fixture()
def plo_skills(db_session, curriculum):
    plo = PLO(curriculum_id=curriculum.id, code="PLO2", description_th="ทดสอบ", category="ทักษะ")
    db_session.add(plo)
    db_session.commit()
    db_session.refresh(plo)
    return plo


@pytest.fixture()
def course_and_clo(db_session, curriculum, admin_user):
    course = Course(
        curriculum_id=curriculum.id, course_code="TEST-DC1", name_th="วิชาทดสอบ", credit=3
    )
    db_session.add(course)
    db_session.commit()
    db_session.refresh(course)

    clo_knowledge = CLO(
        course_id=course.id,
        code="CLO1",
        description="ทดสอบ",
        domain="knowledge",
        created_by=admin_user.id,
    )
    db_session.add(clo_knowledge)
    db_session.commit()
    db_session.refresh(clo_knowledge)
    return course, clo_knowledge


class TestDomainCheckEndpoint:
    def test_matching_domain_returns_no_mismatch(self, client, course_and_clo, plo_knowledge):
        _, clo = course_and_clo
        resp = client.get(
            "/clo-plo-mapping/domain-check", params={"clo_id": clo.id, "plo_id": plo_knowledge.id}
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["mismatch"] is False
        assert body["message"] is None

    def test_mismatched_domain_returns_warning_message(self, client, course_and_clo, plo_skills):
        _, clo = course_and_clo
        resp = client.get(
            "/clo-plo-mapping/domain-check", params={"clo_id": clo.id, "plo_id": plo_skills.id}
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["mismatch"] is True
        assert body["message"] is not None

    def test_invalid_clo_id_returns_404(self, client, plo_knowledge):
        resp = client.get(
            "/clo-plo-mapping/domain-check", params={"clo_id": 999999, "plo_id": plo_knowledge.id}
        )
        assert resp.status_code == 404

    def test_invalid_plo_id_returns_404(self, client, course_and_clo):
        _, clo = course_and_clo
        resp = client.get(
            "/clo-plo-mapping/domain-check", params={"clo_id": clo.id, "plo_id": 999999}
        )
        assert resp.status_code == 404


class TestAddDomainCategoryMismatchFlags:
    """ทดสอบ _add_domain_category_mismatch_flags() ตรงๆ โดยสร้าง CourseImportFromMCO3Response ปลอมขึ้น
    มาเอง (เหมือนเป็นผลลัพธ์ที่ Gemini "ตอบกลับมา" แล้ว) แทนที่จะอัปโหลดไฟล์จริงและรอ Gemini - ทดสอบแค่
    ส่วนที่เป็น pure code-level post-processing เท่านั้น ไม่พึ่ง Gemini เลย"""

    def test_appends_flag_when_mismatched(self, db_session, curriculum, plo_skills):
        fake_result = CourseImportFromMCO3Response(
            course_code="TEST",
            name_th="ทดสอบ",
            credit=3,
            category_raw="วิชาแกน",
            category_mapped="วิชาแกน",
            clos=[MCO3CLOItem(code="CLO1", description="ทดสอบ", domain="knowledge")],
            clo_plo_mapping=[MCO3CLOPLOMappingItem(clo_code="CLO1", plo_code="PLO2")],
        )
        result = _add_domain_category_mismatch_flags(db_session, curriculum.id, fake_result)

        mismatch_flags = [f for f in result.flags if f.type == "domain_category_mismatch"]
        assert len(mismatch_flags) == 1
        assert "CLO1" in mismatch_flags[0].message
        assert "PLO2" in mismatch_flags[0].message

    def test_no_flag_when_matched(self, db_session, curriculum, plo_knowledge):
        fake_result = CourseImportFromMCO3Response(
            course_code="TEST",
            name_th="ทดสอบ",
            credit=3,
            category_raw="วิชาแกน",
            category_mapped="วิชาแกน",
            clos=[MCO3CLOItem(code="CLO1", description="ทดสอบ", domain="knowledge")],
            clo_plo_mapping=[MCO3CLOPLOMappingItem(clo_code="CLO1", plo_code="PLO1")],
        )
        result = _add_domain_category_mismatch_flags(db_session, curriculum.id, fake_result)

        mismatch_flags = [f for f in result.flags if f.type == "domain_category_mismatch"]
        assert len(mismatch_flags) == 0

    def test_no_flag_when_clo_domain_is_null(self, db_session, curriculum, plo_skills):
        fake_result = CourseImportFromMCO3Response(
            course_code="TEST",
            name_th="ทดสอบ",
            credit=3,
            category_raw="วิชาแกน",
            category_mapped="วิชาแกน",
            clos=[MCO3CLOItem(code="CLO1", description="ทดสอบ", domain=None)],
            clo_plo_mapping=[MCO3CLOPLOMappingItem(clo_code="CLO1", plo_code="PLO2")],
        )
        result = _add_domain_category_mismatch_flags(db_session, curriculum.id, fake_result)

        mismatch_flags = [f for f in result.flags if f.type == "domain_category_mismatch"]
        assert len(mismatch_flags) == 0

    def test_multiple_mappings_each_checked_independently(
        self, db_session, curriculum, plo_knowledge, plo_skills
    ):
        fake_result = CourseImportFromMCO3Response(
            course_code="TEST",
            name_th="ทดสอบ",
            credit=3,
            category_raw="วิชาแกน",
            category_mapped="วิชาแกน",
            clos=[
                MCO3CLOItem(code="CLO1", description="ทดสอบ", domain="knowledge"),
                MCO3CLOItem(code="CLO2", description="ทดสอบ", domain="skills"),
            ],
            clo_plo_mapping=[
                MCO3CLOPLOMappingItem(clo_code="CLO1", plo_code="PLO1"),  # ตรง (knowledge/ความรู้)
                MCO3CLOPLOMappingItem(clo_code="CLO2", plo_code="PLO1"),  # ไม่ตรง (skills/ความรู้)
            ],
        )
        result = _add_domain_category_mismatch_flags(db_session, curriculum.id, fake_result)

        mismatch_flags = [f for f in result.flags if f.type == "domain_category_mismatch"]
        assert len(mismatch_flags) == 1
        assert "CLO2" in mismatch_flags[0].message
