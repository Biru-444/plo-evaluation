"""
ทำอะไร : สร้างไฟล์ Excel รายงานภาพรวม PLO ↔ รายวิชาของหลักสูตรเดียว (ระดับหลักสูตร/รุ่น ไม่ใช่ offering
         เดียวเหมือน clo_report_export_service.py) - ไม่ยึดตามแบบฟอร์มราชการใดๆ (แนวทางเดียวกับ CLO
         report) 7 ชีต: คำอธิบาย, สรุปการบรรลุ PLO, แผนที่หลักสูตร PLO×รายวิชา, CLO×PLO (น้ำหนัก),
         ย้อนรอยการคำนวณ, เปรียบเทียบรายรุ่น (เฉพาะตอนไม่ระบุ cohort_year), รายบุคคล (เฉพาะ admin -
         ข้อมูล PDPA)

เชื่อมกับ : ไฟล์นี้เป็นแค่ชั้น "วาดลง openpyxl" ล้วนๆ - ข้อมูล/ตรรกะจัดรูปแบบทั้งหมดอยู่ใน
            app/services/plo_report_data_service.py - build_plo_report_excel() เรียกจาก
            app/routes/plo_calculation.py::export_plo_report_excel ตัวเลขหลัก (average/achieved_rate)
            มาจาก compute_cohort_plo_achievement() ตัวเดียวกับ GET /plo/achievement/cohort เป๊ะ

ถ้าแก้ : ฟอนต์ต้องเป็น "TH Sarabun New" เสมอ - ข้อมูลที่ต้องโชว์ในรายงานให้แก้ที่
         plo_report_data_service.py ไม่ใช่ที่นี่ (ไฟล์นี้แค่วาดผล ไม่ควรมีตรรกะคำนวณของตัวเอง)
"""
from __future__ import annotations

from decimal import Decimal
from io import BytesIO

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet
from sqlalchemy.orm import Session

from app.models import PLO, Curriculum
from app.schemas.plo_calculation import CurriculumPLOAchievement
from app.services.plo_report_data_service import (
    compute_clo_plo_weight_rows,
    compute_cohort_comparison,
    compute_curriculum_map,
    compute_explanation_rows,
    compute_personal_rows,
    compute_plo_summary_rows,
    compute_traceability_rows,
)

FONT_NAME = "TH Sarabun New"
BASE_FONT = Font(name=FONT_NAME, size=15)
BOLD_FONT = Font(name=FONT_NAME, size=15, bold=True)
HEADER_FONT = Font(name=FONT_NAME, size=16, bold=True)
TITLE_FONT = Font(name=FONT_NAME, size=18, bold=True)
WRAP_ALIGNMENT = Alignment(wrap_text=True, vertical="top")
HEADER_ALIGNMENT = Alignment(horizontal="center", vertical="center", wrap_text=True)
CENTER_ALIGNMENT = Alignment(horizontal="center", vertical="center")

# สีไฮไลต์ : เหลืองอ่อน = "ไม่บรรลุ" (มีข้อมูลแต่ไม่ถึงเกณฑ์), เทาอ่อน = "ยังไม่มี CLO ผูก" (ช่องโหว่การ
# ออกแบบหลักสูตร คนละเรื่องกับผลการเรียน), แดงอ่อน = คะแนนรายบุคคลต่ำกว่าเกณฑ์, ส้มอ่อน = มี CLO ผูกจริง
# แต่ไม่มีแถวใน course_plo (ตั้งใจไว้ไม่ตรงกับที่ทำจริง)
NOT_ACHIEVED_FILL = PatternFill(start_color="FFF3CD", end_color="FFF3CD", fill_type="solid")
NO_CLO_LINKED_FILL = PatternFill(start_color="E2E3E5", end_color="E2E3E5", fill_type="solid")
FAIL_FILL = PatternFill(start_color="F8D7DA", end_color="F8D7DA", fill_type="solid")
MISMATCH_NO_CLO_FILL = PatternFill(start_color="FFF3CD", end_color="FFF3CD", fill_type="solid")
MISMATCH_NO_COURSE_PLO_FILL = PatternFill(start_color="FCE4D6", end_color="FCE4D6", fill_type="solid")


def _autofit_columns(ws: Worksheet, widths: list[int]) -> None:
    for i, width in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(i)].width = width


def _header_row(ws: Worksheet, row: int, headers: list[str]) -> None:
    for col, header in enumerate(headers, start=1):
        cell = ws.cell(row=row, column=col, value=header)
        cell.font = HEADER_FONT
        cell.alignment = HEADER_ALIGNMENT


def _freeze_and_filter(ws: Worksheet, header_row: int, last_row: int, last_col: int) -> None:
    ws.freeze_panes = ws.cell(row=header_row + 1, column=1)
    ws.auto_filter.ref = f"A{header_row}:{get_column_letter(last_col)}{max(last_row, header_row)}"


SHEET_DESCRIPTIONS = [
    ("สรุปการบรรลุ PLO", "ภาพรวมผลบรรลุของแต่ละ PLO ทั้งหลักสูตร - หนึ่งแถวต่อ PLO"),
    (
        "แผนที่หลักสูตร PLO×รายวิชา",
        "หลักสูตรออกแบบให้ PLO แต่ละข้อถูกสอน/วัดในวิชาใดบ้าง (หลักฐานการออกแบบ)",
    ),
    ("CLO×PLO (น้ำหนัก)", "น้ำหนักของ CLO แต่ละข้อที่ผูกกับ PLO แต่ละข้อ"),
    (
        "ย้อนรอยการคำนวณ",
        "ตัวเลข PLO แต่ละข้อมาจาก CLO/วิชาไหน น้ำหนักเท่าไร (ย้อนรอยการคำนวณ)",
    ),
    ("รายบุคคล", "PLO_x (%) ของนักศึกษาแต่ละคน (เฉพาะ admin - ข้อมูลส่วนบุคคล)"),
]


def _build_sheet_explanation(
    wb: Workbook,
    curriculum,
    cohort_year: int | None,
    total_students: int,
    target_rate: Decimal,
    exported_by: str,
    has_cohort_comparison_sheet: bool,
) -> None:
    ws = wb.active
    ws.title = "คำอธิบาย"
    ws.cell(row=1, column=1, value="คำอธิบายรายงานฉบับนี้").font = TITLE_FONT

    sheet_names = list(SHEET_DESCRIPTIONS)
    if has_cohort_comparison_sheet:
        sheet_names.insert(
            4,
            (
                "เปรียบเทียบรายรุ่น",
                "คะแนนเฉลี่ยและร้อยละที่บรรลุของแต่ละ PLO เทียบระหว่างรุ่น (มีเฉพาะตอนไม่เลือกรุ่นเดียว)",
            ),
        )

    rows = compute_explanation_rows(
        curriculum, cohort_year, total_students, target_rate, exported_by, sheet_names
    )
    for i, row in enumerate(rows, start=3):
        label_cell = ws.cell(row=i, column=1, value=row.label)
        label_cell.font = BOLD_FONT
        label_cell.alignment = WRAP_ALIGNMENT
        value_cell = ws.cell(row=i, column=2, value=row.value)
        value_cell.font = BASE_FONT
        value_cell.alignment = WRAP_ALIGNMENT
    _autofit_columns(ws, [32, 80])


def _build_sheet_plo_summary(
    wb: Workbook, db: Session, curriculum_id: int, result: CurriculumPLOAchievement, target_rate: Decimal
) -> None:
    ws = wb.create_sheet("สรุปการบรรลุ PLO")
    headers = [
        "PLO", "หมวด", "คำอธิบาย", "จำนวนวิชาที่วัด", "จำนวน CLO ที่ผูก", "นักศึกษาทั้งหมด",
        "มีข้อมูล", "ความครอบคลุมข้อมูล (%)", "คะแนน PLO เฉลี่ย (%)", "บรรลุ (คน)",
        "ร้อยละที่บรรลุ", "สถานะ",
    ]
    _header_row(ws, 1, headers)

    rows = compute_plo_summary_rows(db, curriculum_id, result, target_rate)
    row_idx = 2
    for row in rows:
        values = [
            row.plo_code, row.category, row.description, row.course_count, row.clo_count,
            row.total_students, row.student_count_with_data, row.coverage_percent,
            row.average_achieved_percent if row.average_achieved_percent is not None else "-",
            row.achieved_student_count,
            row.achieved_rate_percent if row.achieved_rate_percent is not None else "-",
            row.status,
        ]
        for col, value in enumerate(values, start=1):
            cell = ws.cell(row=row_idx, column=col, value=value)
            cell.font = BASE_FONT
            cell.alignment = WRAP_ALIGNMENT
            if row.status == "ไม่บรรลุ":
                cell.fill = NOT_ACHIEVED_FILL
            elif row.status == "ยังไม่มี CLO ผูก":
                cell.fill = NO_CLO_LINKED_FILL
        row_idx += 1

    footer_row = row_idx + 1
    ws.cell(row=footer_row, column=1, value="นักศึกษาที่บรรลุ PLO ครบทุกข้อ").font = BOLD_FONT
    all_achieved_percent_display = (
        f"{result.all_plo_achieved_percent}%" if result.all_plo_achieved_percent is not None else "-"
    )
    ws.cell(
        row=footer_row, column=2,
        value=(
            f"{result.all_plo_achieved_count} คน ({all_achieved_percent_display}) "
            f"จาก {result.all_plo_data_complete_count} คนที่มีข้อมูลครบทุก PLO"
        ),
    ).font = BOLD_FONT
    note_cell = ws.cell(
        row=footer_row + 1, column=1,
        value=(
            f"หมายเหตุ: นับเฉพาะ {result.qualifying_plo_count} จาก {result.total_plo_count} ข้อที่มี "
            "CLO ผูกอยู่จริง (PLO ที่ยังไม่มี CLO ผูกเป็นไปไม่ได้ที่จะบรรลุอยู่แล้วโดยดีไซน์) ตัวหารคือ "
            "นักศึกษาที่มีข้อมูลครบทุก PLO ที่นับ ไม่ใช่นักศึกษาทั้งหมด (คนที่ยังไม่มีข้อมูลของ PLO ข้อใด"
            "ข้อหนึ่งยังตัดสินไม่ได้ว่าบรรลุครบจริงหรือไม่)"
        ),
    )
    note_cell.font = BASE_FONT
    note_cell.alignment = WRAP_ALIGNMENT
    ws.merge_cells(start_row=footer_row + 1, start_column=1, end_row=footer_row + 1, end_column=len(headers))

    _autofit_columns(ws, [10, 16, 32, 14, 12, 14, 10, 18, 16, 10, 14, 16])
    _freeze_and_filter(ws, header_row=1, last_row=row_idx - 1, last_col=len(headers))


def _map_cell_text_and_fill(cell) -> tuple[str, PatternFill | None]:
    if cell.mismatch == "no_clo":
        return "ไม่มี CLO", MISMATCH_NO_CLO_FILL
    if cell.mismatch == "no_course_plo":
        return str(cell.clo_count), MISMATCH_NO_COURSE_PLO_FILL
    if cell.clo_count == 0:
        return "", None
    symbol = "●" if cell.responsibility == "primary" else "○"
    return f"{symbol} {cell.clo_count}", None


def _build_sheet_curriculum_map(
    wb: Workbook, db: Session, curriculum_id: int, cohort_year: int | None, plos: list[PLO]
) -> None:
    ws = wb.create_sheet("แผนที่หลักสูตร PLO×รายวิชา")
    headers = ["รหัสวิชา", "ชื่อวิชา", "หน่วยกิต", "ชั้นปี", "ภาค"] + [p.code for p in plos] + ["จำนวน PLO ต่อวิชา"]
    _header_row(ws, 1, headers)

    result = compute_curriculum_map(db, curriculum_id, cohort_year, plos)
    row_idx = 2
    for row in result.rows:
        base_values = [
            row.course_code, row.name_th, row.credit,
            row.year_level if row.year_level is not None else "-",
            row.semester if row.semester is not None else "-",
        ]
        for col, value in enumerate(base_values, start=1):
            cell = ws.cell(row=row_idx, column=col, value=value)
            cell.font = BASE_FONT
            cell.alignment = WRAP_ALIGNMENT if col == 2 else CENTER_ALIGNMENT

        for offset, plo in enumerate(plos):
            plo_cell = row.cells[plo.id]
            text, fill = _map_cell_text_and_fill(plo_cell)
            cell = ws.cell(row=row_idx, column=6 + offset, value=text or None)
            cell.font = BASE_FONT
            cell.alignment = CENTER_ALIGNMENT
            if fill is not None:
                cell.fill = fill

        last_col = 6 + len(plos)
        count_cell = ws.cell(row=row_idx, column=last_col, value=row.plo_count)
        count_cell.font = BASE_FONT
        count_cell.alignment = CENTER_ALIGNMENT
        row_idx += 1

    footer_row = row_idx
    ws.cell(row=footer_row, column=1, value="จำนวนวิชาต่อ PLO").font = BOLD_FONT
    for offset, plo in enumerate(plos):
        cell = ws.cell(row=footer_row, column=6 + offset, value=result.course_count_by_plo.get(plo.id, 0))
        cell.font = BOLD_FONT
        cell.alignment = CENTER_ALIGNMENT

    note_row = footer_row + 2
    ws.cell(row=note_row, column=1, value=result.study_plan_note).font = BASE_FONT
    ws.cell(
        row=note_row + 1, column=1,
        value="สัญลักษณ์: ● = วิชาหลัก (primary), ○ = วิชารอง (secondary), ตัวเลข = จำนวน CLO ที่ผูกกับ PLO นั้น",
    ).font = BASE_FONT
    ws.cell(
        row=note_row + 2, column=1,
        value="สีเหลือง = course_plo ระบุว่าเป็นวิชาหลัก/รองของ PLO นี้ แต่ไม่มี CLO ผูกจริงเลย",
    ).font = BASE_FONT
    ws.cell(row=note_row + 2, column=1).fill = MISMATCH_NO_CLO_FILL
    ws.cell(
        row=note_row + 3, column=1,
        value="สีส้ม = มี CLO ผูกกับ PLO นี้จริงในระบบ แต่ไม่มีแถวระบุไว้ใน course_plo (แผนที่หลักสูตร)",
    ).font = BASE_FONT
    ws.cell(row=note_row + 3, column=1).fill = MISMATCH_NO_COURSE_PLO_FILL

    widths = [14, 32, 10, 8, 8] + [8] * len(plos) + [16]
    _autofit_columns(ws, widths)
    _freeze_and_filter(ws, header_row=1, last_row=row_idx - 1, last_col=len(headers))


def _build_sheet_clo_plo_weights(wb: Workbook, db: Session, curriculum_id: int, plos: list[PLO]) -> None:
    ws = wb.create_sheet("CLO×PLO (น้ำหนัก)")
    headers = ["รหัสวิชา", "ชื่อวิชา", "CLO", "คำอธิบาย CLO"] + [p.code for p in plos]
    _header_row(ws, 1, headers)

    rows = compute_clo_plo_weight_rows(db, curriculum_id)
    row_idx = 2
    for row in rows:
        base_values = [row.course_code, row.course_name, row.clo_code, row.clo_description]
        for col, value in enumerate(base_values, start=1):
            cell = ws.cell(row=row_idx, column=col, value=value)
            cell.font = BASE_FONT
            cell.alignment = WRAP_ALIGNMENT

        for offset, plo in enumerate(plos):
            weight = row.weights.get(plo.id)
            cell = ws.cell(row=row_idx, column=5 + offset, value=float(weight) if weight is not None else None)
            cell.font = BASE_FONT
            cell.alignment = CENTER_ALIGNMENT
        row_idx += 1

    widths = [14, 28, 10, 32] + [8] * len(plos)
    _autofit_columns(ws, widths)
    _freeze_and_filter(ws, header_row=1, last_row=row_idx - 1, last_col=len(headers))


def _build_sheet_traceability(
    wb: Workbook, db: Session, curriculum_id: int, result: CurriculumPLOAchievement
) -> None:
    ws = wb.create_sheet("ย้อนรอยการคำนวณ")
    headers = [
        "PLO", "รหัสวิชา", "CLO", "น้ำหนัก (%)", "สัดส่วนน้ำหนักใน PLO นี้ (%)",
        "จำนวน นศ. ที่มีคะแนน", "CLO mastery เฉลี่ย (%)", "จำนวนที่ผ่านเกณฑ์ CLO",
    ]
    _header_row(ws, 1, headers)

    rows = compute_traceability_rows(db, curriculum_id, result)
    row_idx = 2
    for row in rows:
        values = [
            row.plo_code, row.course_code, row.clo_code, float(row.weight_percent),
            float(row.weight_share_percent), row.students_with_score,
            float(row.average_mastery_percent) if row.average_mastery_percent is not None else "-",
            row.passed_count,
        ]
        for col, value in enumerate(values, start=1):
            cell = ws.cell(row=row_idx, column=col, value=value)
            cell.font = BASE_FONT
            cell.alignment = CENTER_ALIGNMENT if col != 3 else WRAP_ALIGNMENT
        row_idx += 1

    _autofit_columns(ws, [10, 14, 12, 12, 22, 18, 20, 18])
    _freeze_and_filter(ws, header_row=1, last_row=row_idx - 1, last_col=len(headers))


def _build_sheet_cohort_comparison(
    wb: Workbook, db: Session, curriculum_id: int, cohort_years: list[int]
) -> None:
    ws = wb.create_sheet("เปรียบเทียบรายรุ่น")
    comparison = compute_cohort_comparison(db, curriculum_id, cohort_years)

    headers = ["PLO", "คำอธิบาย"]
    for year in cohort_years:
        count = comparison.student_count_by_cohort.get(year, 0)
        headers.append(f"รุ่น {year} ({count} คน) - คะแนนเฉลี่ย (%)")
        headers.append(f"รุ่น {year} ({count} คน) - ร้อยละที่บรรลุ (%)")
        headers.append(f"รุ่น {year} ({count} คน) - จำนวนผู้มีข้อมูล")
    _header_row(ws, 1, headers)

    row_idx = 2
    for row in comparison.rows:
        ws.cell(row=row_idx, column=1, value=row.plo_code).font = BASE_FONT
        desc_cell = ws.cell(row=row_idx, column=2, value=row.description)
        desc_cell.font = BASE_FONT
        desc_cell.alignment = WRAP_ALIGNMENT

        col = 3
        for year in cohort_years:
            cell_data = row.per_cohort.get(year)
            avg_value = (
                cell_data.average_achieved_percent if cell_data and cell_data.average_achieved_percent is not None else "-"
            )
            avg_cell = ws.cell(row=row_idx, column=col, value=avg_value)
            avg_cell.font = BASE_FONT
            avg_cell.alignment = CENTER_ALIGNMENT
            rate_value = (
                cell_data.achieved_rate_percent if cell_data and cell_data.achieved_rate_percent is not None else "-"
            )
            rate_cell = ws.cell(row=row_idx, column=col + 1, value=rate_value)
            rate_cell.font = BASE_FONT
            rate_cell.alignment = CENTER_ALIGNMENT
            coverage_count_cell = ws.cell(
                row=row_idx, column=col + 2, value=cell_data.student_count_with_data if cell_data else 0
            )
            coverage_count_cell.font = BASE_FONT
            coverage_count_cell.alignment = CENTER_ALIGNMENT
            col += 3
        row_idx += 1

    widths = [10, 32] + [18, 18, 18] * len(cohort_years)
    _autofit_columns(ws, widths)
    _freeze_and_filter(ws, header_row=1, last_row=row_idx - 1, last_col=len(headers))


def _build_sheet_personal(wb: Workbook, db: Session, result: CurriculumPLOAchievement, plos: list[PLO]) -> None:
    ws = wb.create_sheet("รายบุคคล")
    ws.cell(row=1, column=1, value="ข้อมูลส่วนบุคคล — ใช้ภายในสาขาเท่านั้น").font = BOLD_FONT

    header_row = 3
    headers = ["รหัสนักศึกษา", "ชื่อ-สกุล", "รุ่น"] + [p.code for p in plos] + ["จำนวน PLO ที่บรรลุ"]
    _header_row(ws, header_row, headers)

    rows = compute_personal_rows(db, result)
    row_idx = header_row + 1
    for row in rows:
        ws.cell(row=row_idx, column=1, value=row.student_id).font = BASE_FONT
        ws.cell(row=row_idx, column=2, value=row.student_name).font = BASE_FONT
        ws.cell(row=row_idx, column=3, value=row.cohort_year if row.cohort_year is not None else "-").font = BASE_FONT

        for offset, plo in enumerate(plos):
            has_data = row.plo_has_data.get(plo.id, False)
            percent = row.plo_percents.get(plo.id, 0.0)
            cell = ws.cell(row=row_idx, column=4 + offset)
            cell.font = BASE_FONT
            cell.alignment = CENTER_ALIGNMENT
            if not has_data:
                cell.value = "-"
            else:
                cell.value = percent
                if percent < 60:
                    cell.fill = FAIL_FILL

        last_col = 4 + len(plos)
        ws.cell(row=row_idx, column=last_col, value=row.achieved_count).font = BASE_FONT
        row_idx += 1

    widths = [16, 26, 8] + [8] * len(plos) + [16]
    _autofit_columns(ws, widths)
    _freeze_and_filter(ws, header_row=header_row, last_row=row_idx - 1, last_col=len(headers))


def build_plo_report_excel(
    db: Session,
    result: CurriculumPLOAchievement,
    curriculum_id: int,
    cohort_year: int | None,
    target_rate: Decimal,
    include_personal_sheet: bool,
    exported_by: str,
) -> BytesIO:
    """ทำอะไร : สร้าง workbook ครบ 7 ชีต (6 ถ้า include_personal_sheet=False, ตัดชีตเปรียบเทียบรายรุ่น
    ออกถ้าระบุ cohort_year มา - เหลือ 5/4 ชีตตามลำดับ) แล้วคืนเป็น BytesIO พร้อมส่งเป็น StreamingResponse
    - result มาจาก compute_cohort_plo_achievement() ตัวเดียวกับ GET /plo/achievement/cohort เป๊ะ (ไม่
    คำนวณ PLO summary ซ้ำ)"""
    plos = db.query(PLO).filter(PLO.curriculum_id == curriculum_id).order_by(PLO.code).all()
    has_cohort_comparison = cohort_year is None and len(result.available_cohort_years) > 0

    curriculum = db.get(Curriculum, curriculum_id)

    wb = Workbook()
    _build_sheet_explanation(
        wb, curriculum, cohort_year, result.total_students, target_rate, exported_by,
        has_cohort_comparison,
    )
    _build_sheet_plo_summary(wb, db, curriculum_id, result, target_rate)
    _build_sheet_curriculum_map(wb, db, curriculum_id, cohort_year, plos)
    _build_sheet_clo_plo_weights(wb, db, curriculum_id, plos)
    _build_sheet_traceability(wb, db, curriculum_id, result)
    if has_cohort_comparison:
        _build_sheet_cohort_comparison(wb, db, curriculum_id, result.available_cohort_years)
    if include_personal_sheet:
        _build_sheet_personal(wb, db, result, plos)

    buffer = BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return buffer
