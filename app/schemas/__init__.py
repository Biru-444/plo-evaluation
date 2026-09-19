"""
ทำอะไร : รวม import schema (Pydantic model ใช้ validate request/response) ทั้งหมดไว้ที่เดียว เพื่อให้
         ไฟล์ route เขียน `from app.schemas import StudentSchema, ...` ได้โดยไม่ต้องรู้ว่าอยู่ไฟล์ไหน
         แต่ละตารางมักมี schema 3 แบบคู่กัน : XSchema (ใช้ตอบกลับ response เต็มรูปแบบ), XCreateSchema
         (รับตอนสร้างใหม่ - ไม่มี id เพราะฐานข้อมูล generate ให้), XUpdateSchema (รับตอนแก้ไข - ทุก
         field เป็น optional เพราะแก้บางส่วนได้ ไม่ต้องส่งมาครบ)

เชื่อมกับ : import จากทุกไฟล์ใน app/schemas/*.py — ไฟล์ route ทุกไฟล์ใช้ schema จากที่นี่ประกอบ
            response_model และ request body ของ endpoint

ถ้าแก้ : PLOCoursePlanItemSchema และ RecommendedOfferingSchema ถูก import แต่ไม่ได้อยู่ใน __all__
         ด้านล่าง (ตั้งใจ ไม่ใช่ลืม) — ยังใช้งานจริงอยู่ที่ app/routes/plo.py และ app/routes/students.py
         ตามลำดับ เพียงแต่ import ตรงจากไฟล์ย่อยแทนที่จะผ่าน __all__ ของที่นี่
"""
from .user import UserSchema, UserCreateSchema, UserUpdateSchema
from .curriculum import CurriculumSchema, CurriculumCreateSchema, CurriculumUpdateSchema
from .plo import (
    PLOSchema,
    PLOCreateSchema,
    PLOUpdateSchema,
    PLOCoursePlanItemSchema,
)
from .ylo import YLOSchema, YLOCreateSchema, YLOUpdateSchema
from .ylo_plo_mapping import YLOPLOMappingSchema, YLOPLOMappingCreateSchema
from .course import CourseSchema, CourseCreateSchema, CourseUpdateSchema
from .course_plo import CoursePLOSchema, CoursePLOCreateSchema, CoursePLOUpdateSchema
from .study_plan import StudyPlanSchema, StudyPlanCreateSchema, StudyPlanUpdateSchema
from .course_offering import (
    CourseOfferingSchema,
    CourseOfferingCreateSchema,
    CourseOfferingUpdateSchema,
)
from .student import StudentSchema, StudentCreateSchema, StudentUpdateSchema, EnrolledStudentSchema
from .enrollment import (
    EnrollmentSchema,
    EnrollmentCreateSchema,
    EnrollmentUpdateSchema,
    BulkEnrollByCohortSchema,
    BulkEnrollSchema,
    EnrolledStudentBrief,
    OtherSectionConflict,
    BulkEnrollByCohortResult,
    BulkRemoveByCohortResult,
    BulkEnrollResult,
    RecommendedOfferingSchema,
)
from .clo import CLOSchema, CLOCreateSchema, CLOUpdateSchema
from .clo_plo_mapping import CLOPLOMappingSchema, CLOPLOMappingCreateSchema
from .assessment import (
    AssessmentItemSchema,
    AssessmentCreateSchema,
    AssessmentItemUpdateSchema,
    StudentScoreSchema,
    StudentScoreCreateSchema,
    StudentScoreDetailSchema,
    StudentScoreUpdateSchema,
)
from .item_clo import ItemCLOSchema, ItemCLOCreateSchema, ItemCLOUpdateSchema
from .roster_import import RosterImportInstructor, RosterImportResponse, RosterImportStudentRow

__all__ = [
    "UserSchema",
    "UserCreateSchema",
    "UserUpdateSchema",
    "CurriculumSchema",
    "CurriculumCreateSchema",
    "CurriculumUpdateSchema",
    "PLOSchema",
    "PLOCreateSchema",
    "PLOUpdateSchema",
    "YLOSchema",
    "YLOCreateSchema",
    "YLOUpdateSchema",
    "YLOPLOMappingSchema",
    "YLOPLOMappingCreateSchema",
    "CourseSchema",
    "CourseCreateSchema",
    "CourseUpdateSchema",
    "CoursePLOSchema",
    "CoursePLOCreateSchema",
    "CoursePLOUpdateSchema",
    "StudyPlanSchema",
    "StudyPlanCreateSchema",
    "StudyPlanUpdateSchema",
    "CourseOfferingSchema",
    "CourseOfferingCreateSchema",
    "CourseOfferingUpdateSchema",
    "StudentSchema",
    "StudentCreateSchema",
    "StudentUpdateSchema",
    "EnrolledStudentSchema",
    "EnrollmentSchema",
    "EnrollmentCreateSchema",
    "EnrollmentUpdateSchema",
    "BulkEnrollByCohortSchema",
    "BulkEnrollSchema",
    "EnrolledStudentBrief",
    "OtherSectionConflict",
    "BulkEnrollByCohortResult",
    "BulkRemoveByCohortResult",
    "BulkEnrollResult",
    "CLOSchema",
    "CLOCreateSchema",
    "CLOUpdateSchema",
    "CLOPLOMappingSchema",
    "CLOPLOMappingCreateSchema",
    "AssessmentItemSchema",
    "AssessmentCreateSchema",
    "AssessmentItemUpdateSchema",
    "StudentScoreSchema",
    "StudentScoreCreateSchema",
    "StudentScoreDetailSchema",
    "StudentScoreUpdateSchema",
    "ItemCLOSchema",
    "ItemCLOCreateSchema",
    "ItemCLOUpdateSchema",
    "RosterImportInstructor",
    "RosterImportResponse",
    "RosterImportStudentRow",
]
