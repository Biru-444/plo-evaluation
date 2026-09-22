"""
ทำอะไร : ฟีเจอร์ "นำเข้าหลักสูตร/PLO จาก มคอ.2 ด้วย AI" (Workstream 2) — Phase 1
         (POST /curricula/import-from-mco2) รับไฟล์ .pdf/.docx ส่งให้ Gemini แกะชื่อ/ปีหลักสูตร +
         รายการ PLO ออกมาเป็น JSON ให้ frontend แสดงหน้าตรวจสอบ (ไม่เขียน DB เลย) - Phase 2
         (POST /curricula/import-from-mco2/save) รับผลลัพธ์ที่แอดมินตรวจ/แก้ไขแล้วจากหน้านั้น มาบันทึก
         จริง เลียนแบบแพทเทิร์น Phase 1/2 เดียวกับ app/routes/course_import.py (มคอ.3) ทุกประการ

เชื่อมกับ : Phase 1 เรียก app.services.mco2_import_service ล้วนๆ แล้วเติม existing_curriculum_id/
            existing_plo_codes เองที่นี่ (เช็คจาก DB ตรงๆ ว่ามีหลักสูตรชื่อ+ปีตรงกับที่แกะได้อยู่แล้ว
            หรือไม่ - pure code-level ไม่ใช่ Gemini ตัดสิน) Phase 2 ไม่เรียก service นั้นเลย เขียน
            object (Curriculum/PLO) ตรงๆ ในทรานแซกชันเดียว เลียนแบบแพทเทิร์นเดียวกับ Phase 2 ของ
            course_import.py (db.add -> db.flush() เอา id -> ... -> db.commit() ครั้งเดียวตอนจบ)

ถ้าแก้ : ต่างจาก มคอ.3 ตรงที่ Phase 2 ของ มคอ.2 เป็น upsert โดยตั้งใจ (ตัดสินใจแล้วตาม
         แผนการแก้ไขครั้งใหญ่-PLO-CLO.md Workstream 2) — ถ้า curriculum_id ที่ส่งมาชี้ไปหลักสูตรที่มี
         อยู่แล้ว: PLO ที่ code ตรงกับที่มีอยู่แล้ว = อัปเดต description/category, code ใหม่ = สร้างเพิ่ม
         ไม่มี 409 ปฏิเสธแบบ มคอ.3 - curriculum_id = None ถึงจะสร้างหลักสูตรใหม่ (ทุก PLO ในคำขอเป็น
         "สร้างใหม่" หมด)

         plo.category เป็นคอลัมน์ NOT NULL ในฐานข้อมูล (ดู app/models/plo.py) - ถ้า MCO2PLOItem
         ตัวไหนใน payload มี category = None (Gemini แกะไม่ออก/แอดมินยังไม่ได้แก้ในหน้า Phase 3) ต้อง
         400 ปฏิเสธก่อนแตะ DB เลย ไม่ปล่อยให้ IntegrityError จาก NOT NULL คุมแทน (ข้อความไม่ชัดเท่า)
"""
from __future__ import annotations

from pathlib import PurePosixPath

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from google.genai.errors import APIError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import require_role
from app.database import get_db
from app.models import Curriculum, PLO, User
from app.schemas.curriculum import CurriculumSchema
from app.schemas.curriculum_import import (
    CurriculumImportFromMCO2Response,
    CurriculumImportSaveRequest,
    CurriculumImportSaveResponse,
)
from app.schemas.plo import PLOSchema
from app.services.mco2_import_service import (
    import_curriculum_from_mco2_docx,
    import_curriculum_from_mco2_pdf,
)

router = APIRouter(prefix="/curricula", tags=["Curriculum Import (มคอ.2 AI)"])

ALLOWED_EXTENSIONS = {".pdf", ".docx"}


# เติม existing_curriculum_id/existing_plo_codes เข้าไปใน response ของ Phase 1 ทีหลัง - pure
# code-level เช็คจาก DB ตรงๆ ว่ามีหลักสูตรชื่อ+ปีตรงกับที่ Gemini แกะได้อยู่แล้วหรือไม่ (เทียบ exact
# match ทั้งชื่อและปี - ชื่อหลักสูตรในเอกสารไทยมักคัดลอกตรงตัว ถ้าไม่ตรงเป๊ะแอดมินยังแก้ชื่อ/ปีในหน้า
# Phase 3 เองได้อยู่ดี ไม่ใช่จุดตัดสินใจสุดท้าย)
def _add_existing_curriculum_info(
    db: Session, result: CurriculumImportFromMCO2Response
) -> CurriculumImportFromMCO2Response:
    existing = (
        db.query(Curriculum)
        .filter(Curriculum.name == result.curriculum_name, Curriculum.year == result.curriculum_year)
        .first()
    )
    if existing is not None:
        result.existing_curriculum_id = existing.id
        result.existing_plo_codes = [
            code for (code,) in db.query(PLO.code).filter(PLO.curriculum_id == existing.id).all()
        ]
    return result


@router.post("/import-from-mco2", response_model=CurriculumImportFromMCO2Response)
async def import_curriculum_from_mco2(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    filename = file.filename or ""
    extension = PurePosixPath(filename).suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"รองรับเฉพาะไฟล์ .pdf หรือ .docx เท่านั้น (ไฟล์ที่ส่งมา: {filename or 'ไม่ทราบชื่อไฟล์'})",
        )

    content_bytes = await file.read()
    if not content_bytes:
        raise HTTPException(status_code=400, detail="ไฟล์ว่างเปล่าหรืออ่านไม่ได้")

    try:
        if extension == ".pdf":
            result = import_curriculum_from_mco2_pdf(content_bytes)
        else:
            result = import_curriculum_from_mco2_docx(content_bytes)
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except APIError as exc:
        # google-genai ยิง exception ประเภทนี้เองตอน Gemini API ตอบ error กลับมา (เช่น 503 "high
        # demand", 429 rate limit) - ไม่ใช่ RuntimeError เลยไม่ถูก except ด้านบนจับ ถ้าไม่ดักไว้ตรงนี้
        # exception จะหลุดเป็น 500 ดิบๆ ที่ไม่มี CORS header เบราว์เซอร์เลยรายงานผิดเป็น "CORS policy"
        # แทนที่จะเป็น 500/502 จริง (บั๊กเดียวกันกับ app/routes/course_import.py - แก้คู่กันไว้แล้ว)
        raise HTTPException(status_code=502, detail=f"เรียก Gemini ไม่สำเร็จ: {exc}") from exc

    return _add_existing_curriculum_info(db, result)


@router.post(
    "/import-from-mco2/save", response_model=CurriculumImportSaveResponse, status_code=201
)
def save_curriculum_from_mco2(
    payload: CurriculumImportSaveRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    missing_category_codes = sorted(p.code for p in payload.plos if p.category is None)
    if missing_category_codes:
        raise HTTPException(
            status_code=400,
            detail=f"PLO ต่อไปนี้ยังไม่ได้ระบุหมวดหมู่ (category) กรุณากรอกให้ครบก่อนบันทึก: {missing_category_codes}",
        )

    codes_in_payload = [p.code for p in payload.plos]
    duplicate_codes = sorted({c for c in codes_in_payload if codes_in_payload.count(c) > 1})
    if duplicate_codes:
        raise HTTPException(
            status_code=400,
            detail=f"รหัส PLO ซ้ำกันเองภายในคำขอนี้: {duplicate_codes}",
        )

    if payload.curriculum_id is not None:
        curriculum = db.get(Curriculum, payload.curriculum_id)
        if curriculum is None:
            raise HTTPException(status_code=404, detail="Curriculum not found")
    else:
        curriculum = Curriculum(name=payload.curriculum_name, year=payload.curriculum_year)
        db.add(curriculum)

    try:
        db.flush()  # ต้องมี curriculum.id ก่อนสร้าง/อัปเดต PLO ที่อ้างถึง

        existing_plos = {
            plo.code: plo
            for plo in db.query(PLO).filter(PLO.curriculum_id == curriculum.id).all()
        }

        created_plo_codes: list[str] = []
        updated_plo_codes: list[str] = []
        for plo_item in payload.plos:
            existing = existing_plos.get(plo_item.code)
            if existing is not None:
                existing.description_th = plo_item.description_th
                existing.description_en = plo_item.description_en
                existing.category = plo_item.category
                updated_plo_codes.append(plo_item.code)
            else:
                db.add(
                    PLO(
                        curriculum_id=curriculum.id,
                        code=plo_item.code,
                        description_th=plo_item.description_th,
                        description_en=plo_item.description_en,
                        category=plo_item.category,
                    )
                )
                created_plo_codes.append(plo_item.code)

        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="บันทึกไม่สำเร็จ (ข้อมูลขัดแย้งที่ไม่ได้เช็คไว้ล่วงหน้า)",
        ) from exc

    db.refresh(curriculum)
    plos = db.query(PLO).filter(PLO.curriculum_id == curriculum.id).order_by(PLO.id).all()

    return CurriculumImportSaveResponse(
        curriculum=CurriculumSchema.model_validate(curriculum),
        plos=[PLOSchema.model_validate(p) for p in plos],
        created_plo_codes=created_plo_codes,
        updated_plo_codes=updated_plo_codes,
    )
