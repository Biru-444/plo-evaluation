"""
Seed script: ชุดข้อมูลทดสอบแบบ "แยกหลักสูตรของตัวเองทั้งก้อน" สำหรับทดสอบหน้าเว็บและปุ่มส่งออก Excel
(หน้า /curriculum และ /student-plo) — ต่างจาก seed_mock_test_data.py ที่ยัดนักศึกษาปลอมเข้าหลักสูตร
จริง (curriculum_id=1) ชุดนี้สร้างหลักสูตร/PLO/YLO/วิชา/อาจารย์/นักศึกษาใหม่ทั้งหมด จึงไม่ปนกับข้อมูลจริง
เลย (export วิชาจริงจะไม่มีนักศึกษาทดสอบโผล่มา)

สิ่งที่สร้าง:
  - หลักสูตร "[TEST] หลักสูตรวิทยาการคอมพิวเตอร์ (ข้อมูลทดสอบ)" + PLO 5 ข้อ + YLO 4 ปี
  - อาจารย์ 3 คน (username ขึ้นต้น "test.ajarn" รหัสผ่านสุ่มทิ้ง - login ไม่ได้ มีไว้แสดงชื่อเท่านั้น)
  - วิชา 4 วิชา (รหัส TST....) + CLO + การผูก CLO-PLO + แผนการเรียน + งานประเมิน
  - นักศึกษา 16 คน (รหัสขึ้นต้น "TSX") รุ่น 68 จำนวน 10 คน, รุ่น 69 จำนวน 6 คน + คะแนน

เคสที่ตั้งใจใส่ไว้ให้ทดสอบ:
  - TST1001 เปิด 3 กลุ่มเรียน อาจารย์ 2 คน (ทดสอบรายชื่ออาจารย์หลายคน / หลายภาคเรียน)
  - TST1002 มี CLO ที่ผูกกับ PLO 2 ข้อพร้อมกัน และเกณฑ์ผ่าน 65% (ไม่ใช่ 60% เหมือนวิชาอื่น)
  - TST2002 ยังไม่กำหนดอาจารย์ผู้สอน และยังไม่มี CLO เลย (ไฟล์ Excel ต้องไม่พัง)
  - PLO5 ไม่มี CLO ผูกอยู่เลย -> ทุกคน "ยังไม่มีข้อมูล" (กฎเดียวกับระบบจริง)
  - นักศึกษาเก่ง/ปานกลาง/อ่อน, คนที่ยังไม่มีคะแนนเลย, คนที่ขาดคะแนนบางชิ้น (-> "ไม่มีข้อมูล"),
    และคนที่ลงเรียนวิชาเดิมซ้ำ 2 ภาคเรียน (TSX68010 - Excel รายวิชาแยกแถวตามครั้งที่เรียน)

ใช้งาน:
  python scripts/seed_export_test_data.py            # สร้างข้อมูล (ถามยืนยันก่อน)
  python scripts/seed_export_test_data.py --remove   # ลบข้อมูลชุดนี้ทั้งหมด
  เพิ่ม --yes เพื่อข้ามการถามยืนยัน

Idempotent: ถ้ามีหลักสูตรทดสอบอยู่แล้วจะไม่สร้างซ้ำ (ลบด้วย --remove ก่อนถ้าอยากสร้างใหม่) — การลบ
กรองด้วยชื่อหลักสูตร/รหัสนักศึกษา "TSX"/username "test.ajarn" ของชุดนี้เท่านั้น ไม่แตะข้อมูลจริง
"""
from __future__ import annotations

import argparse
import random
import secrets
import sys
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy.engine import make_url

from app.auth import hash_password
from app.database import Base, SessionLocal, engine
from app.models import (
    CLO,
    AssessmentItem,
    CLOPLOMapping,
    Course,
    CourseOffering,
    CoursePLO,
    Curriculum,
    Enrollment,
    ItemCLO,
    PLO,
    Student,
    StudentScore,
    StudyPlan,
    User,
    YLO,
    YLOPLOMapping,
)
from app.services.domain_category_check import DOMAIN_TO_CATEGORY_TH

CURRICULUM_NAME = "[TEST] หลักสูตรวิทยาการคอมพิวเตอร์ (ข้อมูลทดสอบ)"
CURRICULUM_YEAR = 2569
STUDENT_ID_PREFIX = "TSX"
INSTRUCTOR_USERNAME_PREFIX = "test.ajarn"
# น้ำหนัก CLO ทุกตัวที่ผูกกับ PLO เท่ากันหมด -> คะแนน PLO = ค่าเฉลี่ยธรรมดาของ CLO ที่ผูก
CLO_PLO_WEIGHT = Decimal(100)
CATEGORY_TO_DOMAIN = {category: domain for domain, category in DOMAIN_TO_CATEGORY_TH.items()}

random.seed(2569)  # ผลลัพธ์เดิมทุกครั้งที่รัน

PLOS = [
    ("PLO1", "ความรู้", "อธิบายหลักการพื้นฐานของวิทยาการคอมพิวเตอร์และคณิตศาสตร์ที่เกี่ยวข้องได้"),
    ("PLO2", "ทักษะ", "พัฒนาโปรแกรมเพื่อแก้ปัญหาได้อย่างถูกต้องและมีประสิทธิภาพ"),
    ("PLO3", "ทักษะ", "ออกแบบและจัดการระบบฐานข้อมูลได้"),
    ("PLO4", "จริยธรรม", "ปฏิบัติตามจรรยาบรรณวิชาชีพและกฎหมายด้านเทคโนโลยีสารสนเทศ"),
    ("PLO5", "ลักษณะบุคคล", "ทำงานเป็นทีมและสื่อสารได้อย่างมีประสิทธิภาพ"),  # ไม่มี CLO ผูก (ตั้งใจ)
]

# year_level -> (คำอธิบาย YLO, PLO ที่ YLO ปีนั้นผูกไว้)
YLOS = {
    1: ("เข้าใจพื้นฐานการเขียนโปรแกรมและคณิตศาสตร์สำหรับคอมพิวเตอร์", ["PLO1", "PLO2"]),
    2: ("ประยุกต์ใช้โปรแกรมและฐานข้อมูลแก้ปัญหาได้อย่างมีจริยธรรม", ["PLO2", "PLO3", "PLO4"]),
    3: ("พัฒนาระบบขนาดกลางร่วมกับผู้อื่นได้", ["PLO5"]),
    4: ("พัฒนาโครงงานที่นำไปใช้ได้จริงและนำเสนอผลงานได้", ["PLO5"]),
}

# key -> (username, ชื่อ, นามสกุล)
INSTRUCTORS = {
    "somsak": (f"{INSTRUCTOR_USERNAME_PREFIX}.somsak", "สมศักดิ์", "รักการสอน"),
    "wipa": (f"{INSTRUCTOR_USERNAME_PREFIX}.wipa", "วิภาวดี", "ใจงาม"),
    "teera": (f"{INSTRUCTOR_USERNAME_PREFIX}.teera", "ธีรพงษ์", "มั่นคง"),
}

# รายวิชา: clos = [(code, คำอธิบาย, เกณฑ์ผ่าน, [PLO ที่ผูก])]
# items = [(ชื่อ, ประเภท, คะแนนเต็ม, {CLO: น้ำหนัก})]
COURSES = [
    {
        "code": "TST1001",
        "name_th": "การเขียนโปรแกรมเบื้องต้น",
        "name_en": "Introduction to Programming",
        "credit": 3,
        "category": "วิชาแกน",
        "plan": (1, 1),
        "course_plo": {"PLO1": "primary", "PLO2": "primary", "PLO4": "secondary"},
        "clos": [
            ("CLO1", "อธิบายโครงสร้างพื้นฐานและชนิดข้อมูลของโปรแกรมได้", 60, ["PLO1"]),
            ("CLO2", "เขียนโปรแกรมที่มีเงื่อนไขและการทำงานซ้ำได้", 60, ["PLO2"]),
            ("CLO3", "ส่งงานด้วยผลงานของตนเองตามจรรยาบรรณ ไม่คัดลอกผลงานผู้อื่น", 50, ["PLO4"]),
        ],
        "items": [
            ("แบบทดสอบย่อย 1", "quiz", 10, {"CLO1": 100}),
            ("สอบกลางภาค", "midterm", 30, {"CLO1": 50, "CLO2": 50}),
            ("งานที่มอบหมาย", "assignment", 20, {"CLO3": 100}),
            ("สอบปลายภาค", "final", 40, {"CLO2": 100}),
        ],
    },
    {
        "code": "TST1002",
        "name_th": "คณิตศาสตร์ดิสครีต",
        "name_en": "Discrete Mathematics",
        "credit": 3,
        "category": "วิชาแกน",
        "plan": (1, 2),
        "course_plo": {"PLO1": "primary"},
        "clos": [
            ("CLO1", "อธิบายเซต ความสัมพันธ์ และฟังก์ชันได้", 60, ["PLO1"]),
            ("CLO2", "ใช้ตรรกศาสตร์พิสูจน์และวิเคราะห์อัลกอริทึมอย่างง่ายได้", 65, ["PLO1", "PLO2"]),
        ],
        "items": [
            ("สอบกลางภาค", "midterm", 40, {"CLO1": 100}),
            ("แบบฝึกหัดพิสูจน์", "assignment", 20, {"CLO2": 100}),
            ("สอบปลายภาค", "final", 40, {"CLO1": 30, "CLO2": 70}),
        ],
    },
    {
        "code": "TST2001",
        "name_th": "ระบบฐานข้อมูล",
        "name_en": "Database Systems",
        "credit": 3,
        "category": "วิชาบังคับ",
        "plan": (2, 1),
        "course_plo": {"PLO2": "secondary", "PLO3": "primary", "PLO4": "primary"},
        "clos": [
            ("CLO1", "ออกแบบแบบจำลอง ER และทำ Normalization ได้", 60, ["PLO3"]),
            ("CLO2", "เขียนคำสั่ง SQL เพื่อจัดการและสืบค้นข้อมูลได้", 60, ["PLO2", "PLO3"]),
            ("CLO3", "จัดการข้อมูลส่วนบุคคลตามกฎหมายคุ้มครองข้อมูลส่วนบุคคลได้", 60, ["PLO4"]),
        ],
        "items": [
            ("สอบกลางภาค", "midterm", 30, {"CLO1": 100}),
            ("โปรเจกต์ฐานข้อมูล", "project", 30, {"CLO1": 40, "CLO2": 60}),
            ("รายงาน PDPA", "assignment", 10, {"CLO3": 100}),
            ("สอบปลายภาค", "final", 30, {"CLO2": 100}),
        ],
    },
    {
        # ยังไม่มีอาจารย์ผู้สอนและยังไม่มี CLO (ตั้งใจ - ทดสอบ export วิชาที่ข้อมูลยังไม่ครบ)
        "code": "TST2002",
        "name_th": "โครงสร้างข้อมูลและอัลกอริทึม",
        "name_en": "Data Structures and Algorithms",
        "credit": 3,
        "category": "วิชาบังคับ",
        "plan": (2, 1),
        "course_plo": {},
        "clos": [],
        "items": [],
    },
]

# กลุ่มเรียน: key -> (วิชา, ปีการศึกษา, ภาคเรียน, section, อาจารย์ (None = ยังไม่กำหนด), รุ่น)
OFFERINGS = {
    "1001-68": ("TST1001", 2568, 1, "1", "somsak", 68),
    "1001-69-1": ("TST1001", 2569, 1, "1", "somsak", 69),
    "1001-69-2": ("TST1001", 2569, 1, "2", "wipa", 69),
    "1002-68": ("TST1002", 2568, 2, "1", "teera", 68),
    "2001-68": ("TST2001", 2569, 1, "1", "wipa", 68),
    "2002-68": ("TST2002", 2569, 1, "1", None, 68),
}

# นักศึกษา: (รหัส, คำนำหน้า, ชื่อ, นามสกุล, รุ่น, ระดับคะแนน % พื้นฐาน, กลุ่มเรียนที่ลงทะเบียน,
#            คะแนนเฉพาะ {(กลุ่มเรียน, CLO): %}, ชิ้นงานที่ยังไม่มีคะแนน {(กลุ่มเรียน, ชื่อชิ้นงาน)})
# ระดับคะแนน None = ยังไม่มีคะแนนเลยสักชิ้น (ชั้นปีไม่ต้องใส่ - ระบบคำนวณจาก cohort_year เอง)
COHORT_68_OFFERINGS = ["1001-68", "1002-68", "2001-68", "2002-68"]
STUDENTS = [
    ("TSX68001", "นาย", "ธนากร", "ศรีสุข", 68, 90, COHORT_68_OFFERINGS, {}, set()),
    ("TSX68002", "นางสาว", "พิมพ์ชนก", "แก้วมณี", 68, 85, COHORT_68_OFFERINGS, {}, set()),
    # เก่งแต่ตกเรื่อง PDPA -> ไม่บรรลุ PLO4
    ("TSX68003", "นาย", "กิตติพัฒน์", "บุญมา", 68, 76, COHORT_68_OFFERINGS,
     {("2001-68", "CLO3"): 40}, set()),
    ("TSX68004", "นางสาว", "ศิริพร", "ทองดี", 68, 74, COHORT_68_OFFERINGS, {}, set()),
    # ปานกลาง ตก CLO2 ของ TST1002 (เกณฑ์ 65%) แต่ PLO เป็นค่าเฉลี่ยถ่วงน้ำหนักของทุก CLO ที่ผูก จึงยัง
    # บรรลุ PLO1/PLO2 ได้ (ตัวอย่างว่า "ตก CLO บางข้อ" ไม่ได้แปลว่า "ไม่บรรลุ PLO" เสมอไป)
    ("TSX68005", "นาย", "ณัฐวุฒิ", "พรหมมา", 68, 70, COHORT_68_OFFERINGS,
     {("1002-68", "CLO2"): 58}, set()),
    ("TSX68006", "นางสาว", "อรอุมา", "สายทอง", 68, 66, COHORT_68_OFFERINGS, {}, set()),
    ("TSX68007", "นาย", "วรเชษฐ์", "จันทร์เพ็ญ", 68, 45, COHORT_68_OFFERINGS, {}, set()),
    ("TSX68008", "นางสาว", "กมลชนก", "ปัญญาดี", 68, 38, COHORT_68_OFFERINGS, {}, set()),
    # ขาดคะแนนรายงาน PDPA -> CLO3 ของ TST2001 "ไม่มีข้อมูล"
    ("TSX68009", "นาย", "ภูมิพัฒน์", "วงศ์ใหญ่", 68, 80, COHORT_68_OFFERINGS, {},
     {("2001-68", "รายงาน PDPA")}),
    # ลงเรียน TST1001 ซ้ำ: ครั้งแรก (2568/1) ได้น้อย ครั้งที่สอง (2569/1 Sec 2) ได้ดี
    ("TSX68010", "นางสาว", "ชลธิชา", "มีสุข", 68, 72, COHORT_68_OFFERINGS + ["1001-69-2"],
     {("1001-68", "CLO1"): 35, ("1001-68", "CLO2"): 30, ("1001-68", "CLO3"): 40,
      ("1001-69-2", "CLO1"): 92, ("1001-69-2", "CLO2"): 90, ("1001-69-2", "CLO3"): 95}, set()),
    ("TSX69001", "นาย", "ปัณณวัฒน์", "ทองคำ", 69, 88, ["1001-69-1"], {}, set()),
    ("TSX69002", "นางสาว", "เบญจมาศ", "ศรีวงศ์", 69, 73, ["1001-69-1"], {}, set()),
    ("TSX69003", "นาย", "อนุชา", "แสงทอง", 69, 42, ["1001-69-1"], {}, set()),
    ("TSX69004", "นางสาว", "ปิยะนุช", "บุญเรือง", 69, 65, ["1001-69-2"], {}, set()),
    # ยังไม่มีคะแนนเลยสักชิ้น -> ทุก CLO "ไม่มีข้อมูล"
    ("TSX69005", "นาย", "ศุภกร", "ใจเย็น", 69, None, ["1001-69-2"], {}, set()),
    # ยังไม่ส่งงานที่มอบหมาย -> CLO3 ของ TST1001 "ไม่มีข้อมูล"
    ("TSX69006", "นางสาว", "มณีรัตน์", "พูลสวัสดิ์", 69, 81, ["1001-69-2"], {},
     {("1001-69-2", "งานที่มอบหมาย")}),
]


def _describe_target() -> str:
    url = make_url(str(engine.url))
    if url.get_backend_name() == "sqlite":
        return f"sqlite ({url.database})"
    return f"{url.get_backend_name()} host={url.host} database={url.database}"


def _confirm(message: str, assume_yes: bool) -> bool:
    if assume_yes:
        return True
    return input(f"{message} พิมพ์ y เพื่อยืนยัน: ").strip().lower() == "y"


def seed(db) -> None:
    curriculum = Curriculum(name=CURRICULUM_NAME, year=CURRICULUM_YEAR, is_active=True)
    db.add(curriculum)
    db.flush()

    plo_by_code: dict[str, PLO] = {}
    for code, category, description in PLOS:
        plo = PLO(curriculum_id=curriculum.id, code=code, description_th=description, category=category)
        db.add(plo)
        plo_by_code[code] = plo
    db.flush()

    for year_level, (description, plo_codes) in YLOS.items():
        ylo = YLO(curriculum_id=curriculum.id, year_level=year_level, description=description)
        db.add(ylo)
        db.flush()
        for code in plo_codes:
            db.add(YLOPLOMapping(ylo_id=ylo.id, plo_id=plo_by_code[code].id))

    instructor_by_key: dict[str, User] = {}
    for key, (username, first_name, last_name) in INSTRUCTORS.items():
        user = User(
            username=username,
            # รหัสผ่านสุ่มทิ้ง ไม่มีใครรู้ - บัญชีนี้มีไว้แสดงชื่ออาจารย์เท่านั้น login ไม่ได้
            password=hash_password(secrets.token_urlsafe(24)),
            first_name=first_name,
            last_name=last_name,
            role="instructor",
        )
        db.add(user)
        instructor_by_key[key] = user
    db.flush()
    clo_creator_id = instructor_by_key["somsak"].id

    course_by_code: dict[str, dict] = {}
    for spec in COURSES:
        course = Course(
            curriculum_id=curriculum.id,
            course_code=spec["code"],
            name_th=spec["name_th"],
            name_en=spec["name_en"],
            credit=spec["credit"],
            category=spec["category"],
        )
        db.add(course)
        db.flush()
        year_level, semester = spec["plan"]
        db.add(StudyPlan(curriculum_id=curriculum.id, course_id=course.id, year_level=year_level, semester=semester))
        for plo_code, level in spec["course_plo"].items():
            db.add(CoursePLO(course_id=course.id, plo_id=plo_by_code[plo_code].id, responsibility_level=level))

        clo_by_code: dict[str, CLO] = {}
        for code, description, threshold, plo_codes in spec["clos"]:
            clo = CLO(
                course_id=course.id,
                code=code,
                description=description,
                pass_threshold_percent=Decimal(threshold),
                # domain ของ CLO ให้ตรงกับหมวดหมู่ของ PLO ตัวแรกที่ผูก (ไม่ให้ขึ้นเตือน domain ไม่ตรง)
                domain=CATEGORY_TO_DOMAIN[plo_by_code[plo_codes[0]].category],
                created_by=clo_creator_id,
            )
            db.add(clo)
            db.flush()
            clo_by_code[code] = clo
            for plo_code in plo_codes:
                db.add(
                    CLOPLOMapping(
                        clo_id=clo.id, plo_id=plo_by_code[plo_code].id, weight_percent=CLO_PLO_WEIGHT
                    )
                )
        course_by_code[spec["code"]] = {"course": course, "spec": spec, "clos": clo_by_code}
    db.flush()

    # กลุ่มเรียน + งานประเมินของแต่ละกลุ่ม (ชิ้นงานชุดเดียวกันตาม spec ของวิชา)
    offering_by_key: dict[str, dict] = {}
    for key, (course_code, academic_year, semester, section, instructor_key, cohort_year) in OFFERINGS.items():
        entry = course_by_code[course_code]
        offering = CourseOffering(
            course_id=entry["course"].id,
            instructor_id=instructor_by_key[instructor_key].id if instructor_key else None,
            cohort_year=cohort_year,
            academic_year=academic_year,
            semester=semester,
            section=section,
        )
        db.add(offering)
        db.flush()
        items = []
        for name, item_type, total, clo_weights in entry["spec"]["items"]:
            item = AssessmentItem(offering_id=offering.id, name=name, type=item_type, total_score=Decimal(total))
            db.add(item)
            db.flush()
            for clo_code, weight in clo_weights.items():
                db.add(ItemCLO(item_id=item.id, clo_id=entry["clos"][clo_code].id, weight_percent=Decimal(weight)))
            items.append((item, name, total, clo_weights))
        offering_by_key[key] = {"offering": offering, "items": items}
    db.flush()

    # นักศึกษา + ลงทะเบียน + คะแนน
    for sid, title, first_name, last_name, cohort_year, base, offering_keys, overrides, missing in STUDENTS:
        db.add(
            Student(
                id=sid,
                curriculum_id=curriculum.id,
                title=title,
                first_name=first_name,
                last_name=last_name,
                cohort_year=cohort_year,
            )
        )
        db.flush()
        for key in offering_keys:
            db.add(Enrollment(student_id=sid, offering_id=offering_by_key[key]["offering"].id))
            if base is None:
                continue
            for item, name, total, clo_weights in offering_by_key[key]["items"]:
                if (key, name) in missing:
                    continue
                # % ของชิ้นงาน = ค่าเฉลี่ยของ % ที่ตั้งไว้ของ CLO ที่ชิ้นงานนั้นวัด + สุ่มแกว่ง ±4
                target = sum(overrides.get((key, clo), base) for clo in clo_weights) / len(clo_weights)
                percent = max(0, min(100, target + random.uniform(-4, 4)))
                score = (Decimal(total) * Decimal(str(round(percent, 2))) / Decimal(100)).quantize(Decimal("0.01"))
                db.add(StudentScore(item_id=item.id, student_id=sid, score_obtained=score))
    db.commit()


def remove(db) -> None:
    """ลบเฉพาะข้อมูลของชุดนี้ ลบจากตารางลูกขึ้นไปหาตารางแม่เอง (ไม่พึ่ง ON DELETE CASCADE ของ DB)"""
    curriculum = db.query(Curriculum).filter(Curriculum.name == CURRICULUM_NAME).one_or_none()
    student_ids = [s.id for s in db.query(Student.id).filter(Student.id.like(f"{STUDENT_ID_PREFIX}%"))]
    instructor_ids = [u.id for u in db.query(User.id).filter(User.username.like(f"{INSTRUCTOR_USERNAME_PREFIX}.%"))]

    course_ids: list[int] = []
    if curriculum is not None:
        course_ids = [c.id for c in db.query(Course.id).filter(Course.curriculum_id == curriculum.id)]
    offering_ids = [o.id for o in db.query(CourseOffering.id).filter(CourseOffering.course_id.in_(course_ids))]
    item_ids = [i.id for i in db.query(AssessmentItem.id).filter(AssessmentItem.offering_id.in_(offering_ids))]
    clo_ids = [c.id for c in db.query(CLO.id).filter(CLO.course_id.in_(course_ids))]

    def delete(query) -> None:
        query.delete(synchronize_session=False)

    delete(db.query(StudentScore).filter(
        StudentScore.student_id.in_(student_ids) | StudentScore.item_id.in_(item_ids)
    ))
    delete(db.query(ItemCLO).filter(ItemCLO.item_id.in_(item_ids) | ItemCLO.clo_id.in_(clo_ids)))
    delete(db.query(CLOPLOMapping).filter(CLOPLOMapping.clo_id.in_(clo_ids)))
    delete(db.query(AssessmentItem).filter(AssessmentItem.id.in_(item_ids)))
    delete(db.query(Enrollment).filter(
        Enrollment.student_id.in_(student_ids) | Enrollment.offering_id.in_(offering_ids)
    ))
    delete(db.query(CourseOffering).filter(CourseOffering.id.in_(offering_ids)))
    delete(db.query(CLO).filter(CLO.id.in_(clo_ids)))
    delete(db.query(CoursePLO).filter(CoursePLO.course_id.in_(course_ids)))
    delete(db.query(StudyPlan).filter(StudyPlan.course_id.in_(course_ids)))
    delete(db.query(Student).filter(Student.id.in_(student_ids)))
    if curriculum is not None:
        ylo_ids = [y.id for y in db.query(YLO.id).filter(YLO.curriculum_id == curriculum.id)]
        delete(db.query(YLOPLOMapping).filter(YLOPLOMapping.ylo_id.in_(ylo_ids)))
        delete(db.query(YLO).filter(YLO.id.in_(ylo_ids)))
        delete(db.query(PLO).filter(PLO.curriculum_id == curriculum.id))
        delete(db.query(Course).filter(Course.id.in_(course_ids)))
        delete(db.query(Curriculum).filter(Curriculum.id == curriculum.id))
    delete(db.query(User).filter(User.id.in_(instructor_ids)))
    db.commit()
    print(
        f"ลบแล้ว: หลักสูตร {1 if curriculum else 0}, วิชา {len(course_ids)}, กลุ่มเรียน {len(offering_ids)}, "
        f"นักศึกษา {len(student_ids)}, อาจารย์ {len(instructor_ids)}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--remove", action="store_true", help="ลบข้อมูลทดสอบชุดนี้ทั้งหมด")
    parser.add_argument("--yes", action="store_true", help="ไม่ต้องถามยืนยัน")
    args = parser.parse_args()

    # สร้างตารางที่ยังไม่มี (เหมือนที่ app/main.py ทำตอนสตาร์ท) - ใช้กับฐานข้อมูลใหม่เอี่ยมได้เลย
    Base.metadata.create_all(bind=engine)

    print(f"ฐานข้อมูลเป้าหมาย: {_describe_target()}")
    db = SessionLocal()
    try:
        if args.remove:
            if _confirm("จะลบข้อมูลทดสอบชุดนี้ทั้งหมด", args.yes):
                remove(db)
            return

        if db.query(Curriculum).filter(Curriculum.name == CURRICULUM_NAME).first() is not None:
            print("มีข้อมูลทดสอบชุดนี้อยู่แล้ว - ไม่สร้างซ้ำ (รันด้วย --remove ก่อนถ้าอยากสร้างใหม่)")
            return
        if not _confirm(
            f"จะสร้างหลักสูตรทดสอบ 1, วิชา {len(COURSES)}, อาจารย์ {len(INSTRUCTORS)}, "
            f"นักศึกษา {len(STUDENTS)} คน",
            args.yes,
        ):
            return
        seed(db)
        print(f"สร้างเสร็จแล้ว - หลักสูตร \"{CURRICULUM_NAME}\"")
    finally:
        db.close()


if __name__ == "__main__":
    main()
