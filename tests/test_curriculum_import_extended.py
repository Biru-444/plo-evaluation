"""
Tests สำหรับ POST /curricula/import-from-mco2 (Phase 1 - app/routes/curriculum_import.py)

Test เหล่านี้เรียก Gemini API จริง (ไม่ mock) เหมือน tests/test_mco3_import_extended.py - ข้าม
อัตโนมัติถ้าไม่มี GEMINI_API_KEY ตั้งไว้ ไม่มีไฟล์ มคอ.2 จริงให้ใช้ตอนนี้ (ต่างจาก มคอ.3 ที่มีไฟล์
ตัวอย่างจริงใน tests/fixtures/mco3_samples/) จึงสร้างไฟล์สังเคราะห์เองด้วย python-docx เหมือน
synthetic-4122305-title-content-mismatch.docx ที่ tests/test_mco3_import_extended.py ใช้เป็น
บรรทัดฐาน (ดูคอมเมนต์หัวไฟล์นั้น) - ทดสอบแค่ปลั๊กท่อทั้งชุด (extraction -> existing_curriculum_id
detection) ไม่ได้ทดสอบความแม่นยำสุดขั้วของ Gemini กับเอกสารจริงหลากหลายรูปแบบแบบ มคอ.3
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from app.models import Curriculum

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "mco2_samples"

requires_gemini_key = pytest.mark.skipif(
    not os.getenv("GEMINI_API_KEY"),
    reason="GEMINI_API_KEY not set - skipping tests that call the real Gemini API",
)


def _import_sample(client, filename: str):
    with open(FIXTURES_DIR / filename, "rb") as f:
        data = f.read()
    resp = client.post(
        "/curricula/import-from-mco2",
        files={
            "file": (
                filename,
                data,
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
    )
    return resp


@requires_gemini_key
def test_synthetic_curriculum_extracts_name_year_and_plos(client):
    resp = _import_sample(client, "synthetic-test-curriculum.docx")
    assert resp.status_code == 200
    body = resp.json()

    assert body["curriculum_year"] == 2567
    assert "ปัญญาประดิษฐ์ทดสอบ" in body["curriculum_name"]
    assert len(body["plos"]) == 3

    categories = {p["code"]: p["category"] for p in body["plos"]}
    assert categories.get("PLO1") == "ความรู้"
    assert categories.get("PLO2") == "ทักษะ"
    assert categories.get("PLO3") == "จริยธรรม"

    assert body["existing_curriculum_id"] is None
    assert body["existing_plo_codes"] == []


@requires_gemini_key
def test_synthetic_curriculum_detects_existing_curriculum(client, db_session):
    """ถ้ามีหลักสูตรชื่อ+ปีตรงกับที่แกะได้อยู่แล้วในระบบ existing_curriculum_id ต้องไม่ null - เช็คนี้
    เป็น pure code-level (เทียบจาก DB ตรงๆ ไม่ใช่ Gemini ตัดสิน) ดู
    app/routes/curriculum_import.py::_add_existing_curriculum_info"""
    resp_first = _import_sample(client, "synthetic-test-curriculum.docx")
    curriculum_name = resp_first.json()["curriculum_name"]
    curriculum_year = resp_first.json()["curriculum_year"]

    existing = Curriculum(name=curriculum_name, year=curriculum_year)
    db_session.add(existing)
    db_session.commit()
    db_session.refresh(existing)

    resp_second = _import_sample(client, "synthetic-test-curriculum.docx")
    assert resp_second.status_code == 200
    body = resp_second.json()
    assert body["existing_curriculum_id"] == existing.id
