"""Tests: แอดมินลบบัญชีตัวเอง/ลดสิทธิ์ตัวเองไม่ได้ (กันระบบไม่เหลือแอดมิน) แต่จัดการคนอื่นได้ตามปกติ"""
from __future__ import annotations

from app.models import User


def _make_user(db_session, username: str, role: str) -> User:
    user = User(username=username, password="x", first_name="ทดสอบ", last_name=username, role=role)
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def test_admin_cannot_delete_self(client, db_session, admin_user):
    resp = client.delete(f"/users/{admin_user.id}")
    assert resp.status_code == 400
    assert db_session.get(User, admin_user.id) is not None


def test_admin_cannot_demote_self(client, db_session, admin_user):
    resp = client.put(f"/users/{admin_user.id}", json={"role": "instructor"})
    assert resp.status_code == 400
    db_session.refresh(admin_user)
    assert admin_user.role == "admin"


def test_admin_can_still_edit_own_profile(client, admin_user):
    resp = client.put(f"/users/{admin_user.id}", json={"first_name": "ชื่อใหม่", "role": "admin"})
    assert resp.status_code == 200
    assert resp.json()["first_name"] == "ชื่อใหม่"


def test_admin_can_delete_and_demote_other_admin(client, db_session):
    other_admin = _make_user(db_session, "other-admin", "admin")
    assert client.put(f"/users/{other_admin.id}", json={"role": "instructor"}).status_code == 200
    assert client.delete(f"/users/{other_admin.id}").status_code == 204


def test_admin_can_delete_instructor(client, db_session):
    instructor = _make_user(db_session, "plain-instructor", "instructor")
    assert client.delete(f"/users/{instructor.id}").status_code == 204
