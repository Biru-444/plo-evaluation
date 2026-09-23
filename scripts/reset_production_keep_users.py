"""
ทำอะไร : ล้างข้อมูลทั้งหมดในฐานข้อมูล ยกเว้น user ที่ role='admin' (ลบ user ที่เป็น instructor ทั้งหมด
         ด้วย รวมถึง test/demo account ที่มีอยู่ตอนนี้) เตรียมฐานข้อมูล production ให้ว่างเปล่าก่อนนำเข้า
         ข้อมูลจริงจาก มคอ.3 - **นี่คือ Phase A เท่านั้น (อ่านอย่างเดียว/dry-run) ยังไม่มี Phase B ที่รันจริง
         บน production - ต้องได้รับอนุมัติแยกต่างหากก่อนรัน --apply กับ production DATABASE_URL เสมอ**

ลำดับการลบ (พึ่ง ON DELETE CASCADE ของ schema เองเกือบทั้งหมด - ดู "ถ้าแก้" ด้านล่างสำหรับ FK ที่เกี่ยวข้อง
ทุกจุด ยืนยันด้วย _fk_blockers() ที่ query pg_catalog จริงตอน dry-run ทุกครั้ง ไม่พึ่งความจำอย่างเดียว) :
  1. DELETE FROM student - cascade ไปที่ enrollment, student_score อัตโนมัติ (ondelete=CASCADE ทั้งคู่)
     ต้องลบก่อน curriculum เสมอ เพราะ student.curriculum_id เป็น ondelete=RESTRICT (กันลบหลักสูตรที่ยังมี
     นักศึกษาอยู่โดยไม่ได้ตั้งใจ - ดู app/models/curriculum.py) ถ้าไม่ลบ student ก่อน ขั้นตอนที่ 2 จะพังทันที
  2. DELETE FROM curriculum - cascade ไปที่ plo, ylo, ylo_plo_mapping, course, course_plo, study_plan,
     course_offering (ผ่าน course), clo (ผ่าน course), clo_plo_mapping (ผ่าน clo), assessment_item (ผ่าน
     course_offering), item_clo (ผ่าน assessment_item และ clo) อัตโนมัติทั้งหมด (ondelete=CASCADE ทุกจุด)
  3. DELETE FROM "user" WHERE role != 'admin' - ปลอดภัยแล้วหลังขั้นตอน 2 เพราะ clo.created_by และ
     course_offering.instructor_id (ทั้งคู่ ondelete=RESTRICT ชี้มาที่ user.id) ถูกลบไปหมดแล้วในขั้นตอน 2
     (clo/course_offering เป็นลูกของ curriculum ผ่าน course) ไม่มีอะไรเหลือให้ RESTRICT บล็อกการลบ user
     อีกต่อไป

เชื่อมกับ : หลังรีเซ็ตแล้ว บัญชีอาจารย์จะถูกสร้างใหม่อัตโนมัติตอนนำเข้าไฟล์รายชื่อ (roster import) รอบถัดไป
            ผ่าน app/routes/roster_import.py - ทุกชื่ออาจารย์ในไฟล์ที่ไม่ตรงกับ user ที่มีอยู่แล้ว (เทียบ
            first_name+last_name) จะถูกสร้าง user role='instructor' ใหม่ พร้อมรหัสผ่านชั่วคราวสุ่ม
            (secrets.token_urlsafe(9), บรรทัด ~337) username รูปแบบ "ajarn{id}" - รหัสผ่านชั่วคราวนี้
            ส่งกลับมาใน response field `new_instructor_credentials` (บรรทัด ~553) ซึ่ง
            AdminRosterImport.jsx แสดงให้แอดมินเห็น/คัดลอกไปแจ้งอาจารย์ต่อ ไม่มีที่เก็บถาวรอื่นอีก (ถ้าไม่
            คัดลอกออกไปตอนนั้น ต้องรีเซ็ตรหัสผ่านใหม่ทีหลังแทน - ไม่มีทางดึงรหัสเดิมย้อนหลังได้)

ถ้าแก้ : ลำดับนี้สำคัญมาก ห้ามสลับ - ขณะเขียนสคริปต์นี้มี 2 จุดที่ ondelete=RESTRICT ชี้มาที่ user.id
         (clo.created_by, course_offering.instructor_id) และ 1 จุดที่ชี้มาที่ curriculum.id
         (student.curriculum_id) - _fk_blockers() query pg_catalog จริงทุกครั้งที่รัน dry-run เพื่อจับ FK
         RESTRICT/NO ACTION ใหม่ที่อาจถูกเพิ่มเข้ามาทีหลังโดยไม่ได้แก้สคริปต์นี้ตาม (เช่นถ้ามีคนเพิ่ม
         ตาราง/FK ใหม่ชี้มาที่ user หรือ curriculum แบบ RESTRICT) - ถ้าเจอจุดที่ไม่รู้จัก สคริปต์จะรายงาน
         เป็น "blocker" และปฏิเสธรัน --apply จนกว่าจะแก้ลำดับการลบให้ครอบคลุมก่อน

         --dry-run (ค่าเริ่มต้น) : อ่านอย่างเดียวทั้งหมด (SET TRANSACTION READ ONLY) รายงานจำนวนแถวที่จะ
         ถูกลบต่อตาราง + blocker ที่เจอ ไม่ลบอะไรจริงแม้แต่แถวเดียว
         --apply : ลบจริงทั้ง 3 คำสั่งในทรานแซกชันเดียว (engine.begin() - พังตรงไหน rollback หมดทั้งก้อน)
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text

from app.database import engine

# FK (child_table, child_column, parent_table) ที่ RESTRICT/NO ACTION ชี้มาที่ user/curriculum ที่ลำดับ
# การลบ 3 ขั้นตอนด้านบนจัดการไว้แล้ว - ใช้เทียบกับผลจริงจาก pg_catalog ใน _fk_blockers()
KNOWN_HANDLED_RESTRICTS = {
    ("clo", "created_by", "user"),
    ("course_offering", "instructor_id", "user"),
    ("student", "curriculum_id", "curriculum"),
}

# ลำดับตารางที่จะถูกลบ (ตรงหรือผ่าน cascade) - ใช้รายงานจำนวนแถวตอน dry-run เท่านั้น ไม่ได้ใช้สั่ง DELETE
# ตรงๆ ทีละตาราง (การลบจริงสั่งแค่ 3 คำสั่งที่ตารางแม่ - ดู module docstring)
AFFECTED_TABLES_IN_CASCADE_ORDER = [
    "student",
    "enrollment",
    "student_score",
    "curriculum",
    "plo",
    "ylo",
    "ylo_plo_mapping",
    "course",
    "course_plo",
    "study_plan",
    "course_offering",
    "clo",
    "clo_plo_mapping",
    "assessment_item",
    "item_clo",
]


def _fk_blockers(conn) -> list[tuple[str, str, str, str]]:
    """หา FK จริงในฐานข้อมูล (ไม่ใช่แค่จากโค้ด model) ที่ delete_rule เป็น RESTRICT หรือ NO ACTION
    (ค่า default ถ้าไม่ระบุ ondelete เลย - พฤติกรรมเหมือน RESTRICT) ที่ parent table เป็น user หรือ
    curriculum - คืนเฉพาะจุดที่ "ยังไม่รู้จัก" (ไม่อยู่ใน KNOWN_HANDLED_RESTRICTS) เป็น blocker จริงที่ต้อง
    แก้ลำดับการลบก่อนถึงจะรัน --apply ได้"""
    rows = conn.execute(
        text(
            """
            SELECT
                tc.table_name AS child_table,
                kcu.column_name AS child_column,
                ccu.table_name AS parent_table,
                rc.delete_rule
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
                ON tc.constraint_name = kcu.constraint_name AND tc.table_schema = kcu.table_schema
            JOIN information_schema.constraint_column_usage ccu
                ON tc.constraint_name = ccu.constraint_name AND tc.table_schema = ccu.table_schema
            JOIN information_schema.referential_constraints rc
                ON tc.constraint_name = rc.constraint_name AND tc.table_schema = rc.constraint_schema
            WHERE tc.constraint_type = 'FOREIGN KEY'
              AND tc.table_schema = 'public'
              AND ccu.table_name IN ('user', 'curriculum')
              AND rc.delete_rule IN ('RESTRICT', 'NO ACTION')
            ORDER BY tc.table_name, kcu.column_name
            """
        )
    ).all()

    unknown = []
    for child_table, child_column, parent_table, delete_rule in rows:
        key = (child_table, child_column, parent_table)
        if key not in KNOWN_HANDLED_RESTRICTS:
            unknown.append((child_table, child_column, parent_table, delete_rule))
    return unknown


def _table_count(conn, table: str) -> int:
    return conn.execute(text(f'SELECT count(*) FROM "{table}"')).scalar()


def _dry_run() -> None:
    with engine.connect() as conn:
        conn.execute(text("SET TRANSACTION READ ONLY"))

        print("=== reset_production_keep_users.py --dry-run (อ่านอย่างเดียว ไม่ลบอะไรจริง) ===\n")

        blockers = _fk_blockers(conn)
        if blockers:
            print("!! พบ FK ที่ RESTRICT/NO ACTION ชี้มาที่ user/curriculum ที่ลำดับการลบยังไม่ได้จัดการ:")
            for child_table, child_column, parent_table, delete_rule in blockers:
                print(f"   - {child_table}.{child_column} -> {parent_table} ({delete_rule})")
            print("   ต้องแก้ลำดับการลบในสคริปต์นี้ก่อน ห้ามรัน --apply จนกว่าจะแก้\n")
        else:
            print("FK check: ไม่พบ blocker ใหม่ - ลำดับการลบ 3 ขั้นตอนครอบคลุม RESTRICT ที่มีอยู่ทั้งหมดแล้ว\n")

        print("จำนวนแถวที่จะถูกลบต่อตาราง (ตรงหรือผ่าน cascade):")
        total_rows = 0
        for table in AFFECTED_TABLES_IN_CASCADE_ORDER:
            count = _table_count(conn, table)
            total_rows += count
            print(f"   {table}: {count}")
        print(f"   รวม: {total_rows} แถว จาก {len(AFFECTED_TABLES_IN_CASCADE_ORDER)} ตาราง\n")

        role_counts = conn.execute(
            text('SELECT role, count(*) FROM "user" GROUP BY role ORDER BY role')
        ).all()
        admin_count = next((c for r, c in role_counts if r == "admin"), 0)
        non_admin_count = sum(c for r, c in role_counts if r != "admin")
        print("user (บัญชีผู้ใช้):")
        for role, count in role_counts:
            marker = "-> เก็บไว้" if role == "admin" else "-> จะถูกลบ"
            print(f"   role={role}: {count} คน {marker}")
        print(f"   สรุป: เก็บ admin {admin_count} คน, ลบบัญชีอื่น {non_admin_count} คน\n")

        print("ลำดับคำสั่งลบจริงตอน --apply (3 คำสั่ง ในทรานแซกชันเดียว):")
        print('   1. DELETE FROM student')
        print('   2. DELETE FROM curriculum')
        print('   3. DELETE FROM "user" WHERE role != \'admin\'')

        conn.execute(text("ROLLBACK"))


def _print_counts(conn, label: str) -> None:
    print(f"จำนวนแถว{label}:")
    total = 0
    for table in AFFECTED_TABLES_IN_CASCADE_ORDER:
        count = _table_count(conn, table)
        total += count
        print(f"   {table}: {count}")
    print(f"   รวม: {total} แถว")
    role_counts = conn.execute(
        text('SELECT role, count(*) FROM "user" GROUP BY role ORDER BY role')
    ).all()
    print("   user by role:", ", ".join(f"{r}={c}" for r, c in role_counts) or "(ไม่มี)")


def _apply() -> None:
    with engine.begin() as conn:
        # เช็ค blocker ซ้ำอีกครั้งในทรานแซกชันเดียวกับที่จะลบจริง (ไม่ใช้ผลจาก dry-run รอบก่อนหน้า ซึ่ง
        # อาจรันคนละครั้ง/คนละเวลากัน) - เจอ blocker ใหม่ที่ไม่รู้จัก ยกเลิกทันที ไม่ลบอะไรเลย (raise ทำให้
        # engine.begin() rollback ทรานแซกชันทั้งหมดอัตโนมัติ)
        blockers = _fk_blockers(conn)
        if blockers:
            print("!! พบ FK blocker ที่ยังไม่ได้จัดการ - ยกเลิกการลบทันที ไม่มีอะไรถูกลบ:")
            for child_table, child_column, parent_table, delete_rule in blockers:
                print(f"   - {child_table}.{child_column} -> {parent_table} ({delete_rule})")
            raise RuntimeError("พบ FK blocker ที่ยังไม่ได้จัดการ - ยกเลิกการลบ (ดู stdout ด้านบน)")

        print("=== reset_production_keep_users.py --apply (ลบจริง) ===\n")
        _print_counts(conn, "ก่อนลบ")
        print()

        result_student = conn.execute(text("DELETE FROM student"))
        result_curriculum = conn.execute(text("DELETE FROM curriculum"))
        result_user = conn.execute(text("DELETE FROM \"user\" WHERE role != 'admin'"))
        print(
            f"ลบแล้ว: student {result_student.rowcount} แถว (ตรงๆ), "
            f"curriculum {result_curriculum.rowcount} แถว (ตรงๆ - ที่เหลือลบผ่าน cascade), "
            f"user {result_user.rowcount} แถว (ตรงๆ)\n"
        )

        _print_counts(conn, "หลังลบ")
        # commit เกิดอัตโนมัติตอนออกจาก engine.begin() context โดยไม่มี exception


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--apply", action="store_true", help="ลบจริง (Phase A ยังไม่รองรับ - ตั้งใจ raise error ถ้าใช้)"
    )
    args = parser.parse_args()

    if args.apply:
        _apply()
    else:
        _dry_run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
