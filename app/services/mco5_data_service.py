"""
ทำอะไร : เตรียม "ข้อมูลพร้อมแสดงผล" สำหรับ export มคอ.5 ทั้งสอง format (Excel - mco5_export_service.py,
         Word - mco5_docx_export_service.py) - ชั้นกลางที่ทำให้สอง format ใช้ข้อมูล/ตรรกะจัดรูปแบบชุด
         เดียวกันเป๊ะ ไม่คำนวณซ้ำคนละสูตรหรือคนละ query (Phase 2 - ดู TASK-export-mco5.md ข้อ 6: "reuse
         the sheet-building data ... do not recompute anything separately for the docx")

เชื่อมกับ : ทุกฟังก์ชัน compute_*() ที่นี่ไม่แตะ openpyxl/python-docx เลย คืนแค่ dataclass ธรรมดา (ค่าดิบ
            ที่จัดรูปแบบไปแล้วเท่าที่เป็น "กฎธุรกิจ" ร่วมกัน เช่น ร้อยละที่เป็น 0 ต้องแสดง "-" - ส่วนที่
            เป็นเรื่องเฉพาะของแต่ละ format เช่น cell เป็นตัวเลขจริงหรือ paragraph text ปล่อยให้ builder
            ของแต่ละ format ตัดสินใจเอง) resolve_mco5_export_access() (เช็คสิทธิ์) ก็อยู่ที่นี่เพราะทั้ง
            สอง endpoint (export/mco5, export/mco5-docx) ใช้ตรรกะเดียวกันเป๊ะ

            ตัวสูตรคำนวณ CLO mastery จริงยังอยู่ที่ clo_achievement_service.py เหมือนเดิม (ไม่แตะ) -
            ที่นี่แค่เรียก compute_offering_clo_achievement_raw() แล้วต่อยอดจัดรูปแบบสำหรับ export

ถ้าแก้ : ถ้าเพิ่ม field ใหม่ที่ต้องโชว์ทั้ง Excel และ Word ให้เพิ่มที่นี่แล้วให้ทั้งสอง builder ดึงไปใช้
         ไม่ใช่เพิ่มแยกคนละที่ (จะทำให้สอง format ข้อมูลไม่ตรงกัน)
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models import AssessmentItem, CourseOffering, Enrollment, StudentScore, StudyPlan, User
from app.services.clo_achievement_service import (
    CLOAchievementResult,
    compute_offering_clo_achievement_raw,
)
from app.services.domain_category_check import DOMAIN_LABEL_TH

# ลำดับ+ความหมายของระดับคะแนนตามแบบฟอร์ม มคอ.5 จริง
GRADE_ORDER = ["A", "B+", "B", "C+", "C", "D+", "D", "F", "S", "U", "Au", "W", "I"]
GRADE_MEANING = {
    "A": "ดีเยี่ยม",
    "B+": "ดีมาก",
    "B": "ดี",
    "C+": "ดีพอใช้",
    "C": "พอใช้",
    "D+": "อ่อน",
    "D": "อ่อนมาก",
    "F": "ตก",
    "S": "พอใจหรือผ่าน",
    "U": "ไม่พอใจหรือไม่ผ่าน",
    "Au": "ไม่นับหน่วยกิต",
    "W": "ถอนรายวิชา",
    "I": "นักศึกษายังทำงานไม่เสร็จฯ",
}


def resolve_mco5_export_access(
    db: Session, offering_id: int, current_user: User
) -> tuple[CourseOffering, bool]:
    """
    ทำอะไร : หา course_offering + เช็คสิทธิ์การ export มคอ.5 (ทั้ง Excel และ Word) ในฟังก์ชันเดียว คืน
             (offering, include_personal_sheet) - include_personal_sheet=False ตัดข้อมูลรายบุคคลออก
             (ชีต 5 ของ Excel - Word ไม่มีส่วนรายบุคคลอยู่แล้วตามสเปก ไม่ใช้ flag นี้)

    เชื่อมกับ : ใช้ pattern เดียวกับ ownership check ใน app/routes/clo.py / clo_plo_mapping.py (admin
                ผ่านเสมอ, อาจารย์ต้องเป็นเจ้าของ offering นี้เท่านั้น)

    ถ้าแก้ : role ที่มีอยู่จริงในระบบตอนนี้มีแค่ "admin"/"instructor" (ดู app/models/user.py) - เงื่อนไข
             "role อื่น" ด้านล่างเผื่อไว้สำหรับ role ในอนาคต (เช่น ประธานหลักสูตร) ที่ยังไม่มีจริงตอนนี้
             แต่ยังต้องมี branch นี้ไว้ตามสเปก - อาจารย์ที่ไม่ใช่เจ้าของ offering โดน 403 ตรงๆ (ไม่ได้รับ
             สิทธิ์แบบ "role อื่น" ทั้งที่ก็ไม่ใช่เจ้าของเหมือนกัน - ตั้งใจแยกสองกรณีนี้ออกจากกันตามสเปก)
    """
    offering = db.get(CourseOffering, offering_id)
    if offering is None:
        raise HTTPException(status_code=404, detail="Course offering not found")

    if current_user.role == "admin":
        return offering, True

    if current_user.role == "instructor":
        if offering.instructor_id != current_user.id:
            raise HTTPException(status_code=403, detail="คุณไม่ใช่ผู้สอนวิชานี้")
        return offering, True

    # role อื่น (เช่น ประธานหลักสูตร ถ้ามีในอนาคต) - ได้เฉพาะชีตสรุป ไม่มีชีตรายบุคคล
    return offering, False


def _thai_date_str(d: date) -> str:
    return f"{d.day:02d}/{d.month:02d}/{d.year + 543}"


def _resolve_year_level(db: Session, offering: CourseOffering) -> int | None:
    """ชั้นปีของวิชานี้จาก study_plan - แผนเฉพาะรุ่น (cohort_year ตรงกับ offering.cohort_year) ชนะแผน
    มาตรฐาน (cohort_year เป็น None) ถ้ามีทั้งคู่ (เหมือน pattern ที่ ylo_calculation.py ใช้) ไม่พบเลย =
    None (export จะเว้นว่าง/แสดง "-" ตามสเปก)"""
    query = db.query(StudyPlan).filter(StudyPlan.course_id == offering.course_id)
    if offering.cohort_year is not None:
        specific = query.filter(StudyPlan.cohort_year == offering.cohort_year).first()
        if specific is not None:
            return specific.year_level
    standard = query.filter(StudyPlan.cohort_year.is_(None)).first()
    if standard is not None:
        return standard.year_level
    any_plan = query.first()
    return any_plan.year_level if any_plan is not None else None


@dataclass
class CourseInfoRow:
    label: str
    value: str


def compute_course_info_rows(
    db: Session, offering: CourseOffering, target_rate: Decimal
) -> list[CourseInfoRow]:
    """หมวด 1 ของ มคอ.5 - 11 แถว (label, value) ตามลำดับที่สเปกกำหนด ใช้ร่วมกันทั้ง Excel (ตาราง 2
    คอลัมน์) และ Word (หมวด 1)"""
    course = offering.course
    curriculum = course.curriculum
    instructor_name = (
        f"{offering.instructor.first_name} {offering.instructor.last_name}"
        if offering.instructor is not None
        else "-"
    )
    name_th_en = course.name_th + (f" / {course.name_en}" if course.name_en else "")
    year_level = _resolve_year_level(db, offering)

    return [
        CourseInfoRow("รหัสวิชา", course.course_code),
        CourseInfoRow("ชื่อวิชา (ไทย/อังกฤษ)", name_th_en),
        CourseInfoRow("หน่วยกิต", str(course.credit)),
        CourseInfoRow("หลักสูตร", f"{curriculum.name} ({curriculum.year})"),
        CourseInfoRow("หมวดวิชา", course.category or "-"),
        CourseInfoRow("อาจารย์ผู้สอน", instructor_name),
        CourseInfoRow("ภาคการศึกษา/ปีการศึกษา", f"{offering.semester}/{offering.academic_year}"),
        CourseInfoRow("กลุ่มเรียน", offering.section),
        CourseInfoRow("ชั้นปี", str(year_level) if year_level is not None else "-"),
        CourseInfoRow("วันที่ออกรายงาน", _thai_date_str(date.today())),
        CourseInfoRow("เกณฑ์บรรลุระดับรายวิชา", f"{target_rate}%"),
    ]


def clo_status(result: CLOAchievementResult, target_rate: Decimal) -> str:
    """'บรรลุ' / 'ไม่บรรลุ' (เทียบ achieved_rate_percent กับ target_rate) / 'ไม่มีข้อมูล' (ไม่มีใครมี
    คะแนนให้ตัดสินเลย - passed_count+failed_count เป็น 0)"""
    if result.passed_count + result.failed_count == 0:
        return "ไม่มีข้อมูล"
    if result.achieved_rate_percent >= float(target_rate):
        return "บรรลุ"
    return "ไม่บรรลุ"


@dataclass
class CLORow:
    clo_id: int
    clo_code: str
    description: str
    domain_label: str
    assessment_text: str
    pass_threshold_percent: float
    average_percent: Decimal | None
    passed_count: int
    failed_count: int
    students_without_data: int
    achieved_rate_percent: float
    status: str
    outcome_text: str
    improvement_text: str


def compute_clo_rows(
    raw_results: list[CLOAchievementResult], target_rate: Decimal
) -> list[CLORow]:
    """หมวด 2 ข้อ 3 ของ มคอ.5 - หนึ่งแถวต่อ CLO ใช้ร่วมกันทั้งชีต 2 ของ Excel และตาราง CLO ของ Word"""
    rows: list[CLORow] = []
    for result in raw_results:
        clo = result.clo
        status = clo_status(result, target_rate)

        assessment_text = "\n".join(
            f"{ic.item.name} (น้ำหนัก {ic.weight_percent}%)" for ic in result.item_clo_mappings
        )
        avg = result.average_percent_with_data
        denom = result.passed_count + result.failed_count

        if denom == 0:
            outcome_text = "ยังไม่มีข้อมูลคะแนนสำหรับ CLO นี้"
        else:
            avg_str = f"{avg:.1f}" if avg is not None else "0.0"
            outcome_text = (
                f"นักศึกษาผ่านเกณฑ์ {result.passed_count} จาก {denom} คน "
                f"({result.achieved_rate_percent:.1f}%) คะแนนเฉลี่ย {avg_str}%"
            )

        improvement_text = "ควรระบุแนวทางปรับปรุง (CLO ไม่บรรลุ)" if status == "ไม่บรรลุ" else ""

        rows.append(
            CLORow(
                clo_id=clo.id,
                clo_code=clo.code,
                description=clo.description,
                domain_label=DOMAIN_LABEL_TH.get(clo.domain, "-") if clo.domain else "-",
                assessment_text=assessment_text or "-",
                pass_threshold_percent=float(clo.pass_threshold_percent),
                average_percent=avg,
                passed_count=result.passed_count,
                failed_count=result.failed_count,
                students_without_data=result.students_without_data,
                achieved_rate_percent=result.achieved_rate_percent,
                status=status,
                outcome_text=outcome_text,
                improvement_text=improvement_text,
            )
        )
    return rows


def _percent_display(count: int, total: int) -> str:
    """ร้อยละที่เป็น 0 แสดง "-" เสมอตามแบบฟอร์มจริง (ไม่ใช่ "0.00") - total เป็น 0 ก็ "-" ด้วย (หารด้วย
    ศูนย์ไม่ได้ และ count จะเป็น 0 อยู่แล้วในกรณีนี้)"""
    if count == 0 or total == 0:
        return "-"
    return f"{(Decimal(count) / Decimal(total) * Decimal(100)).quantize(Decimal('0.01'))}"


@dataclass
class GradeDistributionRow:
    grade: str
    meaning: str
    count: int
    percent_display: str


@dataclass
class GradeDistribution:
    total_registered: int
    withdrawn: int
    remaining: int
    rows: list[GradeDistributionRow]  # 13 เกรดตาม GRADE_ORDER
    no_grade_count: int
    no_grade_percent_display: str
    total_percent_display: str
    all_null_note: bool  # True = ยังไม่มีข้อมูลเกรดในระบบเลยสักคน


def compute_grade_distribution(db: Session, offering: CourseOffering) -> GradeDistribution:
    """หมวด 3 ข้อ 1-4 ของ มคอ.5 - จำนวนลงทะเบียน/ถอน/คงอยู่ + ตารางกระจายเกรด"""
    enrollments = db.query(Enrollment).filter(Enrollment.offering_id == offering.id).all()
    total_registered = len(enrollments)
    withdrawn = sum(1 for e in enrollments if e.final_grade == "W")
    remaining = total_registered - withdrawn

    grade_counts = {g: 0 for g in GRADE_ORDER}
    no_grade_count = 0
    for e in enrollments:
        if e.final_grade is None:
            no_grade_count += 1
        elif e.final_grade in grade_counts:
            grade_counts[e.final_grade] += 1

    rows = [
        GradeDistributionRow(
            grade=grade,
            meaning=GRADE_MEANING[grade],
            count=grade_counts[grade],
            percent_display=_percent_display(grade_counts[grade], total_registered),
        )
        for grade in GRADE_ORDER
    ]

    return GradeDistribution(
        total_registered=total_registered,
        withdrawn=withdrawn,
        remaining=remaining,
        rows=rows,
        no_grade_count=no_grade_count,
        no_grade_percent_display=_percent_display(no_grade_count, total_registered),
        total_percent_display="100.00" if total_registered > 0 else "-",
        all_null_note=total_registered > 0 and all(e.final_grade is None for e in enrollments),
    )


@dataclass
class AssessmentConfirmationRow:
    method_label: str
    clo_codes_label: str
    total_score: float
    average_percent: Decimal | None
    count_with_scores: int
    summary: str


def compute_assessment_confirmation_rows(
    db: Session, offering: CourseOffering, status_by_clo_id: dict[int, str]
) -> list[AssessmentConfirmationRow]:
    """หมวด 3 ข้อ 7 ของ มคอ.5 - หนึ่งแถวต่อ assessment_item ใช้ status_by_clo_id ที่ได้จาก
    compute_clo_rows() (build {clo_id: status}) ไม่คำนวณสถานะ CLO ซ้ำเอง"""
    items = db.query(AssessmentItem).filter(AssessmentItem.offering_id == offering.id).all()
    rows: list[AssessmentConfirmationRow] = []

    for item in items:
        item_clos = item.clo_mappings  # list[ItemCLO], ผ่าน relationship ไม่ต้อง query ซ้ำ
        scores = db.query(StudentScore).filter(StudentScore.item_id == item.id).all()

        clo_codes = [ic.clo.code for ic in item_clos]
        statuses = [status_by_clo_id.get(ic.clo_id, "ไม่มีข้อมูล") for ic in item_clos]

        if not item_clos:
            summary = "ไม่ได้ผูกกับ CLO ใด"
        elif all(s == "บรรลุ" for s in statuses):
            summary = "เป็นไปตามผลลัพธ์การเรียนรู้ในระดับรายวิชาที่กำหนดไว้"
        else:
            not_achieved = [ic.clo.code for ic in item_clos if status_by_clo_id.get(ic.clo_id) != "บรรลุ"]
            summary = f"ยังไม่บรรลุใน {', '.join(not_achieved)}"

        if scores and item.total_score > 0:
            avg_percent = (
                sum((s.score_obtained / item.total_score) * Decimal(100) for s in scores)
                / Decimal(len(scores))
            ).quantize(Decimal("0.1"))
        else:
            avg_percent = None

        rows.append(
            AssessmentConfirmationRow(
                method_label=f"{item.name} ({item.type})",
                clo_codes_label=", ".join(clo_codes) if clo_codes else "-",
                total_score=float(item.total_score),
                average_percent=avg_percent,
                count_with_scores=len(scores),
                summary=summary,
            )
        )
    return rows
