"""
Tests สำหรับ POST /courses/import-from-mco3 (app/routes/course_import.py) - ครอบคลุมส่วนที่เพิ่มมา
ในรอบอัปเดต Phase 1 (คำสั่ง-อัปเดต-mco3-import-phase1.md): รองรับ .docx, flag 6 แบบ, ฟิลด์
domain/instructor_name/semester_display

Test เหล่านี้เรียก Gemini API จริง (ไม่ mock) ตามไฟล์ตัวอย่างจริงใน
tests/fixtures/mco3_samples/ - ข้ามอัตโนมัติถ้าไม่มี GEMINI_API_KEY ตั้งไว้ (เช่นตอนรัน CI ที่ไม่มี
key) เพื่อไม่ให้ `pytest tests/` ทั้งชุดพังเฉยๆ สำหรับคนที่ไม่มี key

หมายเหตุ : 4131301-datastructure-title-mismatch.pdf (ไฟล์จริง) ไม่มี test สำหรับ "title_content_mismatch"
เพราะตรวจสอบแล้วว่าไฟล์จริงไม่มีความขัดแย้งหัวเรื่อง/เนื้อหาแบบที่สเปกคาดไว้ (ดู
ปัญหาล่าสุด-และสิ่งที่ต้องทำต่อ.md ข้อ 2) - แทนที่ด้วย synthetic-4122305-title-content-mismatch.docx
ที่สร้างขึ้นเองด้วย python-docx (หัวเรื่องเขียน "ระบบฐานข้อมูล" ตั้งใจให้ขัดกับเนื้อหาที่เป็นวิชา
"โครงสร้างข้อมูล" 4122305 ทั้งฉบับ) ยืนยันแล้วว่า flag ทำงานจริงและสม่ำเสมอ (รันตรง 3 ครั้งก่อนเขียน
test - ไม่ผ่าน TestClient) - ไม่ใช่ไฟล์ มคอ.3 จริงจากที่ไหน สร้างขึ้นมาเพื่อทดสอบ flag นี้โดยเฉพาะ
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from app.models import Curriculum

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "mco3_samples"

requires_gemini_key = pytest.mark.skipif(
    not os.getenv("GEMINI_API_KEY"),
    reason="GEMINI_API_KEY not set - skipping tests that call the real Gemini API",
)


@pytest.fixture()
def cs_curriculum(db_session):
    """หลักสูตรที่ตรงกับเนื้อหาจริงของไฟล์ตัวอย่างทั้งหมด (ทุกไฟล์เป็นวิชาของหลักสูตรวิทยาการ
    คอมพิวเตอร์) - ตั้งชื่อให้ตรงเพื่อไม่ให้ flag "curriculum_mismatch" ติดมาปนกับ flag ที่กำลังทดสอบ"""
    curriculum = Curriculum(
        name="หลักสูตรวิทยาศาสตรบัณฑิต สาขาวิชาวิทยาการคอมพิวเตอร์ (หลักสูตรปรับปรุง พ.ศ. 2566)",
        year=2566,
    )
    db_session.add(curriculum)
    db_session.commit()
    db_session.refresh(curriculum)
    return curriculum


def _import_sample(client, filename: str, curriculum_id: int, content_type: str):
    with open(FIXTURES_DIR / filename, "rb") as f:
        data = f.read()
    resp = client.post(
        "/courses/import-from-mco3",
        files={"file": (filename, data, content_type)},
        data={"curriculum_id": str(curriculum_id)},
    )
    return resp


@requires_gemini_key
def test_database_v2_flags_checkbox_ambiguous_with_total_count(client, cs_curriculum):
    """4122304-database-v2-with-total-column.pdf - ตาราง PLOxCLO แบบกาเครื่องหมายที่มีคอลัมน์ "รวม"
    ต้องได้ flag checkbox_ambiguous - เช็คแค่ว่า flag type เกิดขึ้นจริง ไม่ assert คำว่า "รวม" ในข้อความ
    แบบเป๊ะๆ (เคยเจอ Gemini ตอบไม่มีคำนี้บางรอบ ทั้งที่ flag ถูกต้อง - สาเหตุคือ LLM ไม่ deterministic
    ไม่ใช่ logic ผิด ดู ปัญหาล่าสุด-และสิ่งที่ต้องทำต่อ.md ข้อ 1 กับสิ่งที่ต้องทำต่อข้อ 2)"""
    resp = _import_sample(
        client, "4122304-database-v2-with-total-column.pdf", cs_curriculum.id, "application/pdf"
    )
    assert resp.status_code == 200
    body = resp.json()

    assert body["course_code"] == "4122304"
    assert body["clo_plo_mapping"] == []

    checkbox_flags = [f for f in body["flags"] if f["type"] == "checkbox_ambiguous"]
    assert len(checkbox_flags) == 1

    # ไฟล์นี้มี (K)/(S)/(A)/(C) กำกับ CLO ชัดเจน - domain ต้องไม่ใช่ null ทั้งหมด
    domains = [c["domain"] for c in body["clos"]]
    assert any(d is not None for d in domains)


@requires_gemini_key
def test_uxui_flags_duplicate_course_code(client, cs_curriculum):
    """4122301-uxui-duplicate-code.pdf - รหัสวิชาในหมวดที่ 1 (4122301) ไม่ตรงกับหมวดที่ 2 (4123310)
    ต้องได้ flag duplicate_course_code ระบุทั้งสองค่าที่ขัดแย้งกัน"""
    resp = _import_sample(client, "4122301-uxui-duplicate-code.pdf", cs_curriculum.id, "application/pdf")
    assert resp.status_code == 200
    body = resp.json()

    duplicate_flags = [f for f in body["flags"] if f["type"] == "duplicate_course_code"]
    assert len(duplicate_flags) == 1
    assert "4122301" in duplicate_flags[0]["message"]
    assert "4123310" in duplicate_flags[0]["message"]


@requires_gemini_key
def test_aunqa_docx_succeeds_and_flags_plo_mapping_not_filled(client, cs_curriculum):
    """4123501-aunqa-empty-mapping.docx - path .docx ต้องผ่านสำเร็จ (200, ไม่ error) และตาราง PLO-CLO
    ที่ว่างเปล่าทั้งตารางต้องได้ flag plo_mapping_not_filled ไม่ใช่ checkbox_ambiguous (คนละสาเหตุกัน)"""
    resp = _import_sample(
        client,
        "4123501-aunqa-empty-mapping.docx",
        cs_curriculum.id,
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )
    assert resp.status_code == 200
    body = resp.json()

    assert body["course_code"] == "4123501"
    assert body["clo_plo_mapping"] == []
    assert body["instructor_name"] is not None
    assert body["semester_display"] is not None

    flag_types = {f["type"] for f in body["flags"]}
    assert "plo_mapping_not_filled" in flag_types
    assert "checkbox_ambiguous" not in flag_types

    # ไฟล์นี้มี (k)/(S) กำกับ CLO1-4 ชัดเจน (CLO5 มี "(E/C)" ที่ไม่มาตรฐาน ต้องเป็น null) -
    # domain ต้องไม่ใช่ null ทั้งหมด
    domains = [c["domain"] for c in body["clos"]]
    assert any(d is not None for d in domains)


@requires_gemini_key
def test_synthetic_title_content_mismatch(client, cs_curriculum):
    """synthetic-4122305-title-content-mismatch.docx (สร้างเองด้วย python-docx ไม่ใช่ไฟล์จริง - ดู
    module docstring) - หัวเรื่องเขียนว่า "ระบบฐานข้อมูล" แต่เนื้อหาทั้งฉบับเป็นวิชา "โครงสร้างข้อมูล"
    รหัส 4122305 ต้องได้ flag title_content_mismatch"""
    resp = _import_sample(
        client,
        "synthetic-4122305-title-content-mismatch.docx",
        cs_curriculum.id,
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )
    assert resp.status_code == 200
    body = resp.json()

    assert body["course_code"] == "4122305"
    flag_types = {f["type"] for f in body["flags"]}
    assert "title_content_mismatch" in flag_types


def test_rejects_unsupported_file_extension(client, cs_curriculum):
    """นามสกุลไฟล์ที่ไม่รองรับ (เช่น .txt) ต้องโดน 400 ก่อนเรียก Gemini เลย ไม่ใช่ error อื่น - ไม่ต้อง
    skip ตาม GEMINI_API_KEY เพราะ endpoint ปฏิเสธก่อนเรียก Gemini เสมอ"""
    resp = client.post(
        "/courses/import-from-mco3",
        files={"file": ("notes.txt", b"random text content", "text/plain")},
        data={"curriculum_id": str(cs_curriculum.id)},
    )
    assert resp.status_code == 400
