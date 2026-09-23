"""
ทำอะไร : สร้างไฟล์ Excel ประกอบการกรอก มคอ.5 (รายงานผลการดำเนินการของรายวิชา ตามแบบฟอร์ม OBE5 BRU) ของ
         course_offering เดียว - ระดับ CLO เท่านั้น (ไม่คำนวณ PLO - อยู่รายงานอีกตัว ดู
         TASK-export-mco5.md) 5 ชีต: ข้อมูลรายวิชา, ผลการบรรลุ CLO, สรุปผลการเรียน (กระจายเกรด),
         การยืนยันผลสัมฤทธิ์ (ต่อชิ้นงาน), รายบุคคล (เฉพาะ admin/อาจารย์เจ้าของวิชา - ข้อมูล PDPA)

เชื่อมกับ : ไฟล์นี้เป็นแค่ชั้น "วาดลง openpyxl" ล้วนๆ - ข้อมูล/ตรรกะจัดรูปแบบทั้งหมด (คำนวณ CLO, กระจาย
            เกรด, สรุปผลชิ้นงาน) อยู่ใน app/services/mco5_data_service.py ที่ Word export
            (mco5_docx_export_service.py) ใช้ร่วมกันเป๊ะ ไม่มีสูตร/query ซ้ำสองชุด (Phase 2 - ดู
            TASK-export-mco5.md ข้อ 6) - build_mco5_excel() เรียกจาก
            app/routes/clo_calculation.py::export_mco5_excel

ถ้าแก้ : ฟอนต์ต้องเป็น "TH Sarabun New" เสมอ (ไฟล์นี้จะถูกคัดลอกไปใส่แบบฟอร์มราชการจริง) - เพิ่ม/แก้ไข
         ชีตต้องอัปเดต TASK-export-mco5.md ให้ตรงด้วย (เอกสารนี้เป็นสเปกอ้างอิงของฟีเจอร์) - ข้อมูลที่ต้อง
         โชว์ทั้ง Excel และ Word ให้แก้ที่ mco5_data_service.py ไม่ใช่ที่นี่
"""
from __future__ import annotations

from decimal import Decimal
from io import BytesIO

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet
from sqlalchemy.orm import Session

from app.models import CourseOffering, Enrollment, Student
from app.services.clo_achievement_service import (
    CLOAchievementResult,
    compute_offering_clo_achievement_raw,
)
from app.services.mco5_data_service import (
    CLORow,
    compute_assessment_confirmation_rows,
    compute_clo_rows,
    compute_course_info_rows,
    compute_grade_distribution,
)

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


def _autofit_columns(ws: Worksheet, widths: list[int]) -> None:
    for i, width in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(i)].width = width


def _build_sheet1_course_info(
    wb: Workbook, db: Session, offering: CourseOffering, target_rate: Decimal
) -> None:
    ws = wb.active
    ws.title = "ข้อมูลรายวิชา"
    ws.cell(row=1, column=1, value="ข้อมูลรายวิชา (มคอ.5 หมวด 1)").font = TITLE_FONT
    for i, row in enumerate(compute_course_info_rows(db, offering, target_rate), start=3):
        ws.cell(row=i, column=1, value=row.label).font = BOLD_FONT
        ws.cell(row=i, column=2, value=row.value).font = BASE_FONT
    _autofit_columns(ws, [28, 50])


def _build_sheet2_clo_achievement(wb: Workbook, clo_rows: list[CLORow]) -> None:
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

    for row_idx, row in enumerate(clo_rows, start=2):
        values = [
            row.clo_code,
            row.description,
            row.domain_label,
            row.assessment_text,
            row.pass_threshold_percent,
            float(row.average_percent) if row.average_percent is not None else "-",
            row.passed_count,
            row.failed_count,
            row.students_without_data,
            row.achieved_rate_percent,
            row.status,
            row.outcome_text,
            row.improvement_text,
        ]
        for col, value in enumerate(values, start=1):
            cell = ws.cell(row=row_idx, column=col, value=value)
            cell.font = BASE_FONT
            cell.alignment = WRAP_ALIGNMENT
            if row.status == "ไม่บรรลุ":
                cell.fill = WARNING_FILL

    _autofit_columns(ws, [10, 30, 14, 32, 12, 12, 8, 8, 10, 10, 10, 40, 30])


def _build_sheet3_grade_distribution(wb: Workbook, db: Session, offering: CourseOffering) -> None:
    ws = wb.create_sheet("สรุปผลการเรียน")
    dist = compute_grade_distribution(db, offering)

    ws.cell(row=1, column=1, value="สรุปผลการเรียน (มคอ.5 หมวด 3 ข้อ 1-4)").font = TITLE_FONT
    ws.cell(row=3, column=1, value="จำนวนนักศึกษาที่ลงทะเบียน").font = BOLD_FONT
    ws.cell(row=3, column=2, value=dist.total_registered).font = BASE_FONT
    ws.cell(row=4, column=1, value="จำนวนที่ถอน (W)").font = BOLD_FONT
    ws.cell(row=4, column=2, value=dist.withdrawn).font = BASE_FONT
    ws.cell(row=5, column=1, value="จำนวนที่คงอยู่เมื่อสิ้นภาค").font = BOLD_FONT
    ws.cell(row=5, column=2, value=dist.remaining).font = BASE_FONT

    if dist.all_null_note:
        ws.cell(row=6, column=1, value="หมายเหตุ: ยังไม่มีข้อมูลเกรดในระบบ — กรอกจากระบบทะเบียน").font = BOLD_FONT

    header_row = 8
    headers = ["ระดับคะแนน", "ความหมาย", "จำนวน (คน)", "ร้อยละ"]
    for col, header in enumerate(headers, start=1):
        cell = ws.cell(row=header_row, column=col, value=header)
        cell.font = HEADER_FONT
        cell.alignment = HEADER_ALIGNMENT

    row_idx = header_row + 1
    for grade_row in dist.rows:
        ws.cell(row=row_idx, column=1, value=grade_row.grade).font = BASE_FONT
        ws.cell(row=row_idx, column=2, value=grade_row.meaning).font = BASE_FONT
        ws.cell(row=row_idx, column=3, value=grade_row.count).font = BASE_FONT
        ws.cell(row=row_idx, column=4, value=grade_row.percent_display).font = BASE_FONT
        row_idx += 1

    ws.cell(row=row_idx, column=1, value="ยังไม่มีเกรด").font = BASE_FONT
    ws.cell(row=row_idx, column=2, value="-").font = BASE_FONT
    ws.cell(row=row_idx, column=3, value=dist.no_grade_count).font = BASE_FONT
    ws.cell(row=row_idx, column=4, value=dist.no_grade_percent_display).font = BASE_FONT
    row_idx += 1

    ws.cell(row=row_idx, column=1, value="รวม").font = BOLD_FONT
    ws.cell(row=row_idx, column=3, value=dist.total_registered).font = BOLD_FONT
    ws.cell(row=row_idx, column=4, value=dist.total_percent_display).font = BOLD_FONT

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

    rows = compute_assessment_confirmation_rows(db, offering, status_by_clo_id)
    for row_idx, row in enumerate(rows, start=2):
        values = [
            row.method_label,
            row.clo_codes_label,
            row.total_score,
            float(row.average_percent) if row.average_percent is not None else "-",
            row.count_with_scores,
            row.summary,
        ]
        for col, value in enumerate(values, start=1):
            cell = ws.cell(row=row_idx, column=col, value=value)
            cell.font = BASE_FONT
            cell.alignment = WRAP_ALIGNMENT

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
    พร้อมส่งเป็น StreamingResponse - เรียก compute_offering_clo_achievement_raw() ครั้งเดียว แล้วส่งต่อ
    ให้ mco5_data_service.py จัดรูปแบบ ใช้ผลลัพธ์ร่วมกันทั้งชีต 2, 4, 5"""
    raw_results = compute_offering_clo_achievement_raw(db, offering)
    clo_rows = compute_clo_rows(raw_results, target_rate)
    status_by_clo_id = {row.clo_id: row.status for row in clo_rows}

    wb = Workbook()
    _build_sheet1_course_info(wb, db, offering, target_rate)
    _build_sheet2_clo_achievement(wb, clo_rows)
    _build_sheet3_grade_distribution(wb, db, offering)
    _build_sheet4_assessment_confirmation(wb, db, offering, status_by_clo_id)
    if include_personal_sheet:
        _build_sheet5_individual(wb, db, offering, raw_results)

    buffer = BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return buffer
