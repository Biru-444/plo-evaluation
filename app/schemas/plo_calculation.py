"""Pydantic schemas สำหรับ GET /plo/achievement/cohort (ผล PLO ทั้งรุ่น/หลักสูตร)

ย้ายมาจาก app/routes/plo_calculation.py เดิม (อยู่ในไฟล์ route ตรงๆ) แยกออกมาที่นี่เพราะตอนนี้มีมากกว่า
1 ที่ใช้ (route เดิม + app/services/plo_achievement_service.py + app/services/plo_report_export_service.py)
- ต้องมี module กลางให้ทุกฝั่ง import ร่วมกันแทนที่จะ import ข้าม route/service กันเอง

เชื่อมกับ : สร้างโดย app/services/plo_achievement_service.py::compute_cohort_plo_achievement - ทั้ง
            GET /plo/achievement/cohort (response_model ตรงๆ) และ GET /plo/achievement/export (ใช้
            ตัวเลขไปสร้างไฟล์ Excel) เรียกฟังก์ชันเดียวกันนั้น ไม่มีสูตรคำนวณซ้ำสองชุด

ถ้าแก้ : ฟิลด์ในนี้เป็น "สัญญา" ของ GET /plo/achievement/cohort ที่ frontend (PLODashboard.jsx,
         PLODetailPage.jsx) พึ่งพาอยู่แล้ว - ห้ามแก้ชื่อ/ความหมายฟิลด์โดยไม่เช็ค caller ฝั่ง frontend ก่อน
         PLOAchievementItem/StudentPLOAchievement ยังใช้ร่วมกับ GET /plo/achievement (รายบุคคล) ด้วย
         YearlyPLOSummaryItem/YearProgressItem/CurriculumYearProgress/StudentPLOCourseBreakdownItem
         (ของ endpoint /achievement/by-year และ /course-breakdown คนละตัว) ยังอยู่ใน
         app/routes/plo_calculation.py เหมือนเดิม ไม่ได้ย้ายมาด้วย เพราะไม่มีใครใช้ร่วมนอกเหนือจาก
         endpoint นั้นเอง
"""
from __future__ import annotations

from pydantic import BaseModel


# ผลบรรลุ PLO ข้อเดียวของนักศึกษา 1 คน (ใช้เป็นรายการย่อยใน StudentPLOAchievement ด้านล่าง) -
# achieved_percent เป็นค่าต่อเนื่อง 0-100 จริง (ค่าเฉลี่ยถ่วงน้ำหนัก ไม่ใช่ 100/0)
class PLOAchievementItem(BaseModel):
    plo_id: int
    plo_code: str
    description: str
    achieved_percent: float
    is_achieved: bool


# ผลบรรลุ PLO ทุกข้อของนักศึกษา 1 คน — response ของ GET /plo/achievement (รายบุคคล) และรายการย่อยใน
# CurriculumPLOAchievement.students ด้านล่าง
class StudentPLOAchievement(BaseModel):
    student_id: str
    student_name: str
    curriculum_id: int
    plo_achievements: list[PLOAchievementItem]


# สรุปผลบรรลุ PLO ข้อเดียวของทั้งรุ่น/หลักสูตร (ค่าเฉลี่ย + จำนวนคนที่บรรลุ) — ใช้ในหน้า "ภาพรวม PLO"
class PLOCohortSummaryItem(BaseModel):
    plo_id: int
    plo_code: str
    description: str
    student_count_with_data: int
    average_achieved_percent: float
    achieved_student_count: int
    achieved_rate_percent: float


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
    # วิชา "หลัก" ที่ผ่านเกณฑ์คำนวณเลยเป็นไปไม่ได้อยู่แล้วโดยดีไซน์ ไม่ควรทำให้วงแหวนนี้ค้างที่ 0% ตลอด
    all_plo_achieved_count: int = 0
    all_plo_achieved_percent: float = 0.0
    qualifying_plo_count: int = 0
    total_plo_count: int = 0
