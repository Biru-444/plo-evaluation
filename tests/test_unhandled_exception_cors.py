"""
Tests สำหรับ app.main::unhandled_exception_handler - regression test สำหรับปัญหาที่เจอจริง (2026-09):
frontend (Vercel) เรียก backend (Render) ข้าม origin แล้วได้ 500 จาก exception ที่ไม่มีใคร handle -
เบราว์เซอร์รายงานเป็น "blocked by CORS policy" แทนที่จะเป็น 500 จริงๆ เพราะ response ของ
ServerErrorMiddleware (Starlette เริ่มต้น) ไม่ผ่าน CORSMiddleware เลย จึงไม่มี header
Access-Control-Allow-Origin ติดไปด้วย - handler ใหม่ทำให้ FastAPI's ExceptionMiddleware (อยู่ในกว่า
CORSMiddleware) เป็นคนจัดการแทน ทำให้ response วิ่งผ่าน CORSMiddleware ตามปกติ

ใช้ monkeypatch บังคับให้ endpoint จริง (GET /plo/achievement/cohort) โยน exception ที่ไม่ใช่
HTTPException ออกมา (จำลอง bug จริงในโค้ดคำนวณ) แล้วเช็คว่า response ที่ได้:
  1. status 500 พร้อม detail message (ไม่ใช่ crash ที่ TestClient re-raise ให้เห็น traceback ตรงๆ)
  2. มี header Access-Control-Allow-Origin ติดมาด้วยเมื่อ request มี Origin header (พิสูจน์ว่าวิ่งผ่าน
     CORSMiddleware จริง)
  3. HTTPException ปกติ (เช่น 404) ยังทำงานเหมือนเดิมทุกประการ ไม่ถูก handler ใหม่นี้แย่งไปจัดการ
"""
from __future__ import annotations

import app.routes.plo_calculation as plo_calculation_route


def test_unhandled_exception_returns_500_with_cors_header(client, monkeypatch):
    def _boom(db, curriculum_id, cohort_year=None):
        raise RuntimeError("simulated bug in compute_cohort_plo_achievement")

    monkeypatch.setattr(plo_calculation_route, "compute_cohort_plo_achievement", _boom)

    resp = client.get(
        "/plo/achievement/cohort?curriculum_id=1",
        headers={"Origin": "http://localhost:3000"},
    )

    assert resp.status_code == 500
    assert resp.json() == {"detail": "Internal server error"}
    assert resp.headers.get("access-control-allow-origin") == "http://localhost:3000"


def test_unhandled_exception_from_disallowed_origin_gets_500_without_cors_header(client, monkeypatch):
    """Origin ที่ไม่อยู่ใน ALLOWED_ORIGINS ต้องไม่ได้ header กลับมา (CORSMiddleware ทำงานถูกต้องตามปกติ
    ไม่ใช่ handler ใหม่นี้เปิดกว้างให้ origin ไหนก็ได้แบบผิดสเปก)"""

    def _boom(db, curriculum_id, cohort_year=None):
        raise RuntimeError("simulated bug")

    monkeypatch.setattr(plo_calculation_route, "compute_cohort_plo_achievement", _boom)

    resp = client.get(
        "/plo/achievement/cohort?curriculum_id=1",
        headers={"Origin": "http://evil.example.com"},
    )

    assert resp.status_code == 500
    assert "access-control-allow-origin" not in {k.lower() for k in resp.headers.keys()}


def test_ordinary_http_exception_still_handled_normally(client):
    """404 ปกติ (HTTPException ที่ตั้งใจ raise) ต้องยังทำงานเหมือนเดิมทุกประการ ไม่ถูก
    unhandled_exception_handler (จับเฉพาะ Exception ที่ไม่มี handler เฉพาะเจาะจงกว่า) แย่งไปจัดการ"""
    resp = client.get("/plo/achievement/cohort?curriculum_id=999999")
    assert resp.status_code == 404
    assert resp.json() == {"detail": "Curriculum not found"}
