"""
ทำอะไร : คำนวณ "ชั้นปีปัจจุบัน" ของนักศึกษาสดจาก cohort_year ทุกครั้งที่เรียก แทนที่ Student.current_year_level
         column เดิมที่เคยเก็บค่าตายตัวไว้ตอน import แล้วไม่เคยอัปเดตอีกเลย (บั๊กจริงที่เจอ 2026-09-23 -
         นักศึกษาปี 1 ที่ import ไว้ตอนต้นปีจะค้างเป็นปี 1 ตลอดไปแม้ข้ามปีการศึกษาไปแล้วจริง ทำให้ตัวกรอง
         ชั้นปีและเงื่อนไข "เรียนถึงชั้นปีนี้แล้วหรือยัง" ใน ylo_calculation.py ผิดทั้งคู่)

         ตรรกะ cutoff เดือนมิถุนายนเหมือนกับ compute_year_level() เดิมใน roster_import.py ทุกประการ
         (ฟังก์ชันนั้นถูกลบไปแล้ว - ย้ายมารวมไว้จุดเดียวที่นี่ ใช้ทั้งตอน import และตอนอ่านค่าทุกจุด)

เชื่อมกับ : Student model (app/models/student.py) มี @property current_year_level/beyond_curriculum ที่
            เรียกฟังก์ชันนี้ตรงๆ (ให้ route/schema เดิมที่ใช้ from_attributes อ่าน student.current_year_level
            ทำงานเหมือนเดิมทุกที่โดยไม่ต้องแก้โค้ดผู้เรียก) ส่วนจุดที่กรองระดับ SQL (เช่น
            ylo_calculation.py::get_ylo_achievement_by_year) ใช้ min_cohort_year_for_level() แทน - กรองที่
            cohort_year ในฐานข้อมูลตรงๆ ไม่ต้องดึงนักศึกษาทุกคนมาคำนวณทีละคนในหน่วยความจำ

ถ้าแก้ : _today() มีไว้ให้เทสมี hook สำหรับ monkeypatch ("ตอนนี้" ของระบบ) โดยไม่ต้องพึ่ง freezegun หรือ
         แก้นาฬิกาเครื่องจริง - เทสที่ต้องการชั้นปีค่าใดค่าหนึ่งแน่นอน (ไม่ผูกกับวันที่รันจริง) ควรเรียก
         current_year_level(cohort_year, today=...) ตรงๆ แทนการ monkeypatch ก็ได้เช่นกัน

         level ต่ำกว่า 1 ยัง clamp ที่ 1 เหมือนโค้ดเดิม (ไม่มีความหมายเป็น "ปี 0"/ติดลบ) แต่ level เกิน 4
         ไม่ clamp ทิ้งแล้ว (ต่างจากโค้ดเดิมที่ clamp ไว้ที่ 4) - คืนเลขจริงพร้อม beyond_curriculum=True ให้
         ฝั่งที่เรียกใช้ (API response -> frontend) ตัดสินใจแสดงผลเอง (เช่น "ปี 4+")
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date


def _today() -> date:
    return date.today()


@dataclass(frozen=True)
class YearLevelResult:
    level: int
    beyond_curriculum: bool


def _buddhist_year_2digit(today: date) -> int:
    """ปี พ.ศ. 2 หลักของ 'ปีการศึกษาปัจจุบัน' ณ วันที่ today - ปีการศึกษาเริ่มประมาณเดือนมิถุนายน จึงนับ
    ถอยหลัง 1 ปีถ้ายังไม่ถึงเดือนมิถุนายน"""
    buddhist_2digit = (today.year + 543) % 100
    if today.month < 6:
        buddhist_2digit = (buddhist_2digit - 1) % 100
    return buddhist_2digit


def current_year_level(cohort_year: int, today: date | None = None) -> YearLevelResult:
    """ชั้นปีปัจจุบันของนักศึกษารุ่น cohort_year (ปี พ.ศ. 2 หลัก เช่น 66) คำนวณสด ณ วันที่ today (ค่า
    เริ่มต้น = วันนี้จริง)"""
    if today is None:
        today = _today()
    level = _buddhist_year_2digit(today) - cohort_year + 1
    level = max(1, level)
    return YearLevelResult(level=level, beyond_curriculum=level > 4)


def min_cohort_year_for_level(year_level: int, today: date | None = None) -> int:
    """ด้านกลับของ current_year_level() - คืนค่า cohort_year (2 หลัก) รุ่นใหม่สุดที่ ณ วันนี้ (หรือ today
    ที่ระบุ) จะมีชั้นปีจริง (ไม่ clamp ขั้นต่ำ) ถึง year_level ที่ขอแล้ว รุ่นไหนก็ตามที่ cohort_year <=
    ค่านี้ ผ่านเงื่อนไข "เรียนถึงชั้นปีนี้แล้ว" ทั้งหมด (รุ่นเก่ากว่า = ตัวเลขน้อยกว่า = เรียนมานานกว่า) ใช้
    กรองระดับ SQL แทนการดึงนักศึกษาทุกคนมาคำนวณทีละคน - ต้องใช้ cutoff เดือนมิถุนายนสูตรเดียวกับ
    current_year_level() ทุกประการ ไม่งั้นผลลัพธ์สองฝั่งจะไม่ตรงกัน"""
    if today is None:
        today = _today()
    return _buddhist_year_2digit(today) - year_level + 1
