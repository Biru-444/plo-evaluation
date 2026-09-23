"""
ทำอะไร : สร้างไฟล์ Excel ประกอบการกรอก มคอ.5 (รายงานผลการดำเนินการของรายวิชา ตามแบบฟอร์ม OBE5 BRU) ของ
         course_offering เดียว - ระดับ CLO เท่านั้น (ไม่คำนวณ PLO - อยู่รายงานอีกตัว ดู
         TASK-export-mco5.md) 5 ชีต: ข้อมูลรายวิชา, ผลการบรรลุ CLO, สรุปผลการเรียน (กระจายเกรด),
         การยืนยันผลสัมฤทธิ์ (ต่อชิ้นงาน), รายบุคคล (เฉพาะ admin/อาจารย์เจ้าของวิชา - ข้อมูล PDPA)

เชื่อมกับ : resolve_mco5_export_access() เช็คสิทธิ์ + หา offering (เรียกจาก
            app/routes/clo_calculation.py::export_mco5_excel) - build_mco5_excel() เรียก
            compute_offering_clo_achievement_raw() จาก clo_achievement_service.py เอาตัวเลข CLO มา
            (สูตรเดียวกับ GET /clo-achievement เป๊ะ ไม่คำนวณ mastery ซ้ำเอง) แล้ว query ข้อมูลเพิ่มเอง
            เฉพาะส่วนที่ endpoint เดิมไม่ได้คืนมา (เกรด, รายชื่อชิ้นงาน, ชั้นปีจาก study_plan ฯลฯ)

ถ้าแก้ : ฟอนต์ต้องเป็น "TH Sarabun New" เสมอ (ไฟล์นี้จะถูกคัดลอกไปใส่แบบฟอร์มราชการจริง) - เพิ่ม/แก้ไข
         ชีตต้องอัปเดต TASK-export-mco5.md ให้ตรงด้วย (เอกสารนี้เป็นสเปกอ้างอิงของฟีเจอร์)
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from io import BytesIO

from fastapi import HTTPException
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet
from sqlalchemy.orm import Session

from app.models import (
    AssessmentItem,
    CourseOffering,
    Enrollment,
    Student,
    StudentScore,
    StudyPlan,
    User,
)
from app.services.clo_achievement_service import (
    CLOAchievementResult,
    compute_offering_clo_achievement_raw,
)
from app.services.domain_category_check import DOMAIN_LABEL_TH

FONT_NAME = "TH Sarabun New"
BASE_FONT = Font(name=FONT_NAME, size=15)
BOLD_FONT = Font(name=FONT_NAME, size=15, bold=True)
HEADER_FONT = Font(name=FONT_NAME, size=16, bold=True)
TITLE_FONT = Font(name=FONT_NAME, size=18, bold=True)
WRAP_ALIGNMENT = Alignment(wrap_text=True, vertical="top")
HEADER_ALIGNMENT = Alignment(horizontal="center", vertical="center", wrap_text=True)

# สีไฮไลต์อ่อนๆ - เหลือง/ส้มอ่อนสำหรับแถว/ข้อความเตือน (CLO ไม่บรรลุ ต้องกรอกแนวทางปรับปรุง), แดงอ่อน
# สำหรับเซลล์คะแนนที่ไม่ผ่านในชีตรายบุคคล
WARNING_FILL = PatternFill(start_color="FFF3CD", end_color="FFF3CD", fill_type="solid")
FAIL_FILL = PatternFill(start_color="F8D7DA", end_color="F8D7DA", fill_type="solid")

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
    ทำอะไร : หา course_offering + เช็คสิทธิ์การ export มคอ.5 ในฟังก์ชันเดียว คืน (offering,
             include_personal_sheet) - include_personal_sheet=False ตัดชีต 5 (ข้อมูลรายบุคคล) ออก

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
    None (หน้า Excel จะเว้นว่างตามสเปก)"""
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


def _clo_status(result: CLOAchievementResult, target_rate: Decimal) -> str:
    """'บรรลุ' / 'ไม่บรรลุ' (เทียบ achieved_rate_percent กับ target_rate) / 'ไม่มีข้อมูล' (ไม่มีใครมี
    คะแนนให้ตัดสินเลย - passed_count+failed_count เป็น 0)"""
    if result.passed_count + result.failed_count == 0:
        return "ไม่มีข้อมูล"
    if result.achieved_rate_percent >= float(target_rate):
        return "บรรลุ"
    return "ไม่บรรลุ"


def _autofit_columns(ws: Worksheet, widths: list[int]) -> None:
    for i, width in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(i)].width = width


def _build_sheet1_course_info(
    wb: Workbook, db: Session, offering: CourseOffering, target_rate: Decimal
) -> None:
    ws = wb.active
    ws.title = "ข้อมูลรายวิชา"
    course = offering.course
    curriculum = course.curriculum
    instructor_name = (
        f"{offering.instructor.first_name} {offering.instructor.last_name}"
        if offering.instructor is not None
        else "-"
    )
    name_th_en = course.name_th + (f" / {course.name_en}" if course.name_en else "")
    year_level = _resolve_year_level(db, offering)

    rows = [
        ("รหัสวิชา", course.course_code),
        ("ชื่อวิชา (ไทย/อังกฤษ)", name_th_en),
        ("หน่วยกิต", course.credit),
        ("หลักสูตร", f"{curriculum.name} ({curriculum.year})"),
        ("หมวดวิชา", course.category or "-"),
        ("อาจารย์ผู้สอน", instructor_name),
        ("ภาคการศึกษา/ปีการศึกษา", f"{offering.semester}/{offering.academic_year}"),
        ("กลุ่มเรียน", offering.section),
        ("ชั้นปี", year_level if year_level is not None else "-"),
        ("วันที่ออกรายงาน", _thai_date_str(date.today())),
        ("เกณฑ์บรรลุระดับรายวิชา", f"{target_rate}%"),
    ]

    ws.cell(row=1, column=1, value="ข้อมูลรายวิชา (มคอ.5 หมวด 1)").font = TITLE_FONT
    for i, (label, value) in enumerate(rows, start=3):
        label_cell = ws.cell(row=i, column=1, value=label)
        label_cell.font = BOLD_FONT
        value_cell = ws.cell(row=i, column=2, value=value)
        value_cell.font = BASE_FONT
    _autofit_columns(ws, [28, 50])


def _build_sheet2_clo_achievement(
    wb: Workbook, raw_results: list[CLOAchievementResult], target_rate: Decimal
) -> dict[int, str]:
    """สร้างชีต 'ผลการบรรลุ CLO' คืน dict {clo_id: status} ให้ชีต 4 (การยืนยันผลสัมฤทธิ์) เอาไปใช้ต่อ
    (ไม่ต้องคำนวณสถานะซ้ำ)"""
    ws = wb.create_sheet("ผลการบรรลุ CLO")
    headers = [
        "CLO",
        "คำอธิบาย",
        "ด้าน",
        "วิธีการประเมิน",
        "เกณฑ์ผ่านรายคน (%)",
        "คะแนนเฉลี่ย (%)",
        "ผ่าน (คน)",
        "ไม่ผ่าน (คน)",
        "ไม่มีข้อมูล (คน)",
        "ร้อยละที่ผ่าน",
        "สถานะ",
        "ผลที่เกิดกับนักศึกษา",
        "แนวทางพัฒนาปรับปรุง",
    ]
    for col, header in enumerate(headers, start=1):
        cell = ws.cell(row=1, column=col, value=header)
        cell.font = HEADER_FONT
        cell.alignment = HEADER_ALIGNMENT

    status_by_clo_id: dict[int, str] = {}
    row_idx = 2
    for result in raw_results:
        clo = result.clo
        status = _clo_status(result, target_rate)
        status_by_clo_id[clo.id] = status

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

        values = [
            clo.code,
            clo.description,
            DOMAIN_LABEL_TH.get(clo.domain, "-") if clo.domain else "-",
            assessment_text or "-",
            float(clo.pass_threshold_percent),
            float(avg) if avg is not None else "-",
            result.passed_count,
            result.failed_count,
            result.students_without_data,
            result.achieved_rate_percent,
            status,
            outcome_text,
            improvement_text,
        ]
        for col, value in enumerate(values, start=1):
            cell = ws.cell(row=row_idx, column=col, value=value)
            cell.font = BASE_FONT
            cell.alignment = WRAP_ALIGNMENT
            if status == "ไม่บรรลุ":
                cell.fill = WARNING_FILL
        row_idx += 1

    _autofit_columns(ws, [10, 30, 14, 32, 12, 12, 8, 8, 10, 10, 10, 40, 30])
    return status_by_clo_id


def _build_sheet3_grade_distribution(wb: Workbook, db: Session, offering: CourseOffering) -> None:
    ws = wb.create_sheet("สรุปผลการเรียน")
    enrollments = db.query(Enrollment).filter(Enrollment.offering_id == offering.id).all()
    total_registered = len(enrollments)
    withdrawn = sum(1 for e in enrollments if e.final_grade == "W")
    remaining = total_registered - withdrawn

    ws.cell(row=1, column=1, value="สรุปผลการเรียน (มคอ.5 หมวด 3 ข้อ 1-4)").font = TITLE_FONT
    ws.cell(row=3, column=1, value="จำนวนนักศึกษาที่ลงทะเบียน").font = BOLD_FONT
    ws.cell(row=3, column=2, value=total_registered).font = BASE_FONT
    ws.cell(row=4, column=1, value="จำนวนที่ถอน (W)").font = BOLD_FONT
    ws.cell(row=4, column=2, value=withdrawn).font = BASE_FONT
    ws.cell(row=5, column=1, value="จำนวนที่คงอยู่เมื่อสิ้นภาค").font = BOLD_FONT
    ws.cell(row=5, column=2, value=remaining).font = BASE_FONT

    if total_registered > 0 and all(e.final_grade is None for e in enrollments):
        ws.cell(row=6, column=1, value="หมายเหตุ: ยังไม่มีข้อมูลเกรดในระบบ — กรอกจากระบบทะเบียน").font = BOLD_FONT

    header_row = 8
    headers = ["ระดับคะแนน", "ความหมาย", "จำนวน (คน)", "ร้อยละ"]
    for col, header in enumerate(headers, start=1):
        cell = ws.cell(row=header_row, column=col, value=header)
        cell.font = HEADER_FONT
        cell.alignment = HEADER_ALIGNMENT

    grade_counts = {g: 0 for g in GRADE_ORDER}
    no_grade_count = 0
    for e in enrollments:
        if e.final_grade is None:
            no_grade_count += 1
        elif e.final_grade in grade_counts:
            grade_counts[e.final_grade] += 1

    def _percent_str(count: int) -> str:
        # แถวที่เป็น 0 แสดง "-" เสมอตามแบบฟอร์มจริง (ไม่ใช่ "0.00") - total_registered เป็น 0 ก็ต้อง
        # "-" ด้วย (หารด้วยศูนย์ไม่ได้ และ count จะเป็น 0 อยู่แล้วในกรณีนี้)
        if count == 0 or total_registered == 0:
            return "-"
        return f"{(Decimal(count) / Decimal(total_registered) * Decimal(100)).quantize(Decimal('0.01'))}"

    row_idx = header_row + 1
    for grade in GRADE_ORDER:
        count = grade_counts[grade]
        ws.cell(row=row_idx, column=1, value=grade).font = BASE_FONT
        ws.cell(row=row_idx, column=2, value=GRADE_MEANING[grade]).font = BASE_FONT
        ws.cell(row=row_idx, column=3, value=count).font = BASE_FONT
        ws.cell(row=row_idx, column=4, value=_percent_str(count)).font = BASE_FONT
        row_idx += 1

    ws.cell(row=row_idx, column=1, value="ยังไม่มีเกรด").font = BASE_FONT
    ws.cell(row=row_idx, column=2, value="-").font = BASE_FONT
    ws.cell(row=row_idx, column=3, value=no_grade_count).font = BASE_FONT
    ws.cell(row=row_idx, column=4, value=_percent_str(no_grade_count)).font = BASE_FONT
    row_idx += 1

    total_percent = "100.00" if total_registered > 0 else "-"
    ws.cell(row=row_idx, column=1, value="รวม").font = BOLD_FONT
    ws.cell(row=row_idx, column=3, value=total_registered).font = BOLD_FONT
    ws.cell(row=row_idx, column=4, value=total_percent).font = BOLD_FONT

    _autofit_columns(ws, [16, 24, 12, 12])


def _build_sheet4_assessment_confirmation(
    wb: Workbook, db: Session, offering: CourseOffering, status_by_clo_id: dict[int, str]
) -> None:
    ws = wb.create_sheet("การยืนยันผลสัมฤทธิ์")
    headers = ["วิธีการ", "CLO ที่วัด", "คะแนนเต็ม", "คะแนนเฉลี่ย (%)", "จำนวนคนที่มีคะแนน", "สรุปผล"]
    for col, header in enumerate(headers, start=1):
        cell = ws.cell(row=1, column=col, value=header)
        cell.font = HEADER_FONT
        cell.alignment = HEADER_ALIGNMENT

    items = db.query(AssessmentItem).filter(AssessmentItem.offering_id == offering.id).all()
    row_idx = 2
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

        values = [
            f"{item.name} ({item.type})",
            ", ".join(clo_codes) if clo_codes else "-",
            float(item.total_score),
            float(avg_percent) if avg_percent is not None else "-",
            len(scores),
            summary,
        ]
        for col, value in enumerate(values, start=1):
            cell = ws.cell(row=row_idx, column=col, value=value)
            cell.font = BASE_FONT
            cell.alignment = WRAP_ALIGNMENT
        row_idx += 1

    _autofit_columns(ws, [30, 20, 12, 14, 16, 45])


def _build_sheet5_individual(
    wb: Workbook, db: Session, offering: CourseOffering, raw_results: list[CLOAchievementResult]
) -> None:
    ws = wb.create_sheet("รายบุคคล")
    ws.cell(row=1, column=1, value="ข้อมูลส่วนบุคคล — ใช้ภายในสาขาเท่านั้น").font = BOLD_FONT

    enrollments = db.query(Enrollment).filter(Enrollment.offering_id == offering.id).all()
    grade_by_student_id = {e.student_id: e.final_grade for e in enrollments}

    # roster เอาจาก raw_results[0] ถ้ามี CLO อย่างน้อย 1 ข้อ (ทุก CLOAchievementResult คำนวณจาก roster
    # เดียวกัน เรียงลำดับเหมือนกันเป๊ะ) ถ้าวิชานี้ไม่มี CLO เลย ต้อง query roster เองแยกต่างหาก
    if raw_results:
        roster_ids_ordered = [sr.student for sr in raw_results[0].student_results]
    else:
        roster_ids_ordered = (
            db.query(Student)
            .join(Enrollment, Enrollment.student_id == Student.id)
            .filter(Enrollment.offering_id == offering.id)
            .order_by(Student.id)
            .all()
        )

    header_row = 3
    ws.cell(row=header_row, column=1, value="รหัสนักศึกษา").font = HEADER_FONT
    ws.cell(row=header_row, column=2, value="ชื่อ-สกุล").font = HEADER_FONT
    ws.cell(row=header_row, column=3, value="เกรด").font = HEADER_FONT
    for col, result in enumerate(raw_results, start=4):
        cell = ws.cell(row=header_row, column=col, value=result.clo.code)
        cell.font = HEADER_FONT
        cell.alignment = HEADER_ALIGNMENT

    for row_offset, student in enumerate(roster_ids_ordered):
        row_idx = header_row + 1 + row_offset
        ws.cell(row=row_idx, column=1, value=student.id).font = BASE_FONT
        ws.cell(row=row_idx, column=2, value=f"{student.first_name} {student.last_name}").font = BASE_FONT
        ws.cell(row=row_idx, column=3, value=grade_by_student_id.get(student.id) or "-").font = BASE_FONT

        for col, result in enumerate(raw_results, start=4):
            student_result = next(
                (sr for sr in result.student_results if sr.student.id == student.id), None
            )
            cell = ws.cell(row=row_idx, column=col)
            cell.font = BASE_FONT
            if student_result is None or student_result.clo_percent is None:
                cell.value = "-"
            else:
                cell.value = float(student_result.clo_percent)
                if student_result.passed is False:
                    cell.fill = FAIL_FILL

    _autofit_columns(ws, [16, 26, 8] + [10] * len(raw_results))


def build_mco5_excel(
    db: Session, offering: CourseOffering, target_rate: Decimal, include_personal_sheet: bool
) -> BytesIO:
    """ทำอะไร : สร้าง workbook ครบ 5 ชีต (หรือ 4 ถ้า include_personal_sheet=False) แล้วคืนเป็น BytesIO
    พร้อมส่งเป็น StreamingResponse - เรียก compute_offering_clo_achievement_raw() ครั้งเดียว ใช้ผลลัพธ์
    ร่วมกันทั้งชีต 2, 4, 5"""
    raw_results = compute_offering_clo_achievement_raw(db, offering)

    wb = Workbook()
    _build_sheet1_course_info(wb, db, offering, target_rate)
    status_by_clo_id = _build_sheet2_clo_achievement(wb, raw_results, target_rate)
    _build_sheet3_grade_distribution(wb, db, offering)
    _build_sheet4_assessment_confirmation(wb, db, offering, status_by_clo_id)
    if include_personal_sheet:
        _build_sheet5_individual(wb, db, offering, raw_results)

    buffer = BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return buffer
