"""Pydantic schemas สำหรับ GET /plo/achievement/cohort (ผล PLO ทั้งรุ่น/หลักสูตร)

ย้ายมาจาก app/routes/plo_calculation.py เดิม (อยู่ในไฟล์ route ตรงๆ) แยกออกมาที่นี่เพราะตอนนี้มีมากกว่า
1 ที่ใช้ (route เดิม + app/services/plo_achievement_service.py + app/services/plo_report_export_service.py)
- ต้องมี module กลางให้ทุกฝั่ง import ร่วมกันแทนที่จะ import ข้าม route/service กันเอง

เชื่อมกับ : สร้างโดย app/services/plo_achievement_service.py::compute_cohort_plo_achievement - ทั้ง
            GET /plo/achievement/cohort (response_model ตรงๆ) และ GET /plo/achievement/export (ใช้
            ตัวเลขไปสร้างไฟล์ Excel) เรียกฟังก์ชันเดียวกันนั้น ไม่มีสูตรคำนวณซ้ำสองชุด

ถ้าแก้ : ฟิลด์ในนี้เป็น "สัญญา" ของ GET /plo/achievement/cohort ที่ frontend (PLODashboard.jsx)
         พึ่งพาอยู่แล้ว - ห้ามแก้ชื่อ/ความหมายฟิลด์โดยไม่เช็ค caller ฝั่ง frontend ก่อน
         PLOAchievementItem/StudentPLOAchievement ยังใช้ร่วมกับ GET /plo/achievement (รายบุคคล) ด้วย
         YearlyPLOSummaryItem/YearProgressItem/CurriculumYearProgress/StudentPLOCourseBreakdownItem
         (ของ endpoint /achievement/by-year และ /course-breakdown คนละตัว) ยังอยู่ใน
         app/routes/plo_calculation.py เหมือนเดิม ไม่ได้ย้ายมาด้วย เพราะไม่มีใครใช้ร่วมนอกเหนือจาก
         endpoint นั้นเอง

         TASK-plo-denominator: สถิติระดับรุ่น (average_achieved_percent/achieved_rate_percent) หารด้วย
         "นักศึกษาที่มีข้อมูล" (has_data=True) ไม่ใช่นักศึกษาทั้งหมดอีกต่อไป - เป็น float | None (None =
         ไม่มีใครมีข้อมูลเลย หารไม่ได้ ไม่ใช่ 0) coverage_percent (ใหม่) คือสัดส่วนคนที่มีข้อมูลจาก
         นักศึกษาทั้งหมด ใช้แสดงคู่กันเสมอฝั่ง frontend ("จากผู้มีข้อมูล N/ทั้งหมด คน") - สูตรรายบุคคล
         (PLOAchievementItem.achieved_percent/is_achieved) ไม่เปลี่ยน มีแค่ has_data เพิ่มมาบอกว่าตัวเลข
         รายคนนั้นมีหลักฐานจริงหรือเป็นค่า "ยังไม่มีข้อมูล" ที่บังเอิญได้ 0.0/False เหมือนคนสอบตก
"""
from __future__ import annotations

from pydantic import BaseModel


# ผลบรรลุ PLO ข้อเดียวของนักศึกษา 1 คน (ใช้เป็นรายการย่อยใน StudentPLOAchievement ด้านล่าง) -
# achieved_percent เป็นค่าต่อเนื่อง 0-100 จริง (ค่าเฉลี่ยถ่วงน้ำหนัก ไม่ใช่ 100/0) - สูตร/เกณฑ์รายบุคคล
# ไม่เปลี่ยนจาก TASK-plo-denominator เลย (achieved_percent/is_achieved ของคนไม่มีข้อมูลยังเป็น 0.0/False
# เหมือนเดิมเพื่อไม่ให้ caller เดิมพัง) - has_data (ใหม่) คือ field ที่ต้องใช้แยกแยะจริงๆ ว่า 0.0/False
# นั้นคือ "สอบตก" หรือ "ยังไม่มีข้อมูลให้ตัดสิน": True เมื่อมี CLO ที่ผูกกับ PLO นี้อย่างน้อย 1 ตัวที่
# นักศึกษาคนนี้มี mastery จริง (ผลรวมน้ำหนักของ CLO ที่นับได้ > 0 ใน _student_plo_score)
class PLOAchievementItem(BaseModel):
    plo_id: int
    plo_code: str
    description: str
    achieved_percent: float
    is_achieved: bool
    has_data: bool = True


# ผลบรรลุ PLO ทุกข้อของนักศึกษา 1 คน — response ของ GET /plo/achievement (รายบุคคล) และรายการย่อยใน
# CurriculumPLOAchievement.students ด้านล่าง
class StudentPLOAchievement(BaseModel):
    student_id: str
    student_name: str
    curriculum_id: int
    plo_achievements: list[PLOAchievementItem]


# สรุปผลบรรลุ PLO ข้อเดียวของทั้งรุ่น/หลักสูตร — ใช้ในหน้า "ภาพรวม PLO" ตัวหารของ average/rate คือ
# student_count_with_data (จำนวนคน has_data=True) ไม่ใช่นักศึกษาทั้งหมดอีกต่อไป (TASK-plo-denominator)
# average_achieved_percent/achieved_rate_percent เป็น None เมื่อ student_count_with_data = 0 (ไม่มีใคร
# มีข้อมูลเลย - หารไม่ได้ ไม่ใช่ 0%) coverage_percent (ใหม่) = student_count_with_data / นักศึกษาทั้งหมด
# ของรุ่นนี้ × 100 (0.0 ถ้าไม่มีนักศึกษาเลย) ต้องแสดงคู่กับ average/rate เสมอฝั่ง frontend
class PLOCohortSummaryItem(BaseModel):
    plo_id: int
    plo_code: str
    description: str
    student_count_with_data: int
    average_achieved_percent: float | None
    achieved_student_count: int
    achieved_rate_percent: float | None
    coverage_percent: float = 0.0
    # PLO นี้มี CLO ผูกอยู่อย่างน้อย 1 ตัวผ่าน clo_plo_mapping หรือไม่ (ดู _qualifying_plo_ids ใน
    # plo_achievement_service.py) - เพิ่มเข้ามา (2026-09) ให้ frontend แยกเหตุผล "ยังไม่มีข้อมูล" ของ PLO
    # ที่ยังไม่มีข้อมูล ระหว่าง "ยังไม่ผูกกับรายวิชาเลย" (False) กับ "ผูกแล้วแต่ยังไม่มีคะแนน/นักศึกษา"
    # (True) - default True กันโค้ดเก่าที่ยังไม่รู้จัก field นี้พัง (ไม่ควรมีเหลือ - constructor ทุกจุดใน
    # compute_cohort_plo_achievement ตั้งค่าจริงเสมอ)
    has_clo_mapping: bool = True


# response หลักของ GET /plo/achievement/cohort — สรุปทั้งหลักสูตร + รายชื่อนักศึกษาทุกคนพร้อมผลบรรลุ
class CurriculumPLOAchievement(BaseModel):
    curriculum_id: int
    curriculum_name: str
    total_students: int
    plo_summary: list[PLOCohortSummaryItem]
    students: list[StudentPLOAchievement]
    available_cohort_years: list[int] = []
    # สถิติวงแหวน "บรรลุ PLO ครบทุกข้อ" (hero stat หน้า "ภาพรวม PLO") - "ครบทุกข้อ" นับเฉพาะ PLO ที่
    # qualifying_plo_count (ดู _qualifying_plo_ids) ไม่ใช่ total_plo_count ทั้งหมด เพราะ PLO ที่ไม่มี
    # วิชา "หลัก" ที่ผ่านเกณฑ์คำนวณเลยเป็นไปไม่ได้อยู่แล้วโดยดีไซน์ ไม่ควรทำให้วงแหวนนี้ค้างที่ 0% ตลอด -
    # ตัวหารเปลี่ยนเป็น all_plo_data_complete_count (คนที่ has_data=True ใน qualifying PLO ทุกข้อ) แทน
    # total_students (TASK-plo-denominator) - all_plo_achieved_percent เป็น None ถ้า
    # all_plo_data_complete_count = 0
    all_plo_achieved_count: int = 0
    all_plo_achieved_percent: float | None = 0.0
    all_plo_data_complete_count: int = 0
    qualifying_plo_count: int = 0
    total_plo_count: int = 0
