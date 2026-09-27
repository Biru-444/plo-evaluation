"""
ทำอะไร : CRUD มาตรฐาน (list/get/create/update/delete) สำหรับตาราง plo (เป้าหมายการเรียนรู้ระดับ
         หลักสูตร) บวก endpoint เสริม course-plan (ดูวิชาบังคับของ PLO นี้ผ่าน course_plo/มคอ.2 -
         ไม่ได้ใช้คำนวณผลบรรลุ PLO แล้ว) และ linked-courses (ดูวิชาที่เชื่อมจริงผ่าน clo_plo_mapping -
         หลักฐานจริงที่ใช้คำนวณ % บรรลุ PLO, เพิ่ม 2026-09) — คนละไฟล์กับ app/routes/plo_calculation.py
         ที่คำนวณ "% บรรลุ" (ไฟล์นี้จัดการแค่ข้อมูล PLO เอง)

เชื่อมกับ : ลบ PLO ที่นี่จะ cascade ลบ ylo_plo_mapping และ course_plo ที่อ้างถึงไปด้วย (ดู
            app/models/plo.py) กระทบทั้งการคำนวณ PLO และ YLO ที่ผูกกับ PLO นี้

ถ้าแก้ : create/update/delete เฉพาะ admin เท่านั้น — list/get/course-plan เปิดให้ทุก role ดูได้
         linked-courses จำกัดแค่ admin/instructor (เหมือน endpoint ผลบรรลุ PLO อื่นๆ) ลำดับการลงทะเบียน
         router นี้ใน app/main.py ต้องมาหลัง plo_calculation.router เสมอ (ดูคอมเมนต์ที่นั่น)
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import get_current_user, require_role
from app.database import get_db
from app.models import CLO, CLOPLOMapping, Course, CoursePLO, PLO
from app.schemas import (
    PLOCoursePlanItemSchema,
    PLOCreateSchema,
    PLOSchema,
    PLOUpdateSchema,
)
from app.schemas.plo import PLOLinkedCourseCLOItemSchema, PLOLinkedCourseItemSchema

router = APIRouter(prefix="/plo", tags=["PLO"])


# คืนรายการ PLO ทั้งหมด กรองตาม curriculum_id ได้
@router.get("", response_model=list[PLOSchema])
def list_plo(
    curriculum_id: int | None = None,
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    query = db.query(PLO)
    if curriculum_id is not None:
        query = query.filter(PLO.curriculum_id == curriculum_id)
    return query.order_by(PLO.id).all()


# คืน PLO รายตัวตาม id
@router.get("/{plo_id}", response_model=PLOSchema)
def get_plo(plo_id: int, db: Session = Depends(get_db), _=Depends(get_current_user)):
    plo = db.get(PLO, plo_id)
    if plo is None:
        raise HTTPException(status_code=404, detail="PLO not found")
    return plo


@router.get("/{plo_id}/course-plan", response_model=list[PLOCoursePlanItemSchema])
def get_plo_course_plan(
    plo_id: int,
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    """วิชาที่ผูกไว้ตอนออกแบบหลักสูตร (Curriculum Mapping, มคอ.2) ผ่าน course_plo - ใช้เกณฑ์เดียวกับ
    ที่ _build_plo_requirements ใน plo_calculation.py ใช้ตัดสินว่าวิชาไหน "เข้าเกณฑ์" ของ PLO ข้อนี้บ้าง

    เฉพาะวิชา responsibility_level='primary' เท่านั้น - วิชา 'secondary' ไม่โชว์ในบล็อกนี้ (สอดคล้องกับ
    _build_plo_requirements ใน plo_calculation.py ที่นับเฉพาะวิชา primary เป็นข้อกำหนดของ PLO เหมือนกัน)"""
    plo = db.get(PLO, plo_id)
    if plo is None:
        raise HTTPException(status_code=404, detail="PLO not found")

    rows = (
        db.query(Course.id, Course.course_code, Course.name_th, CoursePLO.responsibility_level)
        .join(CoursePLO, CoursePLO.course_id == Course.id)
        .filter(CoursePLO.plo_id == plo_id, CoursePLO.responsibility_level == "primary")
        .order_by(Course.course_code)
        .all()
    )
    return [
        PLOCoursePlanItemSchema(
            course_id=r[0], course_code=r[1], name_th=r[2], responsibility_level=r[3]
        )
        for r in rows
    ]


@router.get("/{plo_id}/linked-courses", response_model=list[PLOLinkedCourseItemSchema])
def get_plo_linked_courses(
    plo_id: int,
    db: Session = Depends(get_db),
    _=Depends(require_role("admin", "instructor")),
):
    """รายวิชาที่เชื่อมกับ PLO นี้ผ่าน clo_plo_mapping (CLO↔PLO โดยตรง) - คนละที่มากับ course-plan
    ด้านบน (course_plo/มคอ.2 ซึ่งไม่ได้ใช้คำนวณผลบรรลุ PLO แล้ว - ดู _build_plo_requirements ใน
    plo_achievement_service.py) วิชานี้คือหลักฐานจริงที่ใช้คำนวณ % บรรลุ PLO/"วิชาหลัก" ในหน้าภาพรวม PLO

    1 วิชาอาจมีหลาย CLO ผูกกับ PLO เดียวกัน (เช่น CLO1 และ CLO3 ของวิชาเดียวกันผูกกับ PLO1 ทั้งคู่) - group
    เป็นวิชาเดียวที่มีหลาย CLO ไม่ใช่คนละแถว join ครั้งเดียว (ไม่ query ในลูป) แล้ว group ด้วย Python -
    เรียงวิชาตามรหัสวิชา, เรียง CLO ในแต่ละวิชาตามรหัส CLO (ทั้งคู่มาจาก ORDER BY ของคิวรีอยู่แล้ว
    ไม่ต้อง sort ซ้ำ เพราะ dict ใน Python คงลำดับ insert)

    ไม่กรองซ้ำด้วย curriculum_id เพิ่ม เพราะ plo_id ระบุ PLO ข้อเดียวที่แน่นอนอยู่แล้ว (CLOPLOMapping ที่
    plo_id นี้คือ mapping ของ PLO ข้อนี้เท่านั้นโดยนิยาม)"""
    plo = db.get(PLO, plo_id)
    if plo is None:
        raise HTTPException(status_code=404, detail="PLO not found")

    rows = (
        db.query(
            Course.id,
            Course.course_code,
            Course.name_th,
            Course.credit,
            CLO.id,
            CLO.code,
            CLO.description,
            CLOPLOMapping.weight_percent,
        )
        .join(CLO, CLO.id == CLOPLOMapping.clo_id)
        .join(Course, Course.id == CLO.course_id)
        .filter(CLOPLOMapping.plo_id == plo_id)
        .order_by(Course.course_code, CLO.code)
        .all()
    )

    courses_by_id: dict[int, PLOLinkedCourseItemSchema] = {}
    for course_id, course_code, name_th, credit, clo_id, clo_code, description, weight in rows:
        if course_id not in courses_by_id:
            courses_by_id[course_id] = PLOLinkedCourseItemSchema(
                course_id=course_id,
                course_code=course_code,
                course_name_th=name_th,
                credits=credit,
                clos=[],
            )
        courses_by_id[course_id].clos.append(
            PLOLinkedCourseCLOItemSchema(
                clo_id=clo_id, clo_code=clo_code, description_th=description, weight_percent=weight
            )
        )
    return list(courses_by_id.values())


# สร้าง PLO ใหม่ (admin เท่านั้น) — 409 ถ้ารหัส (code) ซ้ำในหลักสูตรเดียวกัน
@router.post("", response_model=PLOSchema, status_code=201)
def create_plo(
    payload: PLOCreateSchema,
    db: Session = Depends(get_db),
    _=Depends(require_role("admin")),
):
    plo = PLO(**payload.model_dump())
    db.add(plo)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="PLO could not be created (duplicate code?)") from exc
    db.refresh(plo)
    return plo


# แก้ไข PLO (admin เท่านั้น)
@router.put("/{plo_id}", response_model=PLOSchema)
def update_plo(
    plo_id: int,
    payload: PLOUpdateSchema,
    db: Session = Depends(get_db),
    _=Depends(require_role("admin")),
):
    plo = db.get(PLO, plo_id)
    if plo is None:
        raise HTTPException(status_code=404, detail="PLO not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(plo, field, value)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="PLO could not be updated (duplicate code?)") from exc
    db.refresh(plo)
    return plo


# ลบ PLO (admin เท่านั้น)
@router.delete("/{plo_id}", status_code=204)
def delete_plo(plo_id: int, db: Session = Depends(get_db), _=Depends(require_role("admin"))):
    plo = db.get(PLO, plo_id)
    if plo is None:
        raise HTTPException(status_code=404, detail="PLO not found")
    db.delete(plo)  # cascade ลบ ylo_plo_mapping / course_plo ที่อ้างถึงด้วย
    db.commit()
