"""
PLO achievement calculation route.

Calculation (all-or-nothing, confirmed spec - not a continuous blended average):
  1. CLO mastery = weighted average of a student's % score on every assessment
     item that measures that CLO, weighted by item_clo.weight_percent (same
     formula as clo_calculation.py). A CLO the student has no recorded score
     for at all has no mastery value.
  2. A CLO "passes" only if its mastery >= that CLO's own pass_threshold_percent
     (per-CLO, not a global constant). No mastery value = does not pass.
  3. For a given PLO, every course that has at least one CLO mapped to it (via
     clo_plo_mapping) is "required" for that PLO. A student "passes a required
     course for this PLO" only if ALL of that course's CLOs mapped to this PLO
     pass (CLOs of the same course mapped to a *different* PLO are irrelevant
     here) - courses are found globally from clo_plo_mapping, independent of
     whether the student is even enrolled in them.
  4. A student achieves a PLO only if they pass EVERY required course for it.
     A PLO with zero required courses is reported as not achieved (no data to
     judge from, not an automatic pass).
  achieved_percent is 100.0/0.0 (mirrors is_achieved) rather than a partial
  score, since there's no "partially achieved" concept left under this model.
"""
from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models import (
    CLO,
    CLOPLOMapping,
    Course,
    CourseOffering,
    CoursePLO,
    Curriculum,
    Enrollment,
    AssessmentItem,
    ItemCLO,
    PLO,
    Student,
    StudentScore,
    StudyPlan,
    User,
    YLO,
    YLOPLOMapping,
)

router = APIRouter(prefix="/plo", tags=["PLO Achievement"])


class PLOAchievementItem(BaseModel):
    plo_id: int
    plo_code: str
    description: str
    achieved_percent: float
    is_achieved: bool


class StudentPLOAchievement(BaseModel):
    student_id: str
    student_name: str
    curriculum_id: int
    plo_achievements: list[PLOAchievementItem]


class PLOCohortSummaryItem(BaseModel):
    plo_id: int
    plo_code: str
    description: str
    student_count_with_data: int
    average_achieved_percent: float
    achieved_student_count: int
    achieved_rate_percent: float


class CurriculumPLOAchievement(BaseModel):
    curriculum_id: int
    curriculum_name: str
    total_students: int
    plo_summary: list[PLOCohortSummaryItem]
    students: list[StudentPLOAchievement]
    available_cohort_years: list[int] = []
    # สถิติวงแหวน "บรรลุ PLO ครบทุกข้อ" (hero stat หน้า "ภาพรวม PLO") - "ครบทุกข้อ" นับเฉพาะ PLO ที่
    # qualifying_plo_count (ดู _qualifying_plo_ids) ไม่ใช่ total_plo_count ทั้งหมด เพราะ PLO ที่ไม่มี
    # วิชา "หลัก" ที่ผ่านเกณฑ์คำนวณเลยเป็นไปไม่ได้อยู่แล้วโดยดีไซน์ ไม่ควรทำให้วงแหวนนี้ค้างที่ 0% ตลอด
    all_plo_achieved_count: int = 0
    all_plo_achieved_percent: float = 0.0
    qualifying_plo_count: int = 0
    total_plo_count: int = 0


class YearlyPLOSummaryItem(BaseModel):
    plo_id: int
    plo_code: str
    description: str
    is_expected_this_year: bool
    student_count_with_data: int
    average_achieved_percent: float
    achieved_student_count: int
    achieved_rate_percent: float


class YearProgressItem(BaseModel):
    year_level: int
    ylo_description: str
    course_count: int
    plo_summary: list[YearlyPLOSummaryItem]
    students: list[StudentPLOAchievement]


class CurriculumYearProgress(BaseModel):
    curriculum_id: int
    curriculum_name: str
    years: list[YearProgressItem]
    available_cohort_years: list[int] = []


class StudentPLOCourseBreakdownItem(BaseModel):
    course_id: int
    course_code: str
    name_th: str
    passed: bool


def _build_plo_requirements(
    db: Session, curriculum_id: int
) -> tuple[dict[int, dict[int, set[int]]], dict[int, Decimal]]:
    """Per curriculum (not per student - compute once and reuse across every
    student in a cohort, not once per student):
      - plo_requirements[plo_id][course_id] = the set of that course's CLO ids
        that map to that specific PLO (CLOs of the same course mapped to a
        *different* PLO are excluded from that set).
      - clo_pass_thresholds[clo_id] = that CLO's own pass_threshold_percent.
    A course only appears under a PLO here if BOTH: (a) course_plo marks it
    responsibility_level='primary' for that PLO (curriculum-design mapping),
    AND (b) it has at least one CLO actually mapped to that PLO via
    clo_plo_mapping (what an instructor bound while teaching). A course that's
    only 'secondary', or has no course_plo entry at all for this PLO, is not
    required - even if clo_plo_mapping links it (e.g. a co-op/สหกิจศึกษา course
    marked secondary still isn't forced to pass).
    """
    rows = (
        db.query(CLOPLOMapping.plo_id, CLO.course_id, CLOPLOMapping.clo_id, CLO.pass_threshold_percent)
        .join(CLO, CLO.id == CLOPLOMapping.clo_id)
        .join(Course, Course.id == CLO.course_id)
        .join(
            CoursePLO,
            (CoursePLO.course_id == CLO.course_id) & (CoursePLO.plo_id == CLOPLOMapping.plo_id),
        )
        .filter(Course.curriculum_id == curriculum_id, CoursePLO.responsibility_level == "primary")
        .all()
    )
    plo_requirements: dict[int, dict[int, set[int]]] = {}
    clo_pass_thresholds: dict[int, Decimal] = {}
    for plo_id, course_id, clo_id, threshold in rows:
        plo_requirements.setdefault(plo_id, {}).setdefault(course_id, set()).add(clo_id)
        clo_pass_thresholds[clo_id] = threshold
    return plo_requirements, clo_pass_thresholds


def _qualifying_plo_ids(plo_requirements: dict[int, dict[int, set[int]]]) -> set[int]:
    """PLO ที่มีวิชา "หลัก" อย่างน้อย 1 วิชาผ่านเกณฑ์การคำนวณ (คือมี key อยู่ใน plo_requirements เลย -
    _build_plo_requirements ใส่ key เฉพาะ plo_id ที่เจอวิชาที่เข้าเงื่อนไขจริงเท่านั้น) ใช้ตัดสินว่า
    PLO ข้อไหนควรถูกนับเป็นส่วนหนึ่งของ "บรรลุ PLO ครบทุกข้อ" - dynamic ตามข้อมูล course_plo/
    clo_plo_mapping จริงเสมอ ไม่ hardcode รายชื่อ PLO ที่ตัดออก ถ้าข้อมูลเปลี่ยน (เช่นมีคนเติม course_plo
    ให้ PLO ที่เคยไม่มีวิชาเลย) ผลลัพธ์จะเปลี่ยนตามอัตโนมัติโดยไม่ต้องแก้โค้ด"""
    return {plo_id for plo_id, courses in plo_requirements.items() if courses}


def _clo_passed(
    clo_id: int, clo_mastery: dict[int, Decimal], clo_pass_thresholds: dict[int, Decimal]
) -> bool:
    """Passes only if mastery >= this CLO's own pass_threshold_percent. No
    recorded score data for this CLO at all (mastery missing) = does not pass
    (same rule clo_calculation.py uses for its "students_without_data" bucket)."""
    mastery = clo_mastery.get(clo_id)
    if mastery is None:
        return False
    threshold = clo_pass_thresholds.get(clo_id)
    if threshold is None:
        return False
    return mastery >= threshold


def _student_passed_course_for_plo(
    course_clo_ids: set[int], clo_mastery: dict[int, Decimal], clo_pass_thresholds: dict[int, Decimal]
) -> bool:
    """"Passed this course for this PLO" only if every one of that course's
    CLOs mapped to this PLO passes (see docstring on _build_plo_requirements
    for why course_clo_ids is already filtered to just this PLO's CLOs)."""
    return all(_clo_passed(clo_id, clo_mastery, clo_pass_thresholds) for clo_id in course_clo_ids)


def _student_achieved_plo(
    courses_for_plo: dict[int, set[int]] | None,
    clo_mastery: dict[int, Decimal],
    clo_pass_thresholds: dict[int, Decimal],
) -> bool:
    """Achieves the PLO only if every course required for it (globally, from
    clo_plo_mapping) is passed. Zero required courses = not achieved (nothing
    to judge from, not an automatic pass)."""
    if not courses_for_plo:
        return False
    return all(
        _student_passed_course_for_plo(clo_ids, clo_mastery, clo_pass_thresholds)
        for clo_ids in courses_for_plo.values()
    )


def _clo_mastery_for_student(
    db: Session, student_id: str, course_id_filter: set[int] | None = None
) -> dict[int, Decimal]:
    """CLO mastery per CLO the student has been assessed on - weighted average
    of item scores by item_clo.weight_percent (same formula as
    clo_calculation.py). A CLO absent from the returned dict has no recorded
    score data at all (see _clo_passed). course_id_filter, when given, scopes
    to only that student's enrollments in those courses (used by the by-year
    endpoint); omit it to consider every course the student is enrolled in.
    """
    offering_query = db.query(Enrollment.offering_id).filter(Enrollment.student_id == student_id)
    if course_id_filter is not None:
        offering_query = offering_query.join(
            CourseOffering, CourseOffering.id == Enrollment.offering_id
        ).filter(CourseOffering.course_id.in_(course_id_filter))
    offering_ids = [row[0] for row in offering_query.all()]

    item_by_id: dict[int, AssessmentItem] = {}
    score_by_item: dict[int, Decimal] = {}
    item_clos: list[ItemCLO] = []

    if offering_ids:
        items = (
            db.query(AssessmentItem)
            .filter(AssessmentItem.offering_id.in_(offering_ids))
            .all()
        )
        item_by_id = {item.id: item for item in items}

        if item_by_id:
            scores = (
                db.query(StudentScore)
                .filter(
                    StudentScore.student_id == student_id,
                    StudentScore.item_id.in_(item_by_id.keys()),
                )
                .all()
            )
            score_by_item = {s.item_id: s.score_obtained for s in scores}

            item_clos = (
                db.query(ItemCLO).filter(ItemCLO.item_id.in_(item_by_id.keys())).all()
            )

    clo_weighted_sum: dict[int, Decimal] = {}
    clo_weight_total: dict[int, Decimal] = {}
    for ic in item_clos:
        score = score_by_item.get(ic.item_id)
        item = item_by_id.get(ic.item_id)
        if score is None or item is None or item.total_score <= 0:
            continue
        item_percent = (score / item.total_score) * Decimal(100)
        clo_weighted_sum[ic.clo_id] = clo_weighted_sum.get(ic.clo_id, Decimal(0)) + item_percent * ic.weight_percent
        clo_weight_total[ic.clo_id] = clo_weight_total.get(ic.clo_id, Decimal(0)) + ic.weight_percent

    return {
        clo_id: clo_weighted_sum[clo_id] / clo_weight_total[clo_id]
        for clo_id in clo_weighted_sum
        if clo_weight_total[clo_id] > 0
    }


def _clo_mastery_for_students_batch(
    db: Session, student_ids: list[str], course_id_filter: set[int] | None = None
) -> dict[str, dict[int, Decimal]]:
    """เหมือน _clo_mastery_for_student ทุกประการ (สูตร weighted average เดียวกัน) แต่คำนวณให้หลายคน
    พร้อมกันด้วย query ชุดเดียว (ไม่วนเรียก _clo_mastery_for_student ทีละคนในลูป ซึ่งจะเป็น N+1 query
    ถ้า roster มีนักศึกษาเยอะ) - ใช้ตอนต้องได้ CLO mastery ของนักศึกษาทั้ง roster วิชาเดียวกันพร้อมกัน
    (ดู GET /courses/{course_id}/enrolled-students?plo_id=...) คืนค่า {student_id: {clo_id: mastery}}
    ครบทุก student_id ที่ส่งมาเสมอ (dict ว่างถ้าคนนั้นไม่มีข้อมูลเลย ไม่ใช่ key หายไป)"""
    result: dict[str, dict[int, Decimal]] = {sid: {} for sid in student_ids}
    if not student_ids:
        return result

    offering_query = db.query(Enrollment.student_id, Enrollment.offering_id).filter(
        Enrollment.student_id.in_(student_ids)
    )
    if course_id_filter is not None:
        offering_query = offering_query.join(
            CourseOffering, CourseOffering.id == Enrollment.offering_id
        ).filter(CourseOffering.course_id.in_(course_id_filter))
    enrollment_rows = offering_query.all()

    offering_ids_by_student: dict[str, set[int]] = {}
    all_offering_ids: set[int] = set()
    for student_id, offering_id in enrollment_rows:
        offering_ids_by_student.setdefault(student_id, set()).add(offering_id)
        all_offering_ids.add(offering_id)

    if not all_offering_ids:
        return result

    items = db.query(AssessmentItem).filter(AssessmentItem.offering_id.in_(all_offering_ids)).all()
    item_by_id: dict[int, AssessmentItem] = {item.id: item for item in items}
    if not item_by_id:
        return result

    item_clos = db.query(ItemCLO).filter(ItemCLO.item_id.in_(item_by_id.keys())).all()
    scores = (
        db.query(StudentScore)
        .filter(
            StudentScore.student_id.in_(student_ids),
            StudentScore.item_id.in_(item_by_id.keys()),
        )
        .all()
    )
    score_by_student_item: dict[tuple[str, int], Decimal] = {
        (s.student_id, s.item_id): s.score_obtained for s in scores
    }

    for student_id in student_ids:
        enrolled_offering_ids = offering_ids_by_student.get(student_id)
        if not enrolled_offering_ids:
            continue
        clo_weighted_sum: dict[int, Decimal] = {}
        clo_weight_total: dict[int, Decimal] = {}
        for ic in item_clos:
            item = item_by_id.get(ic.item_id)
            if item is None or item.offering_id not in enrolled_offering_ids:
                continue
            score = score_by_student_item.get((student_id, ic.item_id))
            if score is None or item.total_score <= 0:
                continue
            item_percent = (score / item.total_score) * Decimal(100)
            clo_weighted_sum[ic.clo_id] = clo_weighted_sum.get(ic.clo_id, Decimal(0)) + item_percent * ic.weight_percent
            clo_weight_total[ic.clo_id] = clo_weight_total.get(ic.clo_id, Decimal(0)) + ic.weight_percent
        result[student_id] = {
            clo_id: clo_weighted_sum[clo_id] / clo_weight_total[clo_id]
            for clo_id in clo_weighted_sum
            if clo_weight_total[clo_id] > 0
        }
    return result


def _course_plo_mastery_percent(
    clo_mastery: dict[int, Decimal], course_clo_ids: set[int]
) -> Decimal | None:
    """สรุป CLO mastery ของนักศึกษาคนหนึ่งสำหรับวิชาหนึ่ง เทียบกับ PLO ข้อหนึ่ง ให้เป็นตัวเลข % เดียว
    (เฉลี่ยแบบไม่ถ่วงน้ำหนักของ mastery ต่อ CLO ที่มีข้อมูล - course_clo_ids คือ CLO ของวิชานั้นที่ผูกกับ
    PLO ข้อนี้โดยเฉพาะ ตามที่ _build_plo_requirements คำนวณไว้แล้ว) CLO ที่ไม่มีคะแนนเลยถูกข้ามจากค่าเฉลี่ย
    (ไม่นับเป็น 0 - เพราะ "ไม่มีข้อมูล" กับ "ได้ 0%" เป็นคนละความหมาย เหมือนที่ _clo_passed ปฏิบัติ) คืน
    None ถ้าไม่มี CLO ไหนมีข้อมูลเลยสักตัว (ไม่ใช่ course_clo_ids ว่างเปล่า - นั่นแปลว่าวิชานี้ไม่มี CLO
    ผูกกับ PLO นี้จริงๆ ก็ยัง None เหมือนกัน แค่คนละเหตุผล)"""
    available = [clo_mastery[clo_id] for clo_id in course_clo_ids if clo_id in clo_mastery]
    if not available:
        return None
    return sum(available) / len(available)


def _calculate_plo_achievement_for_student(
    db: Session,
    student: Student,
    plo_requirements: dict[int, dict[int, set[int]]],
    clo_pass_thresholds: dict[int, Decimal],
    course_id_filter: set[int] | None = None,
) -> StudentPLOAchievement:
    plos = (
        db.query(PLO)
        .filter(PLO.curriculum_id == student.curriculum_id)
        .order_by(PLO.code)
        .all()
    )

    clo_mastery = _clo_mastery_for_student(db, student.id, course_id_filter)

    # PLO achievement: all-or-nothing across every required course (see
    # _student_achieved_plo) - not a blended average of CLO masteries.
    achievements = []
    for plo in plos:
        achieved = _student_achieved_plo(
            plo_requirements.get(plo.id), clo_mastery, clo_pass_thresholds
        )
        achievements.append(
            PLOAchievementItem(
                plo_id=plo.id,
                plo_code=plo.code,
                description=plo.description_th,
                achieved_percent=100.0 if achieved else 0.0,
                is_achieved=achieved,
            )
        )

    return StudentPLOAchievement(
        student_id=student.id,
        student_name=f"{student.first_name} {student.last_name}",
        curriculum_id=student.curriculum_id,
        plo_achievements=achievements,
    )


def _aggregate_plo_percent_stats(
    student_achievements: list[StudentPLOAchievement],
) -> tuple[dict[int, Decimal], dict[int, int], dict[int, int]]:
    """Sum achieved_percent, and count students with data / who achieved, per PLO.

    Shared by /achievement/cohort and /achievement/by-year so the cohort-level
    averaging logic exists in exactly one place.
    """
    percent_sum_by_plo: dict[int, Decimal] = {}
    # achieved_percent is now always 100.0 or 0.0 (see module docstring), so
    # count_with_data_by_plo below is really just achieved_count_by_plo again -
    # kept as-is since nothing in the frontend reads student_count_with_data
    # (the field it feeds) and this function isn't the place to drop it.
    count_with_data_by_plo: dict[int, int] = {}
    achieved_count_by_plo: dict[int, int] = {}

    for achievement in student_achievements:
        for item in achievement.plo_achievements:
            percent_sum_by_plo[item.plo_id] = (
                percent_sum_by_plo.get(item.plo_id, Decimal(0)) + Decimal(str(item.achieved_percent))
            )
            if item.achieved_percent > 0:
                count_with_data_by_plo[item.plo_id] = count_with_data_by_plo.get(item.plo_id, 0) + 1
            if item.is_achieved:
                achieved_count_by_plo[item.plo_id] = achieved_count_by_plo.get(item.plo_id, 0) + 1

    return percent_sum_by_plo, count_with_data_by_plo, achieved_count_by_plo


def _count_all_qualifying_plo_achieved(
    student_achievements: list[StudentPLOAchievement], qualifying_plo_ids: set[int]
) -> int:
    """จำนวนนักศึกษาที่บรรลุ PLO ครบทุกข้อใน qualifying_plo_ids (ไม่ใช่ครบทุก PLO ในหลักสูตรเสมอไป -
    ดู _qualifying_plo_ids) - PLO ที่ไม่มีวิชา "หลัก" ผ่านเกณฑ์เลยไม่ถูกนับ เพราะเป็นไปไม่ได้อยู่แล้ว
    โดยดีไซน์ ไม่ควรทำให้ไม่มีใครนับว่า "บรรลุครบ" เลยสักคน หา 0 qualifying PLO = ไม่มีใครบรรลุครบได้
    (edge case ที่ไม่ควรเกิดในทางปฏิบัติ แต่คืน 0 อย่างปลอดภัยแทนการหารด้วยศูนย์/พังตอนไม่มี PLO เข้าเกณฑ์เลย)"""
    if not qualifying_plo_ids:
        return 0
    count = 0
    for achievement in student_achievements:
        if all(
            item.is_achieved
            for item in achievement.plo_achievements
            if item.plo_id in qualifying_plo_ids
        ):
            count += 1
    return count


@router.get("/achievement", response_model=StudentPLOAchievement)
def get_plo_achievement(
    student_id: str = Query(..., description="Student ID, e.g. 6500001"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    student = db.get(Student, student_id)
    if student is None:
        raise HTTPException(status_code=404, detail="Student not found")

    plo_requirements, clo_pass_thresholds = _build_plo_requirements(db, student.curriculum_id)
    return _calculate_plo_achievement_for_student(db, student, plo_requirements, clo_pass_thresholds)


@router.get(
    "/{plo_id}/students/{student_id}/course-breakdown",
    response_model=list[StudentPLOCourseBreakdownItem],
)
def get_student_plo_course_breakdown(
    plo_id: int,
    student_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """วิชาทั้งหมดที่เกี่ยวข้องกับ PLO ข้อนี้ (จาก clo_plo_mapping) พร้อมสถานะผ่าน/ไม่ผ่านของนักศึกษา
    คนนี้โดยเฉพาะต่อวิชา - เรียก _build_plo_requirements และ _student_passed_course_for_plo ตัวเดียวกับ
    ที่ตัดสิน "% บรรลุ PLO" ทุกที่ในไฟล์นี้ ไม่มี logic คำนวณแยกที่อาจ drift ไม่ตรงกัน"""
    plo = db.get(PLO, plo_id)
    if plo is None:
        raise HTTPException(status_code=404, detail="PLO not found")
    student = db.get(Student, student_id)
    if student is None:
        raise HTTPException(status_code=404, detail="Student not found")

    plo_requirements, clo_pass_thresholds = _build_plo_requirements(db, student.curriculum_id)
    courses_for_plo = plo_requirements.get(plo_id)
    if not courses_for_plo:
        return []

    clo_mastery = _clo_mastery_for_student(db, student.id)

    courses = db.query(Course).filter(Course.id.in_(courses_for_plo.keys())).all()
    course_by_id = {c.id: c for c in courses}

    breakdown = []
    for course_id, clo_ids in courses_for_plo.items():
        course = course_by_id.get(course_id)
        if course is None:
            continue
        breakdown.append(
            StudentPLOCourseBreakdownItem(
                course_id=course_id,
                course_code=course.course_code,
                name_th=course.name_th,
                passed=_student_passed_course_for_plo(clo_ids, clo_mastery, clo_pass_thresholds),
            )
        )
    breakdown.sort(key=lambda c: c.course_code)
    return breakdown


@router.get("/achievement/cohort", response_model=CurriculumPLOAchievement)
def get_cohort_plo_achievement(
    curriculum_id: int = Query(..., description="Curriculum ID"),
    cohort_year: int | None = Query(None, description="กรองเฉพาะรุ่นที่เข้าเรียนปีนี้ (เช่น 66) - ไม่ใส่ = รวมทุกรุ่น"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    curriculum = db.get(Curriculum, curriculum_id)
    if curriculum is None:
        raise HTTPException(status_code=404, detail="Curriculum not found")

    plos = (
        db.query(PLO)
        .filter(PLO.curriculum_id == curriculum_id)
        .order_by(PLO.code)
        .all()
    )

    plo_requirements, clo_pass_thresholds = _build_plo_requirements(db, curriculum_id)
    qualifying_plo_ids = _qualifying_plo_ids(plo_requirements)

    available_cohort_years = sorted(
        {
            row[0]
            for row in db.query(Student.cohort_year)
            .filter(Student.curriculum_id == curriculum_id, Student.cohort_year.isnot(None))
            .distinct()
            .all()
        }
    )

    students_query = db.query(Student).filter(Student.curriculum_id == curriculum_id)
    if cohort_year is not None:
        students_query = students_query.filter(Student.cohort_year == cohort_year)
    students = students_query.all()

    if not students:
        return CurriculumPLOAchievement(
            curriculum_id=curriculum.id,
            curriculum_name=curriculum.name,
            total_students=0,
            plo_summary=[
                PLOCohortSummaryItem(
                    plo_id=plo.id,
                    plo_code=plo.code,
                    description=plo.description_th,
                    student_count_with_data=0,
                    average_achieved_percent=0.0,
                    achieved_student_count=0,
                    achieved_rate_percent=0.0,
                )
                for plo in plos
            ],
            students=[],
            available_cohort_years=available_cohort_years,
            qualifying_plo_count=len(qualifying_plo_ids),
            total_plo_count=len(plos),
        )

    student_achievements = [
        _calculate_plo_achievement_for_student(db, student, plo_requirements, clo_pass_thresholds)
        for student in students
    ]
    students_sorted = sorted(
        student_achievements, key=lambda sa: (sa.student_name, sa.student_id)
    )

    total_students = len(students)
    percent_sum_by_plo, count_with_data_by_plo, achieved_count_by_plo = _aggregate_plo_percent_stats(
        student_achievements
    )

    plo_summary = []
    for plo in plos:
        percent_sum = percent_sum_by_plo.get(plo.id, Decimal(0))
        achieved_count = achieved_count_by_plo.get(plo.id, 0)

        average_achieved_percent = (percent_sum / Decimal(total_students)).quantize(Decimal("0.1"))
        achieved_rate_percent = (
            Decimal(achieved_count) / Decimal(total_students) * Decimal(100)
        ).quantize(Decimal("0.1"))

        plo_summary.append(
            PLOCohortSummaryItem(
                plo_id=plo.id,
                plo_code=plo.code,
                description=plo.description_th,
                student_count_with_data=count_with_data_by_plo.get(plo.id, 0),
                average_achieved_percent=float(average_achieved_percent),
                achieved_student_count=achieved_count,
                achieved_rate_percent=float(achieved_rate_percent),
            )
        )

    all_plo_achieved_count = _count_all_qualifying_plo_achieved(student_achievements, qualifying_plo_ids)
    all_plo_achieved_percent = (
        Decimal(all_plo_achieved_count) / Decimal(total_students) * Decimal(100)
    ).quantize(Decimal("0.1"))

    return CurriculumPLOAchievement(
        curriculum_id=curriculum.id,
        curriculum_name=curriculum.name,
        total_students=total_students,
        plo_summary=plo_summary,
        students=students_sorted,
        available_cohort_years=available_cohort_years,
        all_plo_achieved_count=all_plo_achieved_count,
        all_plo_achieved_percent=float(all_plo_achieved_percent),
        qualifying_plo_count=len(qualifying_plo_ids),
        total_plo_count=len(plos),
    )


@router.get("/achievement/by-year", response_model=CurriculumYearProgress)
def get_plo_achievement_by_year(
    curriculum_id: int = Query(..., description="Curriculum ID"),
    cohort_year: int | None = Query(None, description="กรองเฉพาะรุ่นที่เข้าเรียนปีนี้ (เช่น 66) - ไม่ใส่ = รวมทุกรุ่น"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Same all-or-nothing PLO calculation as /achievement/cohort, but run once
    per year_level (1-4) with only that year's study_plan courses counted for
    the student's score data - so each year reflects what was taught that
    year, not a cumulative total. Also flags which PLOs that year's YLO
    expects. Note: which courses are *required* for a PLO (plo_requirements)
    is still the curriculum-global set, not year-scoped - a PLO whose required
    courses span multiple years will therefore show as not-achieved in any
    single year's slice unless every one of those courses happens to fall in
    that year. This endpoint's achievement numbers aren't rendered anywhere in
    the UI currently (only course_count per year is), so this is a documented
    quirk rather than something worth adding extra complexity to fix."""
    curriculum = db.get(Curriculum, curriculum_id)
    if curriculum is None:
        raise HTTPException(status_code=404, detail="Curriculum not found")

    plos = db.query(PLO).filter(PLO.curriculum_id == curriculum_id).order_by(PLO.code).all()

    plo_requirements, clo_pass_thresholds = _build_plo_requirements(db, curriculum_id)

    available_cohort_years = sorted(
        {
            row[0]
            for row in db.query(Student.cohort_year)
            .filter(Student.curriculum_id == curriculum_id, Student.cohort_year.isnot(None))
            .distinct()
            .all()
        }
    )

    students_query = db.query(Student).filter(Student.curriculum_id == curriculum_id)
    if cohort_year is not None:
        students_query = students_query.filter(Student.cohort_year == cohort_year)
    students = students_query.all()
    total_students = len(students)

    ylo_by_year = {
        ylo.year_level: ylo
        for ylo in db.query(YLO).filter(YLO.curriculum_id == curriculum_id).all()
    }

    years: list[YearProgressItem] = []
    for year_level in (1, 2, 3, 4):
        ylo = ylo_by_year.get(year_level)
        ylo_description = ylo.description if ylo is not None else ""

        expected_plo_ids: set[int] = set()
        if ylo is not None:
            expected_plo_ids = {
                row[0]
                for row in db.query(YLOPLOMapping.plo_id)
                .filter(YLOPLOMapping.ylo_id == ylo.id)
                .all()
            }

        course_ids = {
            row[0]
            for row in db.query(StudyPlan.course_id)
            .filter(
                StudyPlan.curriculum_id == curriculum_id,
                StudyPlan.year_level == year_level,
                StudyPlan.cohort_year.is_(None),
            )
            .all()
        }

        if total_students == 0:
            years.append(
                YearProgressItem(
                    year_level=year_level,
                    ylo_description=ylo_description,
                    course_count=len(course_ids),
                    plo_summary=[
                        YearlyPLOSummaryItem(
                            plo_id=plo.id,
                            plo_code=plo.code,
                            description=plo.description_th,
                            is_expected_this_year=plo.id in expected_plo_ids,
                            student_count_with_data=0,
                            average_achieved_percent=0.0,
                            achieved_student_count=0,
                            achieved_rate_percent=0.0,
                        )
                        for plo in plos
                    ],
                    students=[],
                )
            )
            continue

        student_achievements = [
            _calculate_plo_achievement_for_student(
                db, student, plo_requirements, clo_pass_thresholds, course_id_filter=course_ids
            )
            for student in students
        ]
        students_sorted = sorted(
            student_achievements, key=lambda sa: (sa.student_name, sa.student_id)
        )

        percent_sum_by_plo, count_with_data_by_plo, achieved_count_by_plo = _aggregate_plo_percent_stats(
            student_achievements
        )

        plo_summary = []
        for plo in plos:
            percent_sum = percent_sum_by_plo.get(plo.id, Decimal(0))
            achieved_count = achieved_count_by_plo.get(plo.id, 0)

            average_achieved_percent = (percent_sum / Decimal(total_students)).quantize(Decimal("0.1"))
            achieved_rate_percent = (
                Decimal(achieved_count) / Decimal(total_students) * Decimal(100)
            ).quantize(Decimal("0.1"))

            plo_summary.append(
                YearlyPLOSummaryItem(
                    plo_id=plo.id,
                    plo_code=plo.code,
                    description=plo.description_th,
                    is_expected_this_year=plo.id in expected_plo_ids,
                    student_count_with_data=count_with_data_by_plo.get(plo.id, 0),
                    average_achieved_percent=float(average_achieved_percent),
                    achieved_student_count=achieved_count,
                    achieved_rate_percent=float(achieved_rate_percent),
                )
            )

        years.append(
            YearProgressItem(
                year_level=year_level,
                ylo_description=ylo_description,
                course_count=len(course_ids),
                plo_summary=plo_summary,
                students=students_sorted,
            )
        )

    return CurriculumYearProgress(
        curriculum_id=curriculum.id,
        curriculum_name=curriculum.name,
        years=years,
        available_cohort_years=available_cohort_years,
    )
