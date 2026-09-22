"""
ทำอะไร : Phase 1 ของฟีเจอร์ "นำเข้าข้อมูลวิชาจาก มคอ.3 ด้วย AI" — รับไฟล์ PDF (มคอ.3) + curriculum_id
         ที่แอดมินเลือกไว้ ส่งให้ Gemini แกะข้อมูลวิชา/CLO/CLO-PLO mapping ออกมาเป็น JSON คืนกลับให้
         frontend แสดงหน้าตรวจสอบก่อนเสมอ (Phase 1 นี้ไม่เขียนอะไรลง DB เลย - ดู TASK ต้นทางที่สั่งงานนี้)

เชื่อมกับ : เรียก app.services.mco3_import_service.import_course_from_mco3_pdf ล้วนๆ ไม่มี logic
            เรียก Gemini อยู่ในไฟล์นี้เอง ไฟล์นี้มีหน้าที่แค่รับ request/เช็คสิทธิ์/หา curriculum
            ที่เลือกไว้ (ใช้ชื่อหลักสูตรไปเทียบ curriculum_mismatch ใน service)

ถ้าแก้ : สิทธิ์ตั้งใจให้ admin เท่านั้น (require_role("admin")) เพราะเป็นฟีเจอร์เตรียมนำเข้าข้อมูล
         หลักสูตร/วิชาระดับระบบ - Phase 2 (endpoint บันทึกจริง) และ Phase 3 (หน้าจอ frontend) ยังไม่ทำ
         ในรอบนี้
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.auth import require_role
from app.database import get_db
from app.models import Curriculum, User
from app.schemas.course_import import CourseImportFromMCO3Response
from app.services.mco3_import_service import import_course_from_mco3_pdf

router = APIRouter(prefix="/courses", tags=["Course Import (มคอ.3 AI)"])


@router.post("/import-from-mco3", response_model=CourseImportFromMCO3Response)
async def import_course_from_mco3(
    file: UploadFile = File(...),
    curriculum_id: int = Form(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    curriculum = db.get(Curriculum, curriculum_id)
    if curriculum is None:
        raise HTTPException(status_code=404, detail="Curriculum not found")

    pdf_bytes = await file.read()
    if not pdf_bytes:
        raise HTTPException(status_code=400, detail="ไฟล์ว่างเปล่าหรืออ่านไม่ได้")

    try:
        return import_course_from_mco3_pdf(pdf_bytes, curriculum.name)
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
