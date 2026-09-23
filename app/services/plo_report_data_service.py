"""
ทำอะไร : เตรียม "ข้อมูลพร้อมแสดงผล" สำหรับ export รายงานภาพรวม PLO ↔ รายวิชาของหลักสูตรเดียวเป็น Excel
         (plo_report_export_service.py) - ไม่ยึดตามแบบฟอร์มราชการใดๆ (แนวทางเดียวกับ
         clo_report_data_service.py) ตอบ 3 คำถามหลักของ AUN-QA : PLO ถูกออกแบบให้สอน/วัดที่ไหน (แผนที่
         หลักสูตร), นักศึกษาบรรลุ PLO กี่เปอร์เซ็นต์ (สรุปการบรรลุ), ตัวเลขมาจาก CLO/วิชาไหนน้ำหนักเท่าไร
         (ย้อนรอยการคำนวณ)

เชื่อมกับ : ทุกฟังก์ชัน compute_*() ที่นี่ไม่แตะ openpyxl เลย คืนแค่ dataclass ธรรมดา - ตัวสูตรคำนวณ PLO
            จริง (mastery/PLO_x/threshold) ยังอยู่ที่ app/services/plo_achievement_service.py เหมือนเดิม
            (ไม่แตะ) ที่นี่แค่เรียก compute_cohort_plo_achievement() (ผลลัพธ์เดียวกับ
            GET /plo/achievement/cohort) แล้วต่อยอดจัดรูปแบบ/ผูกกับ curriculum mapping
            (course_plo/clo_plo_mapping/study_plan) สำหรับ export - หมายเหตุตัวหารสำคัญ : average/
            achieved_rate หลักในสรุปการบรรลุ PLO หารด้วย**นักศึกษาทั้งหมด**เหมือน endpoint เดิมทุกประการ
            (คนละพฤติกรรมกับ CLO report ที่หารด้วยผู้มีข้อมูล) ห้ามเปลี่ยน - ดู compute_plo_summary_rows

ถ้าแก้ : ถ้าเพิ่ม field ใหม่ที่ต้องโชว์ในรายงาน ให้เพิ่มที่นี่แล้วให้ plo_report_export_service.py ดึงไปใช้
         ไม่ใช่คำนวณแทรกตรงจุดวาด cell เอง (กันข้อมูล/ตรรกะกระจายหลายที่) ห้ามแก้สูตร/เกณฑ์การคำนวณ PLO
         ในไฟล์นี้ (นั่นคืองานของ plo_achievement_service.py)
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models import CLO, CLOPLOMapping, Course, CoursePLO, Curriculum, PLO, Student, StudyPlan
from app.schemas.plo_calculation import CurriculumPLOAchievement
from app.services.plo_achievement_service import (
    PLO_ACHIEVEMENT_THRESHOLD_PERCENT,
    _build_plo_requirements,
    _clo_mastery_for_students_batch,
    _qualifying_plo_ids,
    compute_cohort_plo_achievement,
)


def _thai_datetime_str(dt: datetime) -> str:
    return f"{dt.day:02d}/{dt.month:02d}/{dt.year + 543} {dt.hour:02d}:{dt.minute:02d} น."


@dataclass
class ExplanationRow:
    label: str
    value: str


def compute_explanation_rows(
    curriculum: Curriculum,
    cohort_year: int | None,
    total_students: int,
    target_rate: Decimal,
    exported_by: str,
    sheet_names: list[tuple[str, str]],
) -> list[ExplanationRow]:
    """ชีตแรกสุดของรายงาน - อธิบายสูตร/นิยามให้พอเข้าใจไฟล์นี้ได้เองโดยไม่ต้องถามใคร รวมทั้งรายชื่อชีต
    ทั้งหมดพร้อมคำอธิบายสั้นๆ ว่าแต่ละชีตตอบคำถามอะไร (sheet_names คือ [(ชื่อชีต, คำอธิบายสั้น), ...]
    ตามลำดับจริงที่ workbook จะสร้าง - ส่งเข้ามาจาก export service เพื่อไม่ให้รายชื่อชีตสองที่หลุดไม่ตรงกัน)"""
    rows = [
        ExplanationRow("หลักสูตร", f"{curriculum.name} ({curriculum.year})"),
        ExplanationRow("รุ่นที่เลือก", f"รุ่น {cohort_year}" if cohort_year is not None else "ทุกรุ่น"),
        ExplanationRow("จำนวนนักศึกษาในรายงานนี้", str(total_students)),
        ExplanationRow("วันเวลาที่ออกรายงาน", _thai_datetime_str(datetime.now())),
        ExplanationRow("ผู้ออกรายงาน", exported_by),
        ExplanationRow(
            "สูตรคำนวณ % บรรลุ PLO ต่อคน",
            "PLO_x = ผลรวม(CLO mastery × น้ำหนักคู่ CLO-PLO) ÷ ผลรวมน้ำหนัก โดยนับเฉพาะ CLO ที่ผูกกับ "
            "PLO ข้อนั้นโดยตรง (clo_plo_mapping) และนักศึกษามีคะแนนบันทึกไว้จริงเท่านั้น - CLO mastery "
            "เองก็เป็นค่าเฉลี่ยถ่วงน้ำหนักของ % คะแนนในชิ้นงานที่ผูกกับ CLO นั้น",
        ),
        ExplanationRow(
            "เกณฑ์บรรลุรายคน",
            f"นักศึกษาคนหนึ่งถือว่า \"บรรลุ PLO ข้อนั้น\" เมื่อ PLO_x ≥ {PLO_ACHIEVEMENT_THRESHOLD_PERCENT}% "
            "(ค่าคงที่เดียวทั้งระบบ ไม่แยกต่อ PLO)",
        ),
        ExplanationRow(
            "เกณฑ์บรรลุระดับหลักสูตรที่ใช้ในรายงานนี้",
            f"PLO ข้อหนึ่งถือว่า \"บรรลุระดับหลักสูตร\" เมื่อร้อยละของนักศึกษาที่บรรลุ (จากทั้งหมด) "
            f"≥ {target_rate}%",
        ),
        ExplanationRow(
            "หมายเหตุตัวหารในชีต \"สรุปการบรรลุ PLO\"",
            "คะแนนเฉลี่ยและร้อยละที่บรรลุคอลัมน์หลักหารด้วยนักศึกษาทั้งหมด (คนที่ไม่มีข้อมูลนับเป็น 0%) "
            "เพื่อให้ตรงกับตัวเลขบนหน้าเว็บเป๊ะ ส่วนคอลัมน์ \"ร้อยละที่บรรลุ (จากผู้มีข้อมูล)\" คำนวณแยก "
            "จากผู้ที่มีข้อมูลจริงเท่านั้น เป็นคอลัมน์เสริมให้เห็นภาพทั้งสองมุม",
        ),
    ]
    for name, description in sheet_names:
        rows.append(ExplanationRow(f'ชีต "{name}"', description))
    return rows


@dataclass
class PLOSummaryRow:
    plo_id: int
    plo_code: str
    category: str
    description: str
    course_count: int
    clo_count: int
    total_students: int
    student_count_with_data: int
    average_achieved_percent: float
    achieved_student_count: int
    achieved_rate_percent: float  # จากนักศึกษาทั้งหมด (ตรงกับหน้าเว็บ)
    achieved_rate_percent_with_data: str  # จากผู้มีข้อมูลเท่านั้น - "-" ถ้าไม่มีใครมีข้อมูลเลย
    status: str  # บรรลุ / ไม่บรรลุ / ยังไม่มี CLO ผูก / ยังไม่มีข้อมูล


def compute_plo_summary_rows(
    db: Session,
    curriculum_id: int,
    result: CurriculumPLOAchievement,
    target_rate: Decimal,
) -> list[PLOSummaryRow]:
    """หนึ่งแถวต่อ PLO - ตัวเลขหลัก (average_achieved_percent, achieved_rate_percent) มาจาก
    compute_cohort_plo_achievement() ตรงๆ (หารด้วยนักศึกษาทั้งหมดเหมือน GET /plo/achievement/cohort
    ทุกประการ - ห้ามเปลี่ยน) เพิ่มแค่คอลัมน์ course_count/clo_count (จาก clo_plo_mapping) และ
    achieved_rate_percent_with_data (คอลัมน์เสริม) เข้าไป"""
    plo_clo_weights, plo_course_clo_ids, _thresholds = _build_plo_requirements(db, curriculum_id)
    qualifying_plo_ids = _qualifying_plo_ids(plo_clo_weights)

    plos_by_id = {
        p.id: p
        for p in db.query(PLO).filter(PLO.curriculum_id == curriculum_id).all()
    }

    rows: list[PLOSummaryRow] = []
    for summary in result.plo_summary:
        plo = plos_by_id.get(summary.plo_id)
        course_count = len(plo_course_clo_ids.get(summary.plo_id, {}))
        clo_count = len(plo_clo_weights.get(summary.plo_id, {}))

        if summary.plo_id not in qualifying_plo_ids:
            status = "ยังไม่มี CLO ผูก"
        elif summary.student_count_with_data == 0:
            status = "ยังไม่มีข้อมูล"
        elif summary.achieved_rate_percent >= float(target_rate):
            status = "บรรลุ"
        else:
            status = "ไม่บรรลุ"

        if summary.student_count_with_data > 0:
            rate_with_data = (
                Decimal(summary.achieved_student_count)
                / Decimal(summary.student_count_with_data)
                * Decimal(100)
            ).quantize(Decimal("0.1"))
            rate_with_data_display = f"{rate_with_data}"
        else:
            rate_with_data_display = "-"

        rows.append(
            PLOSummaryRow(
                plo_id=summary.plo_id,
                plo_code=summary.plo_code,
                category=plo.category if plo is not None else "-",
                description=summary.description,
                course_count=course_count,
                clo_count=clo_count,
                total_students=result.total_students,
                student_count_with_data=summary.student_count_with_data,
                average_achieved_percent=summary.average_achieved_percent,
                achieved_student_count=summary.achieved_student_count,
                achieved_rate_percent=summary.achieved_rate_percent,
                achieved_rate_percent_with_data=rate_with_data_display,
                status=status,
            )
        )
    return rows


def _resolve_curriculum_map_study_plan(
    db: Session, curriculum_id: int, cohort_year: int | None
) -> tuple[dict[int, StudyPlan], str]:
    """หา study_plan ที่จะใช้จัดเรียงวิชาในชีต "แผนที่หลักสูตร PLO×รายวิชา" - คืน (course_id -> StudyPlan,
    ข้อความหมายเหตุว่าใช้แผนไหน) ตามลำดับความสำคัญ : รุ่นที่เลือก (ถ้ามี cohort_year เฉพาะรุ่นนั้น) >
    แผนมาตรฐาน (cohort_year IS NULL) > รุ่นล่าสุดที่มีแผน (fallback สุดท้าย)"""
    if cohort_year is not None:
        rows = (
            db.query(StudyPlan)
            .filter(StudyPlan.curriculum_id == curriculum_id, StudyPlan.cohort_year == cohort_year)
            .all()
        )
        if rows:
            return {r.course_id: r for r in rows}, f"ใช้แผนการศึกษาเฉพาะรุ่น {cohort_year}"

    standard_rows = (
        db.query(StudyPlan)
        .filter(StudyPlan.curriculum_id == curriculum_id, StudyPlan.cohort_year.is_(None))
        .all()
    )
    if standard_rows:
        note = (
            "ใช้แผนการศึกษามาตรฐาน (ไม่มีแผนเฉพาะรุ่นที่เลือก)"
            if cohort_year is not None
            else "ใช้แผนการศึกษามาตรฐาน"
        )
        return {r.course_id: r for r in standard_rows}, note

    latest_cohort_row = (
        db.query(StudyPlan.cohort_year)
        .filter(StudyPlan.curriculum_id == curriculum_id, StudyPlan.cohort_year.isnot(None))
        .order_by(StudyPlan.cohort_year.desc())
        .first()
    )
    if latest_cohort_row is not None:
        latest_year = latest_cohort_row[0]
        rows = (
            db.query(StudyPlan)
            .filter(StudyPlan.curriculum_id == curriculum_id, StudyPlan.cohort_year == latest_year)
            .all()
        )
        return {r.course_id: r for r in rows}, (
            f"ไม่มีแผนมาตรฐานหรือแผนของรุ่นที่เลือก - ใช้แผนของรุ่นล่าสุดที่มีข้อมูล (รุ่น {latest_year}) แทน"
        )

    return {}, "หลักสูตรนี้ยังไม่มีแผนการศึกษา (study_plan) เลย - เรียงตามรหัสวิชาแทน"


@dataclass
class CurriculumMapCell:
    clo_count: int  # จำนวน CLO ของวิชานี้ที่ผูกกับ PLO นี้ (0 = ไม่ผูกเลย)
    responsibility: str | None  # 'primary' / 'secondary' / None (ไม่มีแถวใน course_plo)
    mismatch: str | None  # 'no_clo' / 'no_course_plo' / None


@dataclass
class CurriculumMapRow:
    course_id: int
    course_code: str
    name_th: str
    credit: int
    year_level: int | None
    semester: int | None
    in_study_plan: bool
    cells: dict[int, CurriculumMapCell]  # plo_id -> cell
    plo_count: int  # จำนวน PLO ที่วิชานี้ผูกอยู่จริง (clo_count > 0)


@dataclass
class CurriculumMapResult:
    rows: list[CurriculumMapRow]
    course_count_by_plo: dict[int, int]
    study_plan_note: str


def compute_curriculum_map(
    db: Session, curriculum_id: int, cohort_year: int | None, plos: list[PLO]
) -> CurriculumMapResult:
    """ชีต "แผนที่หลักสูตร PLO×รายวิชา" - หนึ่งแถวต่อวิชา เรียงตามชั้นปี/ภาคจาก study_plan วิชาที่ไม่มี
    ใน study_plan ต่อท้ายตาราง ตรวจความไม่สอดคล้องระหว่าง course_plo (ตั้งใจ) กับ clo_plo_mapping
    (ทำจริง) 2 กรณีตามสเปก"""
    courses = db.query(Course).filter(Course.curriculum_id == curriculum_id).all()
    course_by_id = {c.id: c for c in courses}

    study_plan_by_course, study_plan_note = _resolve_curriculum_map_study_plan(
        db, curriculum_id, cohort_year
    )

    course_plo_rows = (
        db.query(CoursePLO)
        .join(Course, Course.id == CoursePLO.course_id)
        .filter(Course.curriculum_id == curriculum_id)
        .all()
    )
    responsibility_by_course_plo: dict[tuple[int, int], str] = {
        (cp.course_id, cp.plo_id): cp.responsibility_level for cp in course_plo_rows
    }

    clo_plo_rows = (
        db.query(CLOPLOMapping.plo_id, CLO.course_id)
        .join(CLO, CLO.id == CLOPLOMapping.clo_id)
        .join(Course, Course.id == CLO.course_id)
        .filter(Course.curriculum_id == curriculum_id)
        .all()
    )
    clo_count_by_course_plo: dict[tuple[int, int], int] = {}
    for plo_id, course_id in clo_plo_rows:
        key = (course_id, plo_id)
        clo_count_by_course_plo[key] = clo_count_by_course_plo.get(key, 0) + 1

    course_count_by_plo: dict[int, int] = {}

    rows: list[CurriculumMapRow] = []
    for course in courses:
        plan = study_plan_by_course.get(course.id)
        cells: dict[int, CurriculumMapCell] = {}
        plo_count = 0
        for plo in plos:
            key = (course.id, plo.id)
            clo_count = clo_count_by_course_plo.get(key, 0)
            responsibility = responsibility_by_course_plo.get(key)

            mismatch = None
            if responsibility is not None and clo_count == 0:
                mismatch = "no_clo"
            elif responsibility is None and clo_count > 0:
                mismatch = "no_course_plo"

            cells[plo.id] = CurriculumMapCell(
                clo_count=clo_count, responsibility=responsibility, mismatch=mismatch
            )
            if clo_count > 0:
                plo_count += 1
                course_count_by_plo[plo.id] = course_count_by_plo.get(plo.id, 0) + 1

        rows.append(
            CurriculumMapRow(
                course_id=course.id,
                course_code=course.course_code,
                name_th=course.name_th,
                credit=course.credit,
                year_level=plan.year_level if plan is not None else None,
                semester=plan.semester if plan is not None else None,
                in_study_plan=plan is not None,
                cells=cells,
                plo_count=plo_count,
            )
        )

    # เรียง: มีใน study_plan ก่อน (ตามชั้นปี->ภาค->รหัสวิชา) แล้วตามด้วยวิชาที่ไม่มีใน study_plan
    # (ตามรหัสวิชา) ต่อท้ายตาราง
    rows.sort(
        key=lambda r: (
            0 if r.in_study_plan else 1,
            r.year_level if r.year_level is not None else 999,
            r.semester if r.semester is not None else 999,
            r.course_code,
        )
    )

    return CurriculumMapResult(
        rows=rows, course_count_by_plo=course_count_by_plo, study_plan_note=study_plan_note
    )


@dataclass
class CLOPLOWeightRow:
    course_code: str
    course_name: str
    clo_code: str
    clo_description: str
    weights: dict[int, Decimal]  # plo_id -> weight_percent (ไม่มี key = ไม่ผูก)


def compute_clo_plo_weight_rows(db: Session, curriculum_id: int) -> list[CLOPLOWeightRow]:
    """ชีต "CLO×PLO (น้ำหนัก)" - หนึ่งแถวต่อ CLO ที่มี mapping อย่างน้อย 1 คู่ เรียงตามรหัสวิชาแล้วตาม
    รหัส CLO"""
    clos = (
        db.query(CLO)
        .join(Course, Course.id == CLO.course_id)
        .filter(Course.curriculum_id == curriculum_id)
        .filter(CLO.plo_mappings.any())
        .all()
    )
    clos.sort(key=lambda c: (c.course.course_code, c.code))

    rows: list[CLOPLOWeightRow] = []
    for clo in clos:
        weights = {mapping.plo_id: mapping.weight_percent for mapping in clo.plo_mappings}
        rows.append(
            CLOPLOWeightRow(
                course_code=clo.course.course_code,
                course_name=clo.course.name_th,
                clo_code=clo.code,
                clo_description=clo.description,
                weights=weights,
            )
        )
    return rows


@dataclass
class TraceabilityRow:
    plo_code: str
    course_code: str
    clo_code: str
    weight_percent: Decimal
    weight_share_percent: Decimal  # สัดส่วนน้ำหนักของคู่นี้ในบรรดา CLO ทั้งหมดที่ผูกกับ PLO ข้อเดียวกัน
    students_with_score: int
    average_mastery_percent: Decimal | None  # None = ไม่มีใครมีคะแนนเลย
    passed_count: int


def compute_traceability_rows(
    db: Session, curriculum_id: int, result: CurriculumPLOAchievement
) -> list[TraceabilityRow]:
    """ชีต "ย้อนรอยการคำนวณ" - หนึ่งแถวต่อคู่ CLO-PLO เรียงตาม PLO แล้วตามวิชา ใช้ mastery จาก
    _clo_mastery_for_students_batch ของนักศึกษาชุดเดียวกับรายงานนี้ (result.students) ไม่ query ทีละคน"""
    plo_clo_weights, _plo_course_clo_ids, clo_pass_thresholds = _build_plo_requirements(
        db, curriculum_id
    )

    all_clo_ids = {clo_id for weights in plo_clo_weights.values() for clo_id in weights}
    clos = db.query(CLO).filter(CLO.id.in_(all_clo_ids)).all() if all_clo_ids else []
    clo_by_id = {c.id: c for c in clos}

    plos_by_id = {p.plo_id: p for p in result.plo_summary}

    student_ids = [s.student_id for s in result.students]
    clo_mastery_by_student = _clo_mastery_for_students_batch(db, student_ids)

    rows: list[TraceabilityRow] = []
    for plo_id, clo_weights in plo_clo_weights.items():
        plo_summary = plos_by_id.get(plo_id)
        if plo_summary is None:
            continue
        weight_total = sum(clo_weights.values()) or Decimal(1)

        for clo_id, weight in clo_weights.items():
            clo = clo_by_id.get(clo_id)
            if clo is None:
                continue
            threshold = clo_pass_thresholds.get(clo_id)

            masteries = [
                clo_mastery_by_student.get(sid, {}).get(clo_id)
                for sid in student_ids
            ]
            masteries_with_data = [m for m in masteries if m is not None]
            students_with_score = len(masteries_with_data)
            average_mastery = (
                (sum(masteries_with_data) / Decimal(students_with_score)).quantize(Decimal("0.1"))
                if students_with_score > 0
                else None
            )
            passed_count = (
                sum(1 for m in masteries_with_data if threshold is not None and m >= threshold)
            )

            rows.append(
                TraceabilityRow(
                    plo_code=plo_summary.plo_code,
                    course_code=clo.course.course_code,
                    clo_code=clo.code,
                    weight_percent=weight,
                    weight_share_percent=(weight / weight_total * Decimal(100)).quantize(Decimal("0.1")),
                    students_with_score=students_with_score,
                    average_mastery_percent=average_mastery,
                    passed_count=passed_count,
                )
            )

    rows.sort(key=lambda r: (r.plo_code, r.course_code, r.clo_code))
    return rows


@dataclass
class CohortComparisonCell:
    average_achieved_percent: float
    achieved_rate_percent: float


@dataclass
class CohortComparisonRow:
    plo_code: str
    description: str
    per_cohort: dict[int, CohortComparisonCell]  # cohort_year -> cell


@dataclass
class CohortComparisonResult:
    rows: list[CohortComparisonRow]
    student_count_by_cohort: dict[int, int]


def compute_cohort_comparison(
    db: Session, curriculum_id: int, cohort_years: list[int]
) -> CohortComparisonResult:
    """ชีต "เปรียบเทียบรายรุ่น" (เฉพาะตอนไม่ระบุ cohort_year) - คำนวณผ่าน compute_cohort_plo_achievement
    ตัวเดียวกับ endpoint หลัก ทีละรุ่น (จำนวนรุ่นในระบบน้อย รับได้ตามสเปก) เพื่อไม่ให้มีสูตรคำนวณซ้ำชุดที่
    สอง"""
    per_cohort_results: dict[int, CurriculumPLOAchievement] = {}
    for year in cohort_years:
        result = compute_cohort_plo_achievement(db, curriculum_id, cohort_year=year)
        if result is not None:
            per_cohort_results[year] = result

    plo_order: list[tuple[str, str]] = []
    seen_codes: set[str] = set()
    for result in per_cohort_results.values():
        for summary in result.plo_summary:
            if summary.plo_code not in seen_codes:
                seen_codes.add(summary.plo_code)
                plo_order.append((summary.plo_code, summary.description))

    rows: list[CohortComparisonRow] = []
    for plo_code, description in plo_order:
        per_cohort: dict[int, CohortComparisonCell] = {}
        for year, result in per_cohort_results.items():
            summary = next((s for s in result.plo_summary if s.plo_code == plo_code), None)
            if summary is not None:
                per_cohort[year] = CohortComparisonCell(
                    average_achieved_percent=summary.average_achieved_percent,
                    achieved_rate_percent=summary.achieved_rate_percent,
                )
        rows.append(CohortComparisonRow(plo_code=plo_code, description=description, per_cohort=per_cohort))

    student_count_by_cohort = {
        year: result.total_students for year, result in per_cohort_results.items()
    }
    return CohortComparisonResult(rows=rows, student_count_by_cohort=student_count_by_cohort)


@dataclass
class PersonalRow:
    student_id: str
    student_name: str
    cohort_year: int | None
    plo_percents: dict[int, float]  # plo_id -> achieved_percent (0.0 แสดงเป็น "-" ฝั่ง export - ดู
    # หมายเหตุใน module docstring เรื่อง 0.0 หมายถึง "ไม่มีข้อมูล" ตามธรรมเนียมเดิมของระบบ)
    plo_achieved: dict[int, bool]
    achieved_count: int


def compute_personal_rows(db: Session, result: CurriculumPLOAchievement) -> list[PersonalRow]:
    """ชีต "รายบุคคล" (admin เท่านั้น) - reshape จาก result.students ที่คำนวณไว้แล้ว (ไม่คำนวณซ้ำ) แค่
    เติม cohort_year ที่ StudentPLOAchievement ไม่มีเก็บไว้ (query แยกเพิ่ม)"""
    student_ids = [s.student_id for s in result.students]
    cohort_by_student = {
        row[0]: row[1]
        for row in db.query(Student.id, Student.cohort_year).filter(Student.id.in_(student_ids)).all()
    }

    rows: list[PersonalRow] = []
    for student in result.students:
        plo_percents = {item.plo_id: item.achieved_percent for item in student.plo_achievements}
        plo_achieved = {item.plo_id: item.is_achieved for item in student.plo_achievements}
        rows.append(
            PersonalRow(
                student_id=student.student_id,
                student_name=student.student_name,
                cohort_year=cohort_by_student.get(student.student_id),
                plo_percents=plo_percents,
                plo_achieved=plo_achieved,
                achieved_count=sum(1 for achieved in plo_achieved.values() if achieved),
            )
        )
    return rows
