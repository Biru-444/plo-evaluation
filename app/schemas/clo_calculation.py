"""Pydantic schemas สำหรับ GET /clo-achievement (ผล CLO ทั้งห้องของ 1 course_offering)

ย้ายมาจาก app/routes/clo_calculation.py เดิม (อยู่ในไฟล์ route ตรงๆ) แยกออกมาที่นี่เพราะตอนนี้มีมากกว่า
1 ที่ใช้ (route เดิม + app/services/mco5_export_service.py) - ต้องมี module กลางให้ทั้งสองฝั่ง import
ร่วมกันแทนที่จะ import ข้าม route/service กันเอง

เชื่อมกับ : สร้างโดย app/services/clo_achievement_service.py::compute_offering_clo_achievement -
            ทั้ง GET /clo-achievement (response_model ตรงๆ) และ GET /clo-achievement/export/mco5
            (ใช้ตัวเลขไปสร้างไฟล์ Excel) เรียกฟังก์ชันเดียวกันนั้น ไม่มีสูตรคำนวณซ้ำสองชุด

ถ้าแก้ : ฟิลด์ในนี้เป็น "สัญญา" ของ GET /clo-achievement ที่ frontend (CLOAchievementPanel.jsx) พึ่งพา
         อยู่แล้ว - ห้ามแก้ชื่อ/ความหมายฟิลด์โดยไม่เช็ค caller ฝั่ง frontend ก่อน
         CLOItemContribution/StudentCourseCLOItem/StudentCourseCLOBreakdown (ของ endpoint
         /student-course คนละตัว) ยังอยู่ใน app/routes/clo_calculation.py เหมือนเดิม ไม่ได้ย้ายมาด้วย
         เพราะไม่มีใครใช้ร่วมนอกเหนือจาก endpoint นั้นเอง
"""
from __future__ import annotations

from pydantic import BaseModel


# คะแนน CLO ข้อเดียวของนักศึกษา 1 คนในห้อง (ใช้เป็นรายการย่อยใน CLOAchievementItem.student_scores)
class StudentCLOScore(BaseModel):
    student_id: str
    student_name: str
    clo_percent: float
    passed: bool


# สรุปผล CLO ข้อเดียวของทั้งห้อง (offering) — จำนวนผ่าน/ไม่ผ่าน/ไม่มีข้อมูล พร้อมคะแนนรายคน
class CLOAchievementItem(BaseModel):
    clo_id: int
    clo_code: str
    description: str
    pass_threshold_percent: float
    passed_count: int
    failed_count: int
    students_without_data: int
    achieved_rate_percent: float
    student_scores: list[StudentCLOScore]


# response ของ GET /clo-achievement — ผล CLO ทุกข้อของ offering เดียว
class OfferingCLOAchievement(BaseModel):
    offering_id: int
    course_name: str
    clo_achievements: list[CLOAchievementItem]
