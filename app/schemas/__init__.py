"""
Pydantic Schemas for Request/Response Data Validation
"""
from .user import UserSchema, UserCreateSchema, UserUpdateSchema
from .curriculum import CurriculumSchema, CurriculumCreateSchema, CurriculumUpdateSchema
from .plo import PLOSchema, PLOCreateSchema, PLOUpdateSchema
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
from .student import StudentSchema, StudentCreateSchema, StudentUpdateSchema
from .enrollment import EnrollmentSchema, EnrollmentCreateSchema, EnrollmentUpdateSchema
from .clo import CLOSchema, CLOCreateSchema, CLOUpdateSchema
from .clo_plo_mapping import (
    CLOPLOMappingSchema,
    CLOPLOMappingCreateSchema,
    CLOPLOMappingUpdateSchema,
)
from .assessment import (
    AssessmentItemSchema,
    AssessmentCreateSchema,
    AssessmentItemUpdateSchema,
    StudentScoreSchema,
    StudentScoreDetailSchema,
    StudentScoreUpdateSchema,
)
from .item_clo import ItemCLOSchema, ItemCLOCreateSchema, ItemCLOUpdateSchema

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
    "EnrollmentSchema",
    "EnrollmentCreateSchema",
    "EnrollmentUpdateSchema",
    "CLOSchema",
    "CLOCreateSchema",
    "CLOUpdateSchema",
    "CLOPLOMappingSchema",
    "CLOPLOMappingCreateSchema",
    "CLOPLOMappingUpdateSchema",
    "AssessmentItemSchema",
    "AssessmentCreateSchema",
    "AssessmentItemUpdateSchema",
    "StudentScoreSchema",
    "StudentScoreDetailSchema",
    "StudentScoreUpdateSchema",
    "ItemCLOSchema",
    "ItemCLOCreateSchema",
    "ItemCLOUpdateSchema",
]
