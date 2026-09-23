"""
ทำอะไร : CRUD สำหรับ assessment_item (ชิ้นงาน/ข้อสอบ) และ student_score (คะแนนดิบของนักศึกษาแต่ละคน)
         — ข้อมูลดิบที่สุดที่ทุกสูตรคำนวณ CLO/PLO/YLO ในระบบนี้อ่านย้อนขึ้นมาจากตารางเหล่านี้

เชื่อมกับ : create/update assessment_item และ student_score เช็คสิทธิ์ความเป็นเจ้าของวิชาเหมือน clo.py/
            item_clo.py (instructor แก้ได้เฉพาะ offering ที่ตัวเองสอน) — create/update student_score
            เช็คว่าคะแนนที่กรอกไม่เกินคะแนนเต็มของชิ้นงานนั้นเสมอ (400 ถ้าเกิน)

ถ้าแก้ : ไม่มี endpoint ลบ student_score โดยตรง (ลบทางอ้อมได้ผ่านการลบ assessment_item ซึ่ง cascade
         ลบคะแนนที่ผูกอยู่ไปด้วย)
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models import AssessmentItem, CourseOffering, StudentScore, User
from app.routes.enrollment import _require_offering_ownership
from app.schemas import (
    AssessmentCreateSchema,
    AssessmentItemSchema,
    AssessmentItemUpdateSchema,
    StudentScoreCreateSchema,
    StudentScoreDetailSchema,
    StudentScoreSchema,
    StudentScoreUpdateSchema,
)

router = APIRouter(tags=["Assessment"])


# คืนรายการชิ้นงานทั้งหมด กรองตาม offering_id ได้
@router.get("/assessment-items", response_model=list[AssessmentItemSchema])
def list_assessment_items(
    offering_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(AssessmentItem)
    if offering_id is not None:
        query = query.filter(AssessmentItem.offering_id == offering_id)
    return query.order_by(AssessmentItem.id).all()


# คืนชิ้นงานรายตัวตาม id
@router.get("/assessment-items/{item_id}", response_model=AssessmentItemSchema)
def get_assessment_item(
    item_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    item = db.get(AssessmentItem, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Assessment item not found")
    return item


# สร้างชิ้นงานใหม่ — instructor สร้างได้เฉพาะใน offering ที่ตัวเองสอน
@router.post("/assessment-items", response_model=AssessmentItemSchema, status_code=201)
def create_assessment_item(
    payload: AssessmentCreateSchema,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != "admin":
        offering = db.get(CourseOffering, payload.offering_id)
        if offering is None or offering.instructor_id != current_user.id:
            raise HTTPException(status_code=403, detail="คุณไม่ใช่ผู้สอนวิชานี้")

    item = AssessmentItem(**payload.model_dump())
    db.add(item)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Assessment item could not be created (invalid offering?)",
        ) from exc
    db.refresh(item)
    return item


# แก้ไขชิ้นงาน (เช่น เปลี่ยนคะแนนเต็ม) — เช็คสิทธิ์ความเป็นเจ้าของวิชาเช่นเดียวกับตอนสร้าง
@router.put("/assessment-items/{item_id}", response_model=AssessmentItemSchema)
def update_assessment_item(
    item_id: int,
    payload: AssessmentItemUpdateSchema,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    item = db.get(AssessmentItem, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Assessment item not found")
    if current_user.role != "admin":
        offering = db.get(CourseOffering, item.offering_id)
        if offering is None or offering.instructor_id != current_user.id:
            raise HTTPException(status_code=403, detail="คุณไม่ใช่ผู้สอนวิชานี้")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(item, field, value)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409, detail="Assessment item could not be updated"
        ) from exc
    db.refresh(item)
    return item


# ลบชิ้นงาน — เช็คสิทธิ์ความเป็นเจ้าของวิชาเช่นเดียวกับตอนสร้าง
@router.delete("/assessment-items/{item_id}", status_code=204)
def delete_assessment_item(
    item_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    item = db.get(AssessmentItem, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Assessment item not found")
    if current_user.role != "admin":
        offering = db.get(CourseOffering, item.offering_id)
        if offering is None or offering.instructor_id != current_user.id:
            raise HTTPException(status_code=403, detail="คุณไม่ใช่ผู้สอนวิชานี้")
    db.delete(item)  # cascade ลบ item_clo / student_score ที่อ้างถึงด้วย
    db.commit()


# คืนคะแนนของนักศึกษา (ระบุ student_id) หรือของทั้งห้อง (ระบุ offering_id) อย่างใดอย่างหนึ่งต้องมี
# มาอย่างน้อย 1 ตัว (400 ถ้าไม่ระบุเลย) — join กับ AssessmentItem เพื่อแนบชื่อ/คะแนนเต็มมาให้ในตัวเดียว
#
# สิทธิ์ (course-level score data - PDPA) : admin ดูได้ทุกอย่าง — instructor จำกัดตาม offering ที่ตัวเอง
# สอนเท่านั้น 2 กรณี : (1) ระบุ offering_id มา -> เช็คความเป็นเจ้าของตรงๆ (403 ถ้าไม่ใช่เจ้าของ) เหมือน
# endpoint อื่น (2) ระบุแค่ student_id (ไม่มี offering_id) -> คะแนนอาจกระจายอยู่หลาย offering คนละอาจารย์
# กัน ไม่มี "เจ้าของ" เดียวให้ 403 ได้ตรงๆ จึงกรองแถวผลลัพธ์แทน (เหลือเฉพาะ offering ที่ตัวเองสอนจริง) ไม่
# บล็อกทั้ง request - กันหน้า /scores (ค้นหานักศึกษาคนไหนก็ได้) ไม่ให้อาจารย์เห็นคะแนนวิชาที่ตัวเองไม่ได้สอน
# โดยไม่ทำให้ workflow ค้นหา/แก้คะแนนนักศึกษาของตัวเองพังไปด้วย
@router.get("/student-scores", response_model=list[StudentScoreDetailSchema])
def list_student_scores(
    student_id: str | None = Query(None, description="Student ID, e.g. 6500001"),
    offering_id: int | None = Query(None, description="คืนคะแนนของนักศึกษาทุกคนในวิชานี้"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if student_id is None and offering_id is None:
        raise HTTPException(status_code=400, detail="Provide student_id or offering_id")

    if offering_id is not None:
        _require_offering_ownership(db, offering_id, current_user)

    query = db.query(StudentScore).join(AssessmentItem, StudentScore.item_id == AssessmentItem.id)
    if student_id is not None:
        query = query.filter(StudentScore.student_id == student_id)
    if offering_id is not None:
        query = query.filter(AssessmentItem.offering_id == offering_id)
    elif current_user.role != "admin":
        query = query.join(CourseOffering, CourseOffering.id == AssessmentItem.offering_id).filter(
            CourseOffering.instructor_id == current_user.id
        )
    scores = query.order_by(StudentScore.id).all()
    return [
        StudentScoreDetailSchema(
            id=score.id,
            item_id=score.item_id,
            item_name=score.item.name,
            total_score=score.item.total_score,
            student_id=score.student_id,
            score_obtained=score.score_obtained,
        )
        for score in scores
    ]


# บันทึกคะแนนของนักศึกษา 1 คนต่อชิ้นงาน 1 ชิ้น — 400 ถ้าคะแนนเกินคะแนนเต็มของชิ้นงานนั้น 409 ถ้ามี
# คะแนนของคนนี้/ชิ้นงานนี้อยู่แล้ว (ต้องใช้ PUT แก้แทน ไม่ใช่ POST ซ้ำ)
@router.post("/student-scores", response_model=StudentScoreSchema, status_code=201)
def create_student_score(
    payload: StudentScoreCreateSchema,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    item = db.get(AssessmentItem, payload.item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Assessment item not found")
    if payload.score_obtained > item.total_score:
        raise HTTPException(
            status_code=400,
            detail=f"คะแนนที่กรอก ({payload.score_obtained}) เกินคะแนนเต็มของชิ้นงานนี้ (เต็ม {item.total_score})",
        )

    score = StudentScore(**payload.model_dump())
    db.add(score)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Score already exists for this student/item, or references an invalid item/student",
        ) from exc
    db.refresh(score)
    return score


# แก้ไขคะแนนที่บันทึกไว้แล้ว — 400 ถ้าคะแนนใหม่เกินคะแนนเต็มของชิ้นงานนั้นเช่นเดียวกับตอนสร้าง
@router.put("/student-scores/{score_id}", response_model=StudentScoreSchema)
def update_student_score(
    score_id: int,
    payload: StudentScoreUpdateSchema,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    score = db.get(StudentScore, score_id)
    if score is None:
        raise HTTPException(status_code=404, detail="Student score not found")
    if payload.score_obtained > score.item.total_score:
        raise HTTPException(
            status_code=400,
            detail=(
                f"คะแนนที่กรอก ({payload.score_obtained}) เกินคะแนนเต็มของชิ้นงานนี้ "
                f"(เต็ม {score.item.total_score})"
            ),
        )

    score.score_obtained = payload.score_obtained
    db.commit()
    db.refresh(score)
    return score
