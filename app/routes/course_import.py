"""
ทำอะไร : ฟีเจอร์ "นำเข้าข้อมูลวิชาจาก มคอ.3 ด้วย AI" — Phase 1 (POST /courses/import-from-mco3) รับ
         ไฟล์ .pdf/.docx + curriculum_id ส่งให้ Gemini แกะข้อมูลวิชา/CLO/CLO-PLO mapping ออกมาเป็น
         JSON ให้ frontend แสดงหน้าตรวจสอบ (ไม่เขียน DB เลย) - Phase 2 (POST
         /courses/import-from-mco3/save) รับผลลัพธ์ที่แอดมินตรวจ/แก้ไขแล้วจากหน้านั้น มาบันทึกจริง
         เป็น Course + CLO + CLOPLOMapping + StudyPlan 1 แถว (ไม่เรียก Gemini ซ้ำ ไม่แตะไฟล์ต้นฉบับอีกแล้ว)

เชื่อมกับ : Phase 1 เรียก app.services.mco3_import_service ล้วนๆ ไม่มี logic เรียก Gemini/แกะไฟล์อยู่
            ในไฟล์นี้เอง - หลัง Gemini ตอบกลับมาแล้ว _add_domain_category_mismatch_flags() เติม flag
            "domain_category_mismatch" ต่อท้าย flags ให้เอง (pure code-level เทียบ clo.domain กับ
            plo.category จริงจาก DB ผ่าน app.services.domain_category_check - Gemini ไม่ตัดสินเรื่องนี้
            เลย ดู Workstream 4 ใน แผนการแก้ไขครั้งใหญ่-PLO-CLO.md) - Phase 2 ไม่เรียก service นั้นเลย
            เขียน object (Course/CLO/CLOPLOMapping/StudyPlan) ตรงๆ ในทรานแซกชันเดียว เลียนแบบแพทเทิร์น
            เดียวกับ create_clo ใน app/routes/clo.py (db.add course -> db.flush() เอา id -> db.add CLO
            ทีละตัว -> db.flush() เอา id -> db.add CLOPLOMapping -> db.add StudyPlan -> db.commit()
            ครั้งเดียวตอนจบ) เพื่อให้ atomic จริง (พังตรงไหนก็ rollback หมดทั้งก้อน ไม่ทิ้ง course ที่ไม่มี
            CLO/แผนการศึกษาค้างไว้)

ถ้าแก้ : สิทธิ์ทั้งสอง endpoint ตั้งใจให้ admin เท่านั้น (require_role("admin")) เพราะเป็นฟีเจอร์เตรียม
         นำเข้าข้อมูลหลักสูตร/วิชาระดับระบบ ไม่ใช่งานแก้ไขวิชาที่ตัวเองสอนแบบ create_clo ทั่วไป (course
         ที่เพิ่ง import ยังไม่มี course_offering ให้เช็ค ownership ด้วยซ้ำ)

         Phase 2 เป็น create-only โดยตั้งใจ (ตัดสินใจแล้ว 2026-09-22) - รหัสวิชาชนกับที่มีอยู่แล้วใน
         หลักสูตร = 409 ตรงๆ ไม่มี update/merge mode ให้แอดมินไปแก้ผ่านหน้าจัดการวิชาปกติแทน ถ้าต้องการ
         update-mode ในอนาคตต้องออกแบบแยกต่างหาก (มีนัยเรื่อง CLO ที่มีอยู่แล้วบางส่วน vs ใหม่ทั้งหมด)

         flags[]/instructor_name/semester_display (ข้อความดิบ) ของ Phase 1 ไม่ถูกส่งมาที่นี่เลย (ไม่มีใน
         สคีมา CourseImportSaveRequest) เพราะไม่ต้องเก็บเป็น audit trail และไม่มีคอลัมน์ปลายทางให้เก็บ -
         ทิ้งได้เลยหลังแอดมินตรวจในหน้า Phase 3 เสร็จ (semester_display ถูกเดาแยกเป็น
         year_level/semester ฝั่ง frontend ก่อนถึงจะส่งมาที่นี่ - ดู module docstring ของ
         app/schemas/course_import.py - สองตัวเลขนั้นเก็บจริงผ่าน study_plan ที่นี่ ส่วนข้อความดิบเองยัง
         ไม่มีที่เก็บเหมือนเดิม)

         เพิ่มนามสกุลไฟล์ใหม่ที่ Phase 1 รองรับ ต้องเพิ่มใน ALLOWED_EXTENSIONS ด้วย ไม่งั้นโดน 400
         ปฏิเสธตั้งแต่ต้น

         weight_percent ของแต่ละคู่ CLO-PLO (Workstream 3) เป็นหน้าที่ของ frontend ล้วนๆ (auto-fill
         เกลี่ยเท่ากันเอง + ให้แอดมินแก้มือได้ก่อนกด "ยืนยันบันทึก" - ดู AdminCourseImportMCO3.jsx) Phase
         1/Gemini ไม่รู้จัก field นี้เลย (ดู MCO3CLOPLOMappingItem vs MCO3CLOPLOMappingSaveItem ใน
         app/schemas/course_import.py - คนละ schema กัน) Phase 2 ที่นี่แค่รับค่าที่ frontend คำนวณมาแล้ว
         ส่งต่อเข้า CLOPLOMapping ตรงๆ ไม่มีการ auto-fill/rebalance เพิ่มอีกชั้น

         study_plan ที่สร้างที่นี่เป็นแผนมาตรฐานเสมอ (cohort_year=NULL) เพราะ มคอ.3 ไม่มีแนวคิด "รุ่น
         นักศึกษา" อยู่แล้ว (เป็นเอกสารระดับวิชา ไม่ใช่ระดับรุ่น) ถ้าแอดมินต้องการแผนเฉพาะรุ่นทีหลัง ต้อง
         ไปเพิ่มเองผ่านหน้าจัดการ study_plan ปกติแยกต่างหาก
"""
from __future__ import annotations

from pathlib import PurePosixPath

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from google.genai.errors import APIError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import require_role
from app.database import get_db
from app.models import CLO, CLOPLOMapping, Course, Curriculum, PLO, StudyPlan, User
from app.schemas.clo import CLOSchema
from app.schemas.course import CourseSchema
from app.schemas.course_import import (
    CourseImportFromMCO3Response,
    CourseImportSaveRequest,
    CourseImportSaveResponse,
    MCO3ImportFlag,
)
from app.schemas.study_plan import StudyPlanSchema
from app.services.domain_category_check import check_domain_category_mismatch
from app.services.mco3_import_service import (
    import_course_from_mco3_docx,
    import_course_from_mco3_pdf,
)

router = APIRouter(prefix="/courses", tags=["Course Import (มคอ.3 AI)"])

ALLOWED_EXTENSIONS = {".pdf", ".docx"}


# เติม flag "domain_category_mismatch" เข้าไปใน response ของ Phase 1 ทีหลัง - pure code-level เทียบ
# clo.domain ที่ Gemini แกะได้ กับ plo.category จริงของหลักสูตรนี้ (ดึงจาก DB ตรงๆ ไม่ใช่ให้ Gemini เดา)
# ไม่แก้ clos/clo_plo_mapping เลย แค่ต่อท้าย flags (Workstream 4)
def _add_domain_category_mismatch_flags(
    db: Session, curriculum_id: int, result: CourseImportFromMCO3Response
) -> CourseImportFromMCO3Response:
    plo_category_by_code: dict[str, str] = dict(
        db.query(PLO.code, PLO.category).filter(PLO.curriculum_id == curriculum_id).all()
    )
    clo_domain_by_code = {clo.code: clo.domain for clo in result.clos}

    for mapping in result.clo_plo_mapping:
        clo_domain = clo_domain_by_code.get(mapping.clo_code)
        plo_category = plo_category_by_code.get(mapping.plo_code)
        message = check_domain_category_mismatch(clo_domain, plo_category)
        if message:
            result.flags.append(
                MCO3ImportFlag(
                    type="domain_category_mismatch",
                    message=f"{mapping.clo_code} → {mapping.plo_code}: {message}",
                )
            )
    return result


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
            result = import_course_from_mco3_pdf(content_bytes, curriculum.name)
        else:
            result = import_course_from_mco3_docx(content_bytes, curriculum.name)
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except APIError as exc:
        # google-genai ยิง exception ประเภทนี้เองตอน Gemini API ตอบ error กลับมา (เช่น 503 "high
        # demand", 429 rate limit) - ไม่ใช่ RuntimeError เลยไม่ถูก except ด้านบนจับ ถ้าไม่ดักไว้ตรงนี้
        # exception จะหลุดเป็น 500 ดิบๆ ที่ไม่มี CORS header (Starlette ไม่ใส่ header ตอน unhandled
        # exception) เบราว์เซอร์เลยรายงานผิดเป็น "CORS policy" แทนที่จะเป็น 500/502 จริง (พบจริงตอน
        # ทดสอบ Workstream 2 ที่ใช้ pattern เดียวกันนี้ - ดู แผนการแก้ไขครั้งใหญ่-PLO-CLO.md)
        raise HTTPException(status_code=502, detail=f"เรียก Gemini ไม่สำเร็จ: {exc}") from exc

    return _add_domain_category_mismatch_flags(db, curriculum_id, result)


@router.post("/import-from-mco3/save", response_model=CourseImportSaveResponse, status_code=201)
def save_course_from_mco3(
    payload: CourseImportSaveRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    curriculum = db.get(Curriculum, payload.curriculum_id)
    if curriculum is None:
        raise HTTPException(status_code=404, detail="Curriculum not found")

    # create-only โดยตั้งใจ (ไม่มี update/merge mode ในรอบนี้ - ดู module docstring) เช็คก่อนแตะ DB
    # เพื่อให้ข้อความ error ชัดกว่าปล่อยให้ IntegrityError คุมแทน (บอก course_id ที่ชนได้ตรงๆ)
    existing_course = (
        db.query(Course)
        .filter(Course.curriculum_id == payload.curriculum_id, Course.course_code == payload.course_code)
        .first()
    )
    if existing_course is not None:
        raise HTTPException(
            status_code=409,
            detail=(
                f"รหัสวิชา {payload.course_code} มีอยู่แล้วในหลักสูตรนี้ "
                f"(course_id={existing_course.id}) - กรุณาแก้ไขผ่านหน้าจัดการวิชาแทน"
            ),
        )

    # ตรวจ reference ของ clo_plo_mapping ก่อนแตะ DB เช่นกัน (400 ชัดเจนแทน IntegrityError คลุมเครือ) -
    # clo_code ต้องอยู่ใน clos ของ payload นี้เอง, plo_code ต้องมีอยู่จริงในหลักสูตรเป้าหมาย
    clo_codes_in_payload = {clo_item.code for clo_item in payload.clos}
    unknown_clo_refs = sorted(
        {m.clo_code for m in payload.clo_plo_mapping if m.clo_code not in clo_codes_in_payload}
    )
    if unknown_clo_refs:
        raise HTTPException(
            status_code=400,
            detail=f"clo_plo_mapping อ้างถึง clo_code ที่ไม่มีอยู่ใน clos ของคำขอนี้: {unknown_clo_refs}",
        )

    plo_id_by_code: dict[str, int] = dict(
        db.query(PLO.code, PLO.id).filter(PLO.curriculum_id == payload.curriculum_id).all()
    )
    unknown_plo_refs = sorted(
        {m.plo_code for m in payload.clo_plo_mapping if m.plo_code not in plo_id_by_code}
    )
    if unknown_plo_refs:
        raise HTTPException(
            status_code=400,
            detail=f"clo_plo_mapping อ้างถึง plo_code ที่ไม่มีอยู่ในหลักสูตรนี้: {unknown_plo_refs}",
        )

    # ทุกอย่างตั้งแต่ course ถึง commit อยู่ใน try เดียวกัน - db.flush() (ใช้เอา id ที่ถูก generate มา
    # อ้างอิงต่อ ก่อนจะ commit จริง) ก็ยิง SQL ไป DB จริงและ raise IntegrityError ได้ทันทีเหมือนกัน ไม่ใช่
    # แค่ db.commit() ท้ายสุด - ถ้า except ครอบแค่ commit() เฉยๆ error จาก flush() ระหว่างทางจะหลุดออกไป
    # เป็น 500 ที่ไม่ได้ rollback ให้สะอาด (พบจริงตอนเขียน test_save_is_atomic_nothing_persists_when_
    # clo_codes_collide_within_payload - CLO รหัสซ้ำกันเองในคำขอชนกันตอน flush ตัวที่สอง ไม่ใช่ตอน commit)
    try:
        course = Course(
            curriculum_id=payload.curriculum_id,
            course_code=payload.course_code,
            name_th=payload.name_th,
            name_en=payload.name_en,
            credit=payload.credit,
            category=payload.category,
        )
        db.add(course)
        db.flush()  # ต้องมี course.id ก่อนสร้าง CLO ที่อ้างถึง

        clo_id_by_code: dict[str, int] = {}
        for clo_item in payload.clos:
            clo = CLO(
                course_id=course.id,
                code=clo_item.code,
                description=clo_item.description,
                domain=clo_item.domain,
                created_by=current_user.id,
            )
            db.add(clo)
            db.flush()  # ต้องมี clo.id ก่อนสร้างแถว clo_plo_mapping ที่อ้างถึง
            clo_id_by_code[clo_item.code] = clo.id

        for mapping in payload.clo_plo_mapping:
            db.add(
                CLOPLOMapping(
                    clo_id=clo_id_by_code[mapping.clo_code],
                    plo_id=plo_id_by_code[mapping.plo_code],
                    weight_percent=mapping.weight_percent,
                )
            )

        # แผนมาตรฐาน (cohort_year=NULL) เสมอ - มคอ.3 เป็นเอกสารระดับวิชา ไม่มีแนวคิด "รุ่นนักศึกษา" ให้
        # อ้างอิง (ดู module docstring) course เพิ่งสร้างในทรานแซกชันนี้เอง ไม่มีทางชน
        # UniqueConstraint(curriculum_id, course_id, cohort_year) เดิมอยู่แล้ว ไม่ต้องเช็คซ้ำก่อน
        study_plan = StudyPlan(
            curriculum_id=payload.curriculum_id,
            course_id=course.id,
            cohort_year=None,
            year_level=payload.year_level,
            semester=payload.semester,
        )
        db.add(study_plan)

        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="บันทึกไม่สำเร็จ (อาจมีรหัส CLO ซ้ำกันภายในวิชานี้ หรือข้อมูลขัดแย้งอื่นที่ไม่ได้เช็คไว้ล่วงหน้า)",
        ) from exc

    db.refresh(course)
    db.refresh(study_plan)
    clos = db.query(CLO).filter(CLO.course_id == course.id).order_by(CLO.id).all()

    return CourseImportSaveResponse(
        course=CourseSchema.model_validate(course),
        study_plan=StudyPlanSchema.model_validate(study_plan),
        clos=[CLOSchema.model_validate(c) for c in clos],
    )
