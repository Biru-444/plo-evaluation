"""Tests สำหรับการบังคับ `domain` ตอนสร้าง CLO ผ่าน POST /clo (ฟอร์ม "จัดการ CLO" ในแอดมิน) และ
การเติม/แก้ domain ผ่าน PUT /clo/{id}

หมายเหตุ : ไม่ได้เพิ่มคอลัมน์ใหม่ - ใช้ clo.domain ที่มีอยู่แล้ว (Workstream 4, ดู
scripts/migrate_add_clo_domain.py) เป็น "ประเภท CLO" โดยตรง เดิม CLOCreateSchema/CLOUpdateSchema
ไม่รับ domain จากไคลเอนต์เลย (ตั้งค่าได้ทางเดียวคือตอนนำเข้า มคอ.3 ที่ construct CLO(...) ข้าม schema)
งานนี้เปิดให้ตั้ง/แก้ domain ผ่าน API ปกติได้ และบังคับให้ต้องส่งมาตอนสร้าง (ตรวจ mismatch ยังใช้
check_domain_category_mismatch/GET /clo-plo-mapping/domain-check เดิมของเพื่อน ไม่มี logic ใหม่ - ดู
tests/test_domain_category_check.py)"""
from __future__ import annotations

import pytest

from app.models import Course, Curriculum


@pytest.fixture()
def course(db_session):
    curriculum = Curriculum(name="Test Curriculum CLO Domain", year=2569)
    db_session.add(curriculum)
    db_session.flush()
    course = Course(
        curriculum_id=curriculum.id, course_code="TESTCD1", name_th="วิชาทดสอบ", credit=3
    )
    db_session.add(course)
    db_session.commit()
    db_session.refresh(course)
    return course


def test_create_without_domain_returns_422(client, course):
    resp = client.post(
        "/clo",
        json={"course_id": course.id, "code": "CLO1", "description": "ทดสอบ"},
    )
    assert resp.status_code == 422


def test_create_with_invalid_domain_returns_422(client, course):
    resp = client.post(
        "/clo",
        json={
            "course_id": course.id,
            "code": "CLO1",
            "description": "ทดสอบ",
            "domain": "not-a-real-domain",
        },
    )
    assert resp.status_code == 422


def test_create_with_valid_domain_succeeds(client, course):
    resp = client.post(
        "/clo",
        json={
            "course_id": course.id,
            "code": "CLO1",
            "description": "ทดสอบ",
            "domain": "skills",
        },
    )
    assert resp.status_code == 201
    assert resp.json()["domain"] == "skills"


def test_update_can_fill_in_missing_domain(client, course):
    create_resp = client.post(
        "/clo",
        json={
            "course_id": course.id,
            "code": "CLO1",
            "description": "ทดสอบ",
            "domain": "knowledge",
        },
    )
    clo_id = create_resp.json()["id"]

    resp = client.put(f"/clo/{clo_id}", json={"domain": "ethics"})
    assert resp.status_code == 200
    assert resp.json()["domain"] == "ethics"


def test_update_without_domain_does_not_clear_it(client, course):
    create_resp = client.post(
        "/clo",
        json={
            "course_id": course.id,
            "code": "CLO1",
            "description": "ทดสอบ",
            "domain": "character",
        },
    )
    clo_id = create_resp.json()["id"]

    resp = client.put(f"/clo/{clo_id}", json={"description": "แก้คำอธิบายอย่างเดียว"})
    assert resp.status_code == 200
    assert resp.json()["domain"] == "character"
