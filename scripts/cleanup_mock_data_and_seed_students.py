"""
Cleanup mock demo data seeded by seed_data.py from curriculum_id=1, and
replace the student roster with the real cohort's ID range (names left
blank - filled in manually later).

- Deletes the 12 mock courses (cs101-cs401) under curriculum_id=1. DB-level
  ON DELETE CASCADE takes care of course_plo, study_plan, course_offering,
  assessment_item, item_clo, student_score, clo, clo_plo_mapping.
- Deletes the 8 mock demo students (6500001-6500008). Cascades to
  enrollment, student_score.
- Upserts student 660112230001..660112230070 (curriculum_id=1, cohort_year=66,
  current_year_level=4) with first_name/last_name cleared to "" - including
  660112230012, which already existed with a real name (cleared per explicit
  user confirmation, since it falls inside the new range).

Idempotent: rerunning finds no mock rows left to delete, and re-upserts the
same 70 blank-name student rows (0 changes on repeat runs).

Run: python scripts/cleanup_mock_data_and_seed_students.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import SessionLocal
from app.models import Course, Student

CURRICULUM_ID = 1

MOCK_COURSE_CODES = [
    "cs101", "cs102", "cs103", "cs104",
    "cs201", "cs202", "cs203", "cs204",
    "cs301", "cs302", "cs303", "cs401",
]

MOCK_STUDENT_IDS = [f"65000{i:02d}" for i in range(1, 9)]

NEW_STUDENT_IDS = [f"660112230{i:03d}" for i in range(1, 71)]

COHORT_YEAR = 66
CURRENT_YEAR_LEVEL = 4


def delete_mock_courses(db) -> int:
    courses = (
        db.query(Course)
        .filter(Course.curriculum_id == CURRICULUM_ID, Course.course_code.in_(MOCK_COURSE_CODES))
        .all()
    )
    count = len(courses)
    for course in courses:
        db.delete(course)
    db.flush()
    return count


def delete_mock_students(db) -> int:
    students = db.query(Student).filter(Student.id.in_(MOCK_STUDENT_IDS)).all()
    count = len(students)
    for student in students:
        db.delete(student)
    db.flush()
    return count


def upsert_students(db) -> tuple[int, int]:
    created = updated = 0
    for student_id in NEW_STUDENT_IDS:
        student = db.query(Student).filter(Student.id == student_id).one_or_none()
        if student is None:
            db.add(
                Student(
                    id=student_id,
                    curriculum_id=CURRICULUM_ID,
                    first_name="",
                    last_name="",
                    cohort_year=COHORT_YEAR,
                    current_year_level=CURRENT_YEAR_LEVEL,
                )
            )
            created += 1
            continue
        # Preserve names already on file (e.g. real names entered manually) -
        # only fall back to blank for students that don't have one yet.
        has_real_name = bool(student.first_name) or bool(student.last_name)
        fields = [
            ("curriculum_id", CURRICULUM_ID),
            ("cohort_year", COHORT_YEAR),
            ("current_year_level", CURRENT_YEAR_LEVEL),
        ]
        if not has_real_name:
            fields.append(("first_name", ""))
            fields.append(("last_name", ""))
        changed = False
        for field, value in fields:
            if getattr(student, field) != value:
                setattr(student, field, value)
                changed = True
        if changed:
            updated += 1
    db.flush()
    return created, updated


def main() -> None:
    db = SessionLocal()
    try:
        deleted_courses = delete_mock_courses(db)
        deleted_students = delete_mock_students(db)
        created, updated = upsert_students(db)
        db.commit()

        print(f"mock course ลบ: {deleted_courses} วิชา "
              f"(cascade: course_plo, study_plan, course_offering, assessment_item, "
              f"item_clo, student_score, clo, clo_plo_mapping)")
        print(f"mock student ลบ: {deleted_students} คน (cascade: enrollment, student_score)")
        print(f"student ({NEW_STUDENT_IDS[0]}-{NEW_STUDENT_IDS[-1]}): created {created}, updated {updated}")

        total_courses = db.query(Course).filter(Course.curriculum_id == CURRICULUM_ID).count()
        total_students = db.query(Student).filter(Student.curriculum_id == CURRICULUM_ID).count()
        print("--- sanity check ---")
        print(f"course ทั้งหมดใน curriculum_id={CURRICULUM_ID}: {total_courses}")
        print(f"student ทั้งหมดใน curriculum_id={CURRICULUM_ID}: {total_students}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
