"""
Mock Data Seeding Script for PLO Evaluation System

Run: python seed_data.py
"""
from __future__ import annotations

import random
from decimal import Decimal

from dotenv import load_dotenv
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.auth import hash_password
from app.database import SessionLocal
from app.models import (
    AssessmentItem,
    CLO,
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
    User,
    YLO,
)

load_dotenv()

random.seed(42)

ALL_TABLES = [
    "student_score", "item_clo", "assessment_item", "clo_plo_mapping", "clo",
    "enrollment", "course_offering", "study_plan", "course_plo", "ylo_plo_mapping",
    "course", "ylo", "plo", "student", "curriculum", '"user"',
]

USER_DATA = [
    ("ajarn.somsak", "สมศักดิ์", "ใจดี", "somsak@university.ac.th"),
    ("ajarn.suda", "สุดา", "แสงทอง", "suda@university.ac.th"),
    ("ajarn.wichai", "วิชัย", "รุ่งเรือง", "wichai@university.ac.th"),
]
INSTRUCTOR_PASSWORD = "devpassword123"

ADMIN_USER_DATA = ("admin", "Admin", "User", "admin@university.ac.th")
ADMIN_PASSWORD = "admin123"

PLO_DATA = [
    ("PLO1", "มีความรู้และความเข้าใจในหลักการพื้นฐานทางวิทยาการคอมพิวเตอร์",
     "Demonstrate foundational knowledge of computer science principles"),
    ("PLO2", "วิเคราะห์ปัญหาและกำหนดความต้องการของระบบซอฟต์แวร์ได้อย่างเป็นระบบ",
     "Analyze problems and define software requirements systematically"),
    ("PLO3", "ออกแบบสถาปัตยกรรมซอฟต์แวร์และฐานข้อมูลที่เหมาะสมกับปัญหา",
     "Design software architecture and databases appropriate to the problem"),
    ("PLO4", "พัฒนาและติดตั้งซอฟต์แวร์โดยใช้เครื่องมือและเทคโนโลยีที่ทันสมัย",
     "Implement and deploy software using modern tools and technologies"),
    ("PLO5", "ทดสอบและประเมินคุณภาพซอฟต์แวร์อย่างเป็นระบบ",
     "Test and evaluate software quality systematically"),
    ("PLO6", "สื่อสารผลงานทางวิชาการและวิชาชีพได้อย่างมีประสิทธิภาพทั้งภาษาไทยและอังกฤษ",
     "Communicate technical and professional work effectively in Thai and English"),
    ("PLO7", "ทำงานร่วมกับผู้อื่นและแสดงภาวะผู้นำในการทำงานเป็นทีม",
     "Collaborate with others and demonstrate leadership in team-based work"),
    ("PLO8", "ปฏิบัติงานด้วยจริยธรรมและความรับผิดชอบต่อวิชาชีพและสังคม",
     "Practice with ethics and responsibility toward the profession and society"),
    ("PLO9", "แสวงหาความรู้และปรับตัวต่อเทคโนโลยีใหม่ได้ด้วยตนเองอย่างต่อเนื่อง",
     "Pursue self-directed, lifelong learning and adapt to emerging technologies"),
]

YLO_DATA = [
    (1, "นักศึกษามีความรู้พื้นฐานด้านคณิตศาสตร์ การเขียนโปรแกรมเบื้องต้น และหลักการคอมพิวเตอร์"),
    (2, "นักศึกษาประยุกต์ใช้โครงสร้างข้อมูล อัลกอริทึม และหลักการฐานข้อมูลในการแก้ปัญหา"),
    (3, "นักศึกษาออกแบบและพัฒนาระบบซอฟต์แวร์ขนาดกลางโดยใช้กระบวนการวิศวกรรมซอฟต์แวร์"),
    (4, "นักศึกษาบูรณาการความรู้เพื่อพัฒนาโครงงานที่สมบูรณ์และพร้อมเข้าสู่วิชาชีพ"),
]

COURSE_DATA = [
    ("cs101", "การเขียนโปรแกรมคอมพิวเตอร์เบื้องต้น", "Introduction to Computer Programming", 3, "Core"),
    ("cs102", "โครงสร้างข้อมูลและอัลกอริทึม", "Data Structures and Algorithms", 3, "Core"),
    ("cs103", "คณิตศาสตร์ดิสครีต", "Discrete Mathematics", 3, "Core"),
    ("cs104", "สถาปัตยกรรมคอมพิวเตอร์", "Computer Organization and Architecture", 3, "Core"),
    ("cs201", "การเขียนโปรแกรมเชิงวัตถุ", "Object-Oriented Programming", 3, "Core"),
    ("cs202", "ระบบฐานข้อมูล", "Database Systems", 3, "Core"),
    ("cs203", "ระบบปฏิบัติการ", "Operating Systems", 3, "Core"),
    ("cs204", "เครือข่ายคอมพิวเตอร์", "Computer Networks", 3, "Core"),
    ("cs301", "วิศวกรรมซอฟต์แวร์", "Software Engineering", 3, "Major Required"),
    ("cs302", "การพัฒนาเว็บแอปพลิเคชัน", "Web Application Development", 3, "Major Elective"),
    ("cs303", "ปัญญาประดิษฐ์เบื้องต้น", "Introduction to Artificial Intelligence", 3, "Major Elective"),
    ("cs401", "โครงงานวิศวกรรมซอฟต์แวร์", "Senior Project", 3, "Major Required"),
]

# course_code -> [(plo_code, responsibility_level), ...]
COURSE_PLO_MAP = {
    "cs101": [("PLO1", "mastery"), ("PLO9", "introduce")],
    "cs102": [("PLO1", "reinforce"), ("PLO2", "introduce"), ("PLO4", "introduce")],
    "cs103": [("PLO1", "reinforce")],
    "cs104": [("PLO1", "reinforce")],
    "cs201": [("PLO2", "reinforce"), ("PLO4", "reinforce")],
    "cs202": [("PLO3", "introduce"), ("PLO4", "reinforce")],
    "cs203": [("PLO1", "mastery"), ("PLO4", "reinforce")],
    "cs204": [("PLO2", "reinforce"), ("PLO4", "reinforce")],
    "cs301": [("PLO2", "mastery"), ("PLO3", "mastery"), ("PLO7", "reinforce")],
    "cs302": [("PLO3", "reinforce"), ("PLO4", "mastery"), ("PLO6", "introduce")],
    "cs303": [("PLO2", "reinforce"), ("PLO5", "introduce")],
    "cs401": [
        ("PLO3", "mastery"), ("PLO4", "mastery"), ("PLO5", "mastery"),
        ("PLO6", "mastery"), ("PLO7", "mastery"), ("PLO8", "reinforce"), ("PLO9", "mastery"),
    ],
}

STUDENT_NAMES = [
    ("สมชาย", "ใจดี"),
    ("สมหญิง", "รักเรียน"),
    ("วิชัย", "ตั้งใจ"),
    ("มาลี", "สุขสันต์"),
    ("ธนกร", "เก่งกาจ"),
    ("ปิยะดา", "ขยันเรียน"),
    ("อนุชา", "มานะ"),
    ("ศิริพร", "แสงทอง"),
]

OFFERED_COURSE_CODES = ["cs101", "cs102", "cs103", "cs104", "cs201", "cs202"]

CLO_TEMPLATES = [
    "สามารถอธิบายแนวคิดพื้นฐานของ{course}ได้อย่างถูกต้อง",
    "สามารถประยุกต์ใช้ความรู้ใน{course}เพื่อแก้ไขปัญหาที่กำหนดให้ได้",
    "สามารถออกแบบและพัฒนาชิ้นงานที่เกี่ยวข้องกับ{course}ได้อย่างสมบูรณ์",
]

# (name, type, total_score) - total_score doubles as the point weight (10 + 30 + 60 = 100)
ASSESSMENT_ITEM_DATA = [
    ("Quiz", "quiz", Decimal("10.00")),
    ("Midterm Exam", "midterm", Decimal("30.00")),
    ("Final Exam", "final", Decimal("60.00")),
]

# Second curriculum: courses only, for exercising the Curriculum/Courses page's
# curriculum switcher. No PLOs, students, or scores attached.
CURRICULUM2_NAME = "หลักสูตรวิทยาการคอมพิวเตอร์ (ปรับปรุง 2565)"
CURRICULUM2_YEAR = 2565

COURSE_DATA_2 = [
    ("cs501", "การเรียนรู้ของเครื่องเบื้องต้น", "Introduction to Machine Learning", 3, "Major Elective"),
    ("cs502", "ความมั่นคงปลอดภัยไซเบอร์", "Cybersecurity Fundamentals", 3, "Major Elective"),
    ("cs503", "การประมวลผลบนคลาวด์", "Cloud Computing", 3, "Major Elective"),
    ("cs504", "วิทยาการข้อมูลเบื้องต้น", "Introduction to Data Science", 3, "Core"),
]


def clear_db(db: Session) -> None:
    db.execute(text(f"TRUNCATE TABLE {', '.join(ALL_TABLES)} RESTART IDENTITY CASCADE"))
    db.commit()
    print("cleared all tables")


def seed_users(db: Session) -> list[User]:
    users = [
        User(username=username, password=hash_password(INSTRUCTOR_PASSWORD), first_name=first,
             last_name=last, email=email, role="instructor")
        for username, first, last, email in USER_DATA
    ]
    admin_username, admin_first, admin_last, admin_email = ADMIN_USER_DATA
    admin = User(username=admin_username, password=hash_password(ADMIN_PASSWORD),
                 first_name=admin_first, last_name=admin_last, email=admin_email, role="admin")

    db.add_all(users)
    db.add(admin)
    db.commit()
    print(f"seeded {len(users)} instructor users + 1 admin user")
    return users


def seed_curriculum(db: Session) -> Curriculum:
    curriculum = Curriculum(name="Computer Science 2024", year=2024, is_active=True)
    db.add(curriculum)
    db.commit()
    print("seeded curriculum:", curriculum.name)
    return curriculum


def seed_plos(db: Session, curriculum: Curriculum) -> list[PLO]:
    plos = [
        PLO(curriculum_id=curriculum.id, code=code, description_th=th, description_en=en)
        for code, th, en in PLO_DATA
    ]
    db.add_all(plos)
    db.commit()
    print(f"seeded {len(plos)} PLOs")
    return plos


def seed_ylos(db: Session, curriculum: Curriculum) -> list[YLO]:
    ylos = [
        YLO(curriculum_id=curriculum.id, year_level=year_level, description=description)
        for year_level, description in YLO_DATA
    ]
    db.add_all(ylos)
    db.commit()
    print(f"seeded {len(ylos)} YLOs")
    return ylos


def seed_courses(db: Session, curriculum: Curriculum) -> list[Course]:
    courses = [
        Course(curriculum_id=curriculum.id, course_code=code, name_th=th, name_en=en,
               credit=credit, category=category)
        for code, th, en, credit, category in COURSE_DATA
    ]
    db.add_all(courses)
    db.commit()
    print(f"seeded {len(courses)} courses")
    return courses


def seed_course_plos(db: Session, courses: list[Course], plos: list[PLO]) -> list[CoursePLO]:
    course_by_code = {c.course_code: c for c in courses}
    plo_by_code = {p.code: p for p in plos}
    mappings = [
        CoursePLO(course_id=course_by_code[code].id, plo_id=plo_by_code[plo_code].id,
                   responsibility_level=level)
        for code, plo_list in COURSE_PLO_MAP.items()
        for plo_code, level in plo_list
    ]
    db.add_all(mappings)
    db.commit()
    print(f"seeded {len(mappings)} course-PLO mappings")
    return mappings


def seed_students(db: Session, curriculum: Curriculum) -> list[Student]:
    students = [
        Student(id=f"65000{i + 1:02d}", curriculum_id=curriculum.id, first_name=first,
                last_name=last, cohort_year=2024, current_year_level=1)
        for i, (first, last) in enumerate(STUDENT_NAMES)
    ]
    db.add_all(students)
    db.commit()
    print(f"seeded {len(students)} students")
    return students


def seed_course_offerings(db: Session, courses: list[Course], users: list[User]) -> list[CourseOffering]:
    course_by_code = {c.course_code: c for c in courses}
    offerings = [
        CourseOffering(course_id=course_by_code[code].id, instructor_id=users[i % len(users)].id,
                        cohort_year=2024, academic_year=2024, semester=1, section="1")
        for i, code in enumerate(OFFERED_COURSE_CODES)
    ]
    db.add_all(offerings)
    db.commit()
    print(f"seeded {len(offerings)} course offerings")
    return offerings


def seed_enrollments(db: Session, students: list[Student], offerings: list[CourseOffering]) -> list[Enrollment]:
    enrollments = [
        Enrollment(student_id=student.id, offering_id=offering.id)
        for student in students
        for offering in offerings
    ]
    db.add_all(enrollments)
    db.commit()
    print(f"seeded {len(enrollments)} enrollments")
    return enrollments


def seed_clos(db: Session, courses: list[Course], users: list[User], course_plos: list[CoursePLO]) -> list[CLO]:
    plo_ids_by_course: dict[int, list[int]] = {}
    for cp in course_plos:
        plo_ids_by_course.setdefault(cp.course_id, []).append(cp.plo_id)

    clos = [
        CLO(course_id=course.id, code=f"CLO{i + 1}",
            description=template.format(course=course.name_th),
            created_by=users[idx % len(users)].id)
        for idx, course in enumerate(courses)
        for i, template in enumerate(CLO_TEMPLATES)
    ]
    db.add_all(clos)
    db.commit()

    # Map each CLO to one PLO (weight 100%), or two PLOs (70/30) when the
    # course covers more than one PLO, so weights stay simple but non-trivial.
    mappings: list[CLOPLOMapping] = []
    for clo in clos:
        plo_ids = plo_ids_by_course.get(clo.course_id, [])
        if not plo_ids:
            continue
        clo_index = int(clo.code.removeprefix("CLO")) - 1
        primary = plo_ids[clo_index % len(plo_ids)]
        if len(plo_ids) > 1:
            secondary = plo_ids[(clo_index + 1) % len(plo_ids)]
            mappings.append(CLOPLOMapping(clo_id=clo.id, plo_id=primary, weight_percent=Decimal("70.00")))
            mappings.append(CLOPLOMapping(clo_id=clo.id, plo_id=secondary, weight_percent=Decimal("30.00")))
        else:
            mappings.append(CLOPLOMapping(clo_id=clo.id, plo_id=primary, weight_percent=Decimal("100.00")))
    db.add_all(mappings)
    db.commit()
    print(f"seeded {len(clos)} CLOs and {len(mappings)} CLO-PLO mappings")
    return clos


def seed_assessment_items(db: Session, offerings: list[CourseOffering], clos: list[CLO]) -> list[AssessmentItem]:
    clos_by_course: dict[int, list[CLO]] = {}
    for clo in clos:
        clos_by_course.setdefault(clo.course_id, []).append(clo)

    items = [
        AssessmentItem(offering_id=offering.id, name=name, type=item_type, total_score=total_score)
        for offering in offerings
        for name, item_type, total_score in ASSESSMENT_ITEM_DATA
    ]
    db.add_all(items)
    db.commit()

    # Split each item's weight evenly across its course's CLOs (e.g. 34/33/33 for 3 CLOs).
    item_clos: list[ItemCLO] = []
    item_idx = 0
    for offering in offerings:
        course_clos = clos_by_course.get(offering.course_id, [])
        n = len(course_clos)
        for _ in ASSESSMENT_ITEM_DATA:
            item = items[item_idx]
            item_idx += 1
            if n == 0:
                continue
            base, remainder = divmod(100, n)
            for j, clo in enumerate(course_clos):
                weight = base + (remainder if j == n - 1 else 0)
                item_clos.append(ItemCLO(item_id=item.id, clo_id=clo.id, weight_percent=Decimal(weight)))
    db.add_all(item_clos)
    db.commit()
    print(f"seeded {len(items)} assessment items and {len(item_clos)} item-CLO mappings")
    return items


def seed_student_scores(db: Session, enrollments: list[Enrollment], items: list[AssessmentItem]) -> list[StudentScore]:
    items_by_offering: dict[int, list[AssessmentItem]] = {}
    for item in items:
        items_by_offering.setdefault(item.offering_id, []).append(item)

    # 40-100 is treated as a percentage of each item's max score, so a
    # student's obtained score never exceeds that item's total_score.
    scores = []
    for enrollment in enrollments:
        for item in items_by_offering.get(enrollment.offering_id, []):
            percent = Decimal(random.randint(40, 100))
            obtained = (item.total_score * percent / Decimal(100)).quantize(Decimal("0.01"))
            scores.append(StudentScore(item_id=item.id, student_id=enrollment.student_id, score_obtained=obtained))
    db.add_all(scores)
    db.commit()
    print(f"seeded {len(scores)} student scores")
    return scores


def seed_second_curriculum(db: Session) -> Curriculum:
    curriculum = Curriculum(name=CURRICULUM2_NAME, year=CURRICULUM2_YEAR, is_active=True)
    db.add(curriculum)
    db.commit()

    courses = [
        Course(curriculum_id=curriculum.id, course_code=code, name_th=th, name_en=en,
               credit=credit, category=category)
        for code, th, en, credit, category in COURSE_DATA_2
    ]
    db.add_all(courses)
    db.commit()
    print(f"seeded second curriculum '{curriculum.name}' with {len(courses)} courses")
    return curriculum


def main() -> None:
    db = SessionLocal()
    try:
        clear_db(db)
        users = seed_users(db)
        curriculum = seed_curriculum(db)
        plos = seed_plos(db, curriculum)
        seed_ylos(db, curriculum)
        courses = seed_courses(db, curriculum)
        course_plos = seed_course_plos(db, courses, plos)
        students = seed_students(db, curriculum)
        offerings = seed_course_offerings(db, courses, users)
        enrollments = seed_enrollments(db, students, offerings)
        clos = seed_clos(db, courses, users, course_plos)
        items = seed_assessment_items(db, offerings, clos)
        seed_student_scores(db, enrollments, items)
        seed_second_curriculum(db)
        print("\nSeeding complete.")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
