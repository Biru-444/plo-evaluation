"""
ทำอะไร : รวม import ตาราง (model) ทั้งหมดของระบบไว้ที่เดียว เพื่อให้ไฟล์อื่นเขียน
         `from app.models import Student, CLO, ...` ได้โดยไม่ต้องรู้ว่าแต่ละ model อยู่ไฟล์ไหน

เชื่อมกับ : เรียงลำดับ import จากตารางที่ไม่มี foreign key ออกไปด้านนอก (user, curriculum) ไปจนถึง
            ตารางที่พึ่งพาตารางอื่นเยอะที่สุด (student_score) — ลำดับนี้ไม่ได้มีผลต่อการทำงานจริง (ต่างจาก
            ลำดับ include_router ใน app/main.py) แต่ช่วยให้อ่านไฟล์นี้แล้วเห็นภาพรวมความสัมพันธ์ของตาราง

ถ้าแก้ : เพิ่ม model ใหม่ต้อง import ที่นี่และเติมใน __all__ ด้วย ไม่งั้นไฟล์อื่นจะ
         `from app.models import ...` model นั้นไม่ได้
"""
from .user import User
from .curriculum import Curriculum
from .plo import PLO
from .ylo import YLO
from .ylo_plo_mapping import YLOPLOMapping
from .course import Course
from .course_plo import CoursePLO
from .study_plan import StudyPlan
from .course_offering import CourseOffering
from .student import Student
from .enrollment import Enrollment
from .clo import CLO
from .clo_plo_mapping import CLOPLOMapping
from .assessment import AssessmentItem, ItemCLO
from .student_score import StudentScore

__all__ = [
    "User",
    "Curriculum",
    "PLO",
    "YLO",
    "YLOPLOMapping",
    "Course",
    "CoursePLO",
    "StudyPlan",
    "CourseOffering",
    "Student",
    "Enrollment",
    "CLO",
    "CLOPLOMapping",
    "AssessmentItem",
    "ItemCLO",
    "StudentScore",
]
