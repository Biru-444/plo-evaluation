"""API routes for importing official university Excel roster files (.xls/.xlsx).

ไฟล์ที่มหาวิทยาลัยส่งให้อาจารย์เป็นไฟล์ Excel รูปแบบเก่า (.xls, binary "CDFV2 Microsoft Excel"
ไม่ใช่ .xlsx) มีโครงสร้างคงที่: หัวเรื่องมหาวิทยาลัย, บรรทัด "ภาคการศึกษา n/pppp", บรรทัด
"รหัสวิชา <code> <ชื่อวิชา> หน่วยกิต <n> Sec <section>", บรรทัด "ผู้สอน <ชื่อ1>[, <ชื่อ2>, ...]",
ตามด้วยตารางรายชื่อที่มีหัวคอลัมน์ "เลขที่ / รหัสประจำตัว / ชื่อ / คะแนน / สัปดาห์..."

แทนที่จะอิงตำแหน่งแถว/คอลัมน์ตายตัว (ซึ่งขยับได้ 1 แถวถ้า "วันเวลาเรียน" มี 1 หรือ 2 บรรทัด) โค้ดนี้
สแกนหาข้อความ/หัวคอลัมน์ที่รู้จักในทุกเซลล์แทน เพื่อให้ทนทานต่อความต่างเล็กน้อยระหว่างไฟล์แต่ละรุ่น
(ตรวจสอบกับไฟล์จริง 5 ไฟล์ คนละรุ่น/section/ภาคเรียนแล้ว)

หลักการ import (ตามที่ผู้ใช้ยืนยัน):
- ไฟล์คือความจริง (authoritative) — ถ้านักศึกษามีอยู่แล้วแต่ชื่อในไฟล์ไม่ตรงกับในระบบ ให้แก้ตามไฟล์
- ค่า Sec ในไฟล์ = student.section ของนักศึกษาทุกคนในไฟล์นั้น (หมู่ประจำตัว ไม่ใช่ของวิชา) — ถ้าคนคนนั้น
  เคยถูกเซ็ตหมู่จากไฟล์วิชาอื่นไว้ก่อนแล้วค่าไม่ตรงกัน ให้ไฟล์ที่ import ล่าสุดทับค่าเดิมเสมอ (หลักการเดียวกับชื่อ)
- ถ้ายังไม่มี course_offering ตรงกับวิชา/ปีการศึกษา/ภาคเรียน/section ในไฟล์ ให้สร้างให้อัตโนมัติ
- ถ้าชื่อผู้สอนในไฟล์ไม่ตรงกับ user ในระบบ ให้สร้างบัญชีอาจารย์จริงให้เลย (username รูปแบบ
  "ajarn<id>" + รหัสผ่านชั่วคราวสุ่ม แสดงครั้งเดียวตอนสร้าง - เหมือน ajarn.somsak/ajarn.suda ที่มีอยู่
  แต่ไม่มีวิธี transliterate ชื่อไทยเป็นอังกฤษได้แม่นยำอัตโนมัติ จึงใช้ id เป็นส่วนต่อท้ายแทน)
- รายวิชา (Course) ต้องมีอยู่ในระบบก่อนแล้วเท่านั้น (import จะไม่สร้างรายวิชาใหม่) - ถ้าไม่เจอ **ไม่ใช่
  error ที่หยุดทั้งไฟล์อีกต่อไป** (เปลี่ยนตามที่ผู้ใช้ระบุ 2026-09-27) จะนำเข้าเฉพาะรายชื่อนักศึกษา
  (สร้าง/อัปเดตตามปกติ) ข้ามผู้สอน/course_offering/enrollment ทั้งหมด - ต้องมี `curriculum_id` (form
  field ใหม่ เลือกเองจากฟอร์ม เพราะปกติได้จาก course.curriculum_id) ก่อนถึงจะ commit ได้จริง (422 ถ้าไม่มี
  ตอน commit - ดู needs_curriculum_id ใน response และ offering_action == "skipped_no_course")

รองรับ 2 โหมดในการเรียกเดียวกัน ผ่าน form field `dry_run`:
- `dry_run=true` (ค่าเริ่มต้น): parse + คำนวณผลลัพธ์ที่ *จะ* เกิดขึ้น แต่ rollback ไม่บันทึกจริง
  ใช้แสดง preview ให้ผู้ใช้ตรวจสอบก่อน
- `dry_run=false`: บันทึกจริงทั้งหมด (สร้าง/แก้ course_offering, user, student, enrollment)
"""
from __future__ import annotations

import io
import re
import secrets
from collections import Counter
from dataclasses import dataclass

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from openpyxl import load_workbook
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import hash_password, require_role
from app.database import get_db
from app.models import Course, CourseOffering, Curriculum, Enrollment, Student, User
from app.schemas import RosterImportInstructor, RosterImportResponse, RosterImportStudentRow

router = APIRouter(prefix="/roster-import", tags=["Roster Import"])

STUDENT_TITLES = ["นางสาว", "นาย", "นาง"]  # เช็ค "นางสาว" ก่อน "นาง" เพราะ "นาง" เป็นคำนำหน้าของ "นางสาว"
ENGLISH_TITLE_RE = re.compile(r"^(Mr|Mrs|Ms|Miss)\.?\s*", re.IGNORECASE)
SEMESTER_RE = re.compile(r"ภาคการศึกษา\s*(\d+)\s*/\s*(\d+)")
COURSE_LINE_RE = re.compile(r"รหัสวิชา\s+(\S+)\s+(.+?)\s+หน่วยกิต\s+\S+\s+Sec\s+(\S+)")


class RosterParseError(Exception):
    """ไฟล์ไม่ตรงรูปแบบที่คาดไว้ - ส่งเป็น HTTP 400 กลับให้ผู้ใช้"""


# ผลลัพธ์การ parse ไฟล์ .xls/.xlsx ของมหาวิทยาลัยแล้ว (ยังไม่บันทึกอะไรลงฐานข้อมูล) — ส่งต่อให้
# _apply_roster_import ตัดสินใจว่าจะสร้าง/แก้ไขอะไรบ้าง (ทั้งโหมด dry-run และ commit ใช้ dataclass
# เดียวกันนี้)
@dataclass
class ParsedRoster:
    course_code: str
    course_name: str
    section: str
    academic_year: int
    semester: int
    cohort_year: int | None
    instructor_names: list[str]
    students: list[tuple[str, str | None, str, str]]  # (student_id, title, first_name, last_name)


def _cellstr(value) -> str:
    if value is None or value == "":
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def _load_xls_workbook(content: bytes):
    """xlrd's own OLE2 (compound document) reader is stricter than real Excel about
    the sector-chain layout, and some genuine files (observed from the university's
    export tool) fail with `IndexError` inside xlrd's compdoc even though Excel opens
    them fine and `olefile` (a more tolerant standalone OLE2 reader) reads them with
    zero issues. Fall back to extracting the raw 'Workbook'/'Book' BIFF stream with
    olefile and handing those bytes to xlrd directly - xlrd accepts a raw BIFF stream
    (no OLE2 signature) and skips its own compdoc parsing entirely in that case."""
    import xlrd

    try:
        return xlrd.open_workbook(file_contents=content)
    except Exception:
        pass

    try:
        import olefile
    except ImportError as exc:  # pragma: no cover - ต้องติดตั้ง olefile บนเซิร์ฟเวอร์จริง
        raise RosterParseError(
            "ไฟล์ .xls นี้เปิดด้วยวิธีปกติไม่ได้ และเซิร์ฟเวอร์ไม่มีไลบรารีสำรอง (olefile) - กรุณาติดต่อผู้ดูแลระบบ"
        ) from exc

    try:
        ole = olefile.OleFileIO(io.BytesIO(content))
        try:
            stream_name = "Workbook" if ole.exists("Workbook") else "Book"
            stream_bytes = ole.openstream(stream_name).read()
        finally:
            ole.close()
        return xlrd.open_workbook(file_contents=stream_bytes)
    except Exception as exc:
        raise RosterParseError(
            "ไฟล์ .xls นี้เปิดไม่ได้ (โครงสร้างไฟล์เสียหายหรือไม่ตรงรูปแบบ) - "
            "ลองเปิดไฟล์นี้ด้วย Excel แล้ว \"บันทึกเป็น\" ใหม่ (.xls หรือ .xlsx) แล้วอัปโหลดไฟล์ที่บันทึกใหม่แทน"
        ) from exc


def _load_rows(filename: str, content: bytes) -> list[list]:
    lower_name = filename.lower()
    if lower_name.endswith(".xls"):
        try:
            import xlrd  # noqa: F401  (สำหรับเช็คว่าติดตั้งไว้หรือยัง ก่อนเข้า _load_xls_workbook)
        except ImportError as exc:  # pragma: no cover - ต้องติดตั้ง xlrd บนเซิร์ฟเวอร์จริง
            raise RosterParseError(
                "เซิร์ฟเวอร์ยังไม่ได้ติดตั้งไลบรารีสำหรับอ่านไฟล์ .xls (xlrd) - กรุณาติดต่อผู้ดูแลระบบ"
            ) from exc
        book = _load_xls_workbook(content)
        sheet = book.sheet_by_index(0)
        return [[sheet.cell_value(r, c) for c in range(sheet.ncols)] for r in range(sheet.nrows)]
    if lower_name.endswith(".xlsx"):
        workbook = load_workbook(io.BytesIO(content), read_only=True, data_only=True)
        worksheet = workbook.active
        return [list(row) for row in worksheet.iter_rows(values_only=True)]
    raise RosterParseError("รองรับเฉพาะไฟล์ .xls หรือ .xlsx เท่านั้น (ไฟล์ที่มหาวิทยาลัยส่งให้ปกติเป็น .xls)")


def split_student_name(raw: str) -> tuple[str | None, str, str]:
    """แยกคำนำหน้า/ชื่อ/นามสกุลจากชื่อนักศึกษา เช่น 'นายกฤษณะ  เข็มมา' หรือ 'Mr.Socheat  Moeun'
    ชื่อ-นามสกุลคั่นด้วยช่องว่าง 2 ตัวขึ้นไปเสมอ (ยืนยันจากไฟล์จริง 5 ไฟล์)"""
    s = raw.strip()
    title: str | None = None
    for t in STUDENT_TITLES:
        if s.startswith(t):
            title = t
            s = s[len(t):]
            break
    if title is None:
        m = ENGLISH_TITLE_RE.match(s)
        if m:
            title = m.group(1) + "."
            s = s[m.end():]
    s = s.strip()
    parts = re.split(r"\s{2,}", s)
    if len(parts) >= 2 and parts[0] and parts[1]:
        first, last = parts[0].strip(), " ".join(parts[1:]).strip()
    else:
        tokens = s.split()
        if len(tokens) >= 2:
            first, last = tokens[0], " ".join(tokens[1:])
        else:
            first, last = s, ""
    return title, first, last


def split_instructor_name(raw: str) -> tuple[str | None, str, str]:
    """แยกคำนำหน้า/ชื่อ/นามสกุลจากชื่อผู้สอน เช่น 'อาจารย์ ชลัท รังสิมาเทวัญ' หรือ
    'ผู้ช่วยศาสตราจารย์ ดร. สมศักดิ์ จีวัฒนา' - คั่นด้วยช่องว่างเดียว 2 คำสุดท้ายคือชื่อ-นามสกุล
    ที่เหลือด้านหน้าคือคำนำหน้า (รองรับคำนำหน้ายศวิชาการยาวกี่คำก็ได้)"""
    tokens = raw.strip().split()
    if len(tokens) >= 3:
        first, last = tokens[-2], tokens[-1]
        title = " ".join(tokens[:-2])
    elif len(tokens) == 2:
        title, first, last = None, tokens[0], tokens[1]
    elif len(tokens) == 1:
        title, first, last = None, tokens[0], ""
    else:
        title, first, last = None, "", ""
    return title, first, last


# ทำอะไร : อ่านไฟล์ดิบ (.xls/.xlsx) แล้วสแกนหาข้อมูลที่ต้องใช้ทั้งหมดด้วยการจับคู่ข้อความ/หัวคอลัมน์ที่
# รู้จัก (ไม่อิงตำแหน่งแถว/คอลัมน์ตายตัว — ดูเหตุผลในหัว docstring ของไฟล์นี้): ภาคการศึกษา/ปีการศึกษา
# (SEMESTER_RE), รหัสวิชา/ชื่อวิชา/section (COURSE_LINE_RE), รายชื่อผู้สอน (บรรทัดที่ขึ้นต้น "ผู้สอน"),
# และตารางรายชื่อนักศึกษา (หาแถวหัวตารางที่มีทั้ง "เลขที่" และ "รหัสประจำตัว") รุ่นนักศึกษา
# (cohort_year) เดาจาก 2 ตัวแรกของรหัสนักศึกษาที่พบมากที่สุดในไฟล์ (เผื่อมีนักศึกษาซ้ำชั้นปนมาบ้าง)
# ถ้าแก้ : โยน RosterParseError (กลายเป็น HTTP 400) ทันทีที่หาข้อมูลที่จำเป็นไม่เจอ แทนที่จะเดาต่อแบบ
# เงียบ ๆ เพื่อไม่ให้นำเข้าข้อมูลผิดโดยไม่รู้ตัว
def parse_roster_xls(filename: str, content: bytes) -> ParsedRoster:
    rows = _load_rows(filename, content)
    rows = [row for row in rows if row]
    if not rows:
        raise RosterParseError("ไฟล์ว่างเปล่าหรืออ่านไม่ได้")

    semester = academic_year = None
    for row in rows:
        for cell in row:
            m = SEMESTER_RE.search(_cellstr(cell))
            if m:
                semester, academic_year = int(m.group(1)), int(m.group(2))
                break
        if semester is not None:
            break
    if semester is None:
        raise RosterParseError("ไม่พบข้อมูลภาคการศึกษา/ปีการศึกษาในไฟล์ (ต้องมีข้อความรูปแบบ 'ภาคการศึกษา n/pppp')")

    course_code = course_name = section = None
    course_row_idx = None
    for idx, row in enumerate(rows):
        for cell in row:
            m = COURSE_LINE_RE.search(_cellstr(cell))
            if m:
                course_code, course_name, section = m.group(1).strip(), m.group(2).strip(), m.group(3).strip()
                course_row_idx = idx
                break
        if course_code is not None:
            break
    if course_code is None:
        raise RosterParseError("ไม่พบข้อมูลรหัสวิชา/Section ในไฟล์ (ต้องมีข้อความขึ้นต้นด้วย 'รหัสวิชา')")

    instructor_names: list[str] = []
    search_rows = rows[course_row_idx:course_row_idx + 4] if course_row_idx is not None else rows
    for row in search_rows:
        for cell in row:
            s = _cellstr(cell)
            if s.startswith("ผู้สอน"):
                raw = s[len("ผู้สอน"):].strip()
                instructor_names = [p.strip() for p in raw.split(",") if p.strip()]
                break
        if instructor_names:
            break

    header_row_idx = None
    id_col = name_col = None
    for idx, row in enumerate(rows):
        cells = [_cellstr(c) for c in row]
        if "เลขที่" in cells and "รหัสประจำตัว" in cells:
            header_row_idx = idx
            id_col = cells.index("รหัสประจำตัว")
            name_col = cells.index("ชื่อ") if "ชื่อ" in cells else None
            break
    if header_row_idx is None or name_col is None:
        raise RosterParseError("ไม่พบหัวตารางรายชื่อนักศึกษา (คอลัมน์ 'เลขที่ / รหัสประจำตัว / ชื่อ')")

    students: list[tuple[str, str | None, str, str]] = []
    seen_ids: set[str] = set()
    started = False
    for row in rows[header_row_idx + 1:]:
        sid = _cellstr(row[id_col]) if id_col < len(row) else ""
        if sid.isdigit() and len(sid) >= 8:
            started = True
            if sid in seen_ids:
                continue
            seen_ids.add(sid)
            name_raw = _cellstr(row[name_col]) if name_col < len(row) else ""
            title, first, last = split_student_name(name_raw)
            students.append((sid, title, first, last))
        elif started:
            break

    if not students:
        raise RosterParseError("ไม่พบรายชื่อนักศึกษาในไฟล์")

    prefixes = [sid[:2] for sid, *_ in students if sid[:2].isdigit()]
    cohort_year = int(Counter(prefixes).most_common(1)[0][0]) if prefixes else None

    return ParsedRoster(
        course_code=course_code,
        course_name=course_name,
        section=section,
        academic_year=academic_year,
        semester=semester,
        cohort_year=cohort_year,
        instructor_names=instructor_names,
        students=students,
    )


# ทำอะไร : นำผล parse (ParsedRoster) ไปเทียบกับข้อมูลที่มีอยู่จริงในฐานข้อมูล แล้วตัดสินใจทีละส่วน
# (ผู้สอน -> course_offering -> นักศึกษา -> การลงทะเบียน) ว่าแต่ละอย่าง "มีอยู่แล้ว"/"จะสร้างใหม่"/
# "จะแก้ไข" — commit=False (dry-run) รันตรรกะเดียวกันทั้งหมดแต่ไม่ db.add()/ไม่ db.commit() จริง (แค่
# คำนวณว่า "จะ" เกิดอะไรขึ้น) commit=True คือบันทึกจริงทุกอย่าง
#
# ถ้าไม่พบวิชาในระบบ (course is None): นำเข้าเฉพาะรายชื่อนักศึกษาเท่านั้น (สร้าง/อัปเดตตามปกติ) ข้าม
# ผู้สอน/course_offering/enrollment ไปทั้งหมด (ไม่มีอะไรให้ผูก) - ต้องรู้ curriculum_id ของนักศึกษาแทนที่
# จะได้จาก course.curriculum_id ตามปกติ รับจาก parameter `curriculum_id` ที่ผู้ใช้เลือกเองในฟอร์ม (ตรวจว่า
# มีอยู่จริงก่อนเสมอ - 422 ถ้าไม่มี/ไม่ถูกต้อง ตอน commit=True เท่านั้น dry-run ยังพรีวิวได้แม้ไม่ระบุ
# curriculum_id มา แค่ข้ามการเช็คหลักสูตรซ้ำของนักศึกษาเดิมไปก่อน - ดู needs_curriculum_id ใน response)
#
# เชื่อมกับ : ใช้ pg_insert().on_conflict_do_nothing() บันทึกการลงทะเบียนแบบ bulk เหมือน
# enrollment.py (กันซ้ำแบบ atomic) — ทุก error ที่ไม่ถึงขั้นทำให้ import ทั้งไฟล์ล้มเหลว (เช่น
# นักศึกษาคนหนึ่งอยู่คนละหลักสูตร) จะถูกเก็บใน errors/action="error" ต่อแถว ไม่ throw exception ทันที
# ถ้าแก้ : ต้อง db.flush() นักศึกษาที่เพิ่ง add() ก่อน bulk insert enrollment เสมอ (ดูคอมเมนต์ในโค้ด
# ด้านล่าง) ไม่งั้นจะชน foreign key constraint เพราะแถว student ยังไม่มีอยู่จริงในตาราง
def _apply_roster_import(
    db: Session, parsed: ParsedRoster, commit: bool, curriculum_id: int | None = None
) -> RosterImportResponse:
    errors: list[str] = []

    courses = (
        db.query(Course)
        .join(Curriculum)
        .filter(Course.course_code == parsed.course_code)
        .order_by(Curriculum.is_active.desc(), Course.id)
        .all()
    )
    course = courses[0] if courses else None
    if course is None:
        errors.append(
            f"ไม่พบวิชารหัส {parsed.course_code} ในระบบ - ระบบนี้ไม่สร้างรายวิชาใหม่อัตโนมัติ จะนำเข้าเฉพาะ"
            f"รายชื่อนักศึกษาเท่านั้น (ไม่สร้างวิชา/การเปิดสอน/ลงทะเบียนให้) กรุณาสร้างวิชา "
            f"'{parsed.course_code} {parsed.course_name}' เองภายหลังแล้วลงทะเบียนนักศึกษาแยกต่างหาก"
        )
    elif len(courses) > 1:
        errors.append(
            f"พบวิชารหัส {parsed.course_code} มากกว่า 1 หลักสูตรในระบบ - เลือกหลักสูตร "
            f"'{course.curriculum.name}' (id={course.curriculum_id}) ให้อัตโนมัติเพราะเป็นหลักสูตรที่ active อยู่"
        )

    resolved_curriculum: Curriculum | None = None
    if course is None:
        if curriculum_id is not None:
            resolved_curriculum = db.get(Curriculum, curriculum_id)
            if resolved_curriculum is None:
                raise HTTPException(status_code=422, detail="ไม่พบหลักสูตรนี้ในระบบ")
        elif commit:
            raise HTTPException(
                status_code=422,
                detail="ต้องระบุหลักสูตรของนักศึกษาก่อนนำเข้าจริง (ไม่พบวิชานี้ในระบบ ระบบจึงไม่ทราบว่า"
                "นักศึกษาอยู่หลักสูตรไหน)",
            )
    # curriculum_id ที่จะใช้สร้าง/เทียบนักศึกษาจริง - course.curriculum_id เป็นหลักเสมอถ้ามีวิชา (ห้ามใช้
    # curriculum_id ที่ผู้ใช้ส่งมาแทนแม้จะส่งมาด้วยก็ตาม - พฤติกรรมตอนมีวิชาต้องเหมือนเดิมทุกประการ) ไม่งั้น
    # ใช้ curriculum_id ที่ resolve แล้ว (อาจเป็น None ถ้ายังไม่ได้ระบุตอน dry-run)
    target_curriculum_id = course.curriculum_id if course is not None else (
        resolved_curriculum.id if resolved_curriculum is not None else None
    )

    # --- ผู้สอน --- ข้ามทั้งหมดถ้าไม่มีวิชา (ไม่มี course_offering ให้ผูกผู้สอนอยู่ดี)
    instructor_results: list[RosterImportInstructor] = []
    primary_instructor_id: int | None = None
    created_credentials: list[dict] = []
    for idx, raw_name in enumerate(parsed.instructor_names if course is not None else []):
        title, first, last = split_instructor_name(raw_name)
        existing = db.query(User).filter(User.first_name == first, User.last_name == last).first()
        if existing:
            entry = RosterImportInstructor(
                full_name=raw_name, title=title, action="matched_existing",
                user_id=existing.id, username=existing.username,
            )
            if idx == 0:
                primary_instructor_id = existing.id
        elif commit:
            temp_password = secrets.token_urlsafe(9)
            new_user = User(
                username="__pending__",
                password=hash_password(temp_password),
                first_name=first,
                last_name=last,
                role="instructor",
            )
            db.add(new_user)
            db.flush()
            new_user.username = f"ajarn{new_user.id}"
            db.flush()
            entry = RosterImportInstructor(
                full_name=raw_name, title=title, action="created",
                user_id=new_user.id, username=new_user.username, temp_password=temp_password,
            )
            created_credentials.append({
                "username": new_user.username,
                "temp_password": temp_password,
                "full_name": f"{(title + ' ') if title else ''}{first} {last}".strip(),
            })
            if idx == 0:
                primary_instructor_id = new_user.id
        else:
            entry = RosterImportInstructor(full_name=raw_name, title=title, action="will_create")
        instructor_results.append(entry)

    # --- course offering --- ข้ามทั้งหมดถ้าไม่มีวิชา (ห้ามสร้าง course_offering ตามที่ผู้ใช้ระบุ)
    offering = None
    offering_id: int | None
    if course is None:
        offering_action = "skipped_no_course"
        offering_id = None
    else:
        offering = (
            db.query(CourseOffering)
            .filter_by(
                course_id=course.id,
                academic_year=parsed.academic_year,
                semester=parsed.semester,
                section=parsed.section,
            )
            .first()
        )
        if offering:
            offering_action = "matched_existing"
            offering_id = offering.id
        elif commit:
            offering = CourseOffering(
                course_id=course.id,
                instructor_id=primary_instructor_id,
                cohort_year=parsed.cohort_year,
                academic_year=parsed.academic_year,
                semester=parsed.semester,
                section=parsed.section,
            )
            db.add(offering)
            db.flush()
            offering_action = "created"
            offering_id = offering.id
        else:
            offering_action = "will_create"
            offering_id = None

    # --- นักศึกษา ---
    student_rows: list[RosterImportStudentRow] = []
    to_enroll_ids: list[str] = []
    counts = {"create": 0, "update_info": 0, "unchanged": 0, "error": 0}
    for i, (sid, title, first, last) in enumerate(parsed.students, start=1):
        existing_student = db.get(Student, sid)
        if existing_student is None:
            row = RosterImportStudentRow(
                line_no=i, student_id=sid, title=title, first_name=first, last_name=last, action="create",
            )
            counts["create"] += 1
            if commit:
                # target_curriculum_id รับประกันว่าไม่ใช่ None ตอน commit=True เสมอ (422 ไปแล้วถ้าไม่มีวิชา
                # และไม่ได้ระบุ curriculum_id มา - ดูเช็คด้านบน)
                db.add(Student(
                    id=sid,
                    curriculum_id=target_curriculum_id,
                    first_name=first,
                    last_name=last,
                    title=title,
                    section=parsed.section,
                    cohort_year=parsed.cohort_year if parsed.cohort_year is not None else int(sid[:2]),
                    # current_year_level ไม่ใช่ column แล้ว - คำนวณสดจาก cohort_year เสมอ (ดู
                    # app/services/year_level.py / Student.current_year_level property)
                ))
            to_enroll_ids.append(sid)
        elif target_curriculum_id is not None and existing_student.curriculum_id != target_curriculum_id:
            row = RosterImportStudentRow(
                line_no=i, student_id=sid, title=title, first_name=first, last_name=last, action="error",
                detail=(
                    f"นักศึกษาคนนี้อยู่คนละหลักสูตร (curriculum_id="
                    f"{existing_student.curriculum_id} ไม่ตรงกับ {target_curriculum_id}) - ข้ามการลงทะเบียนให้ "
                    "กรุณาตรวจสอบด้วยตนเอง"
                ),
            )
            counts["error"] += 1
        else:
            name_changed = (
                existing_student.first_name != first
                or existing_student.last_name != last
                or (existing_student.title or None) != (title or None)
            )
            # ไฟล์นี้ผูกกับ course_offering เดียวที่มี section เดียว - นักศึกษาทุกคนในไฟล์นี้จึงได้ค่า
            # หมู่เดียวกัน ถ้าเคยถูกเซ็ตหมู่จากไฟล์อื่นมาก่อน (เช่นวิชาอื่น section ไม่ตรงกัน) ให้ไฟล์ที่
            # import ล่าสุดทับค่าเดิมเสมอ - ใช้หลักการเดียวกับชื่อ-นามสกุล (ไฟล์มหาวิทยาลัยถูกต้องกว่า)
            section_changed = existing_student.section != parsed.section
            if name_changed or section_changed:
                detail_parts = []
                if name_changed:
                    detail_parts.append(
                        f"ชื่อเดิมในระบบ: {existing_student.title or ''} {existing_student.first_name} "
                        f"{existing_student.last_name} -> ในไฟล์: {title or ''} {first} {last}"
                    )
                if section_changed:
                    detail_parts.append(
                        f"หมู่เดิมในระบบ: {existing_student.section or '(ไม่ระบุ)'} -> ในไฟล์: {parsed.section}"
                    )
                row = RosterImportStudentRow(
                    line_no=i, student_id=sid, title=title, first_name=first, last_name=last,
                    action="update_info",
                    detail=" | ".join(detail_parts),
                )
                counts["update_info"] += 1
                if commit:
                    existing_student.first_name = first
                    existing_student.last_name = last
                    existing_student.title = title
                    existing_student.section = parsed.section
            else:
                row = RosterImportStudentRow(
                    line_no=i, student_id=sid, title=title, first_name=first, last_name=last, action="unchanged",
                )
                counts["unchanged"] += 1
            to_enroll_ids.append(sid)
        student_rows.append(row)

    if commit:
        # นักศึกษาใหม่ที่เพิ่ง db.add() ไว้ข้างบนต้อง flush ลง DB ก่อน ไม่งั้น bulk insert
        # enrollment ด้านล่าง (Core insert ตรง ไม่ผ่าน ORM flush อัตโนมัติ) จะชน FK constraint
        # เพราะ student row ยังไม่มีอยู่จริงในตาราง
        db.flush()

    # --- ลงทะเบียนเรียน --- ไม่มีวิชา = ไม่มี offering ให้ลงทะเบียนเลย ไม่ว่าโหมดไหน (เช็ค course is None
    # ก่อนเสมอ ห้ามปล่อยให้ไหลลงไปเงื่อนไขด้านล่างที่เช็คแค่ offering_id is not None เพราะ commit=True กับ
    # offering_id=None พร้อมกันไม่เคยเกิดได้มาก่อน (ตอนมีวิชา offering ถูกสร้างเสมอ) จนกระทั่งเคสนี้)
    enrollments_added = 0
    enrollments_already = 0
    enrollments_skipped_no_course = 0
    if course is None:
        enrollments_skipped_no_course = len(to_enroll_ids)
    elif to_enroll_ids:
        if commit and offering_id is not None:
            already = {
                r[0]
                for r in db.query(Enrollment.student_id)
                .filter(Enrollment.offering_id == offering_id, Enrollment.student_id.in_(to_enroll_ids))
                .all()
            }
            to_insert = [sid for sid in to_enroll_ids if sid not in already]
            if to_insert:
                stmt = (
                    pg_insert(Enrollment.__table__)
                    .values([{"student_id": sid, "offering_id": offering_id} for sid in to_insert])
                    .on_conflict_do_nothing(index_elements=["student_id", "offering_id"])
                    .returning(Enrollment.__table__.c.student_id)
                )
                result = db.execute(stmt)
                enrollments_added = len(result.fetchall())
            enrollments_already = len(already)
        elif offering_id is not None:
            already = {
                r[0]
                for r in db.query(Enrollment.student_id)
                .filter(Enrollment.offering_id == offering_id, Enrollment.student_id.in_(to_enroll_ids))
                .all()
            }
            enrollments_already = len(already)
            enrollments_added = len(to_enroll_ids) - len(already)
        else:
            # dry-run กับ course_offering ที่ยังไม่มีจริง - ยังไม่มีใครลงทะเบียนได้เลย
            enrollments_added = len(to_enroll_ids)

    if commit:
        try:
            db.commit()
        except IntegrityError as exc:
            db.rollback()
            raise HTTPException(
                status_code=409, detail=f"นำเข้าไม่สำเร็จ - ข้อมูลขัดแย้งกันในฐานข้อมูล ({exc.orig})"
            ) from exc
        if offering is not None:
            db.refresh(offering)
            offering_id = offering.id
    else:
        db.rollback()

    summary = {
        "students_total": len(parsed.students),
        "students_create": counts["create"],
        "students_update_info": counts["update_info"],
        "students_unchanged": counts["unchanged"],
        "students_error": counts["error"],
        "enrollments_added": enrollments_added,
        "enrollments_already": enrollments_already,
        "enrollments_skipped_no_course": enrollments_skipped_no_course,
        "instructors_created": sum(1 for r in instructor_results if r.action == "created"),
        "instructors_will_create": sum(1 for r in instructor_results if r.action == "will_create"),
    }

    return RosterImportResponse(
        dry_run=not commit,
        course_code=parsed.course_code,
        course_name_th=course.name_th if course is not None else parsed.course_name,
        course_found=course is not None,
        academic_year=parsed.academic_year,
        semester=parsed.semester,
        section=parsed.section,
        cohort_year=parsed.cohort_year,
        offering_id=offering_id,
        offering_action=offering_action,
        needs_curriculum_id=course is None and resolved_curriculum is None,
        instructors=instructor_results,
        students=student_rows,
        enrollments_added=enrollments_added,
        enrollments_already=enrollments_already,
        summary=summary,
        new_instructor_credentials=created_credentials,
        errors=errors,
    )


@router.post("", response_model=RosterImportResponse)
async def import_roster(
    file: UploadFile = File(...),
    dry_run: bool = Form(True),
    curriculum_id: int | None = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("admin")),
):
    """นำเข้าไฟล์รายชื่อจากมหาวิทยาลัย (.xls/.xlsx) - admin เท่านั้น เพราะ endpoint นี้สร้างบัญชี
    ผู้ใช้ (อาจารย์) ใหม่ในระบบได้ ซึ่งเป็นสิทธิ์ระดับแอดมินทุกจุดในระบบนี้อยู่แล้ว (ดู users.py)
    เรียกด้วย dry_run=true ก่อนเพื่อดูตัวอย่างผลลัพธ์ แล้วค่อยเรียกซ้ำด้วย dry_run=false เพื่อบันทึกจริง

    `curriculum_id` (optional) จำเป็นเฉพาะตอนไม่พบวิชาในระบบ (ดู needs_curriculum_id ใน response) -
    ไม่มีผลอะไรเลยถ้าพบวิชา (ใช้ course.curriculum_id เสมอ ไม่ว่าจะส่ง curriculum_id มาด้วยหรือไม่)"""
    content = await file.read()
    try:
        parsed = parse_roster_xls(file.filename or "", content)
    except RosterParseError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return _apply_roster_import(db, parsed, commit=not dry_run, curriculum_id=curriculum_id)
