"""
ทำอะไร : normalize plo.code / clo.code ที่มีอยู่แล้วในฐานข้อมูลให้เป็น canonical form เดียวกับที่ทุก
         write/comparison path ใหม่ใช้ (uppercase, ไม่มีช่องว่าง, เลขไทยแปลงเป็นอารบิก - ดู
         app/services/code_normalize.py) แก้บั๊กจริงที่เจอ 2026-09-23: มคอ.2 import เคยบันทึก
         plo.code เป็น "PLO 1".."PLO 9" (มีช่องว่าง) ทำให้ มคอ.3 import ที่ Gemini แกะรหัส PLO แบบไม่มี
         ช่องว่าง (เช่น "PLO4") จับคู่กับ plo.code เดิมไม่ติด (exact string compare)

เชื่อมกับ : เรียก normalize_code() ตัวเดียวกับที่ app/schemas/plo.py, app/schemas/clo.py,
            app/schemas/curriculum_import.py, app/schemas/course_import.py ใช้ (field_validator) - ไม่มี
            กฎ normalize แยกชุดที่นี่

ถ้าแก้ : Idempotent - เทียบ code ปัจจุบันกับ normalize_code(code ปัจจุบัน) ก่อนเสมอ แถวที่ normalize
         แล้วเท่าเดิม (ไม่ต้องแก้) จะไม่ถูกนับเป็นแถวที่ต้องอัปเดต

         เช็คชนกันก่อนเขียนจริงเสมอ (dry-run และ apply เช็คเหมือนกัน) : ถ้า normalize แล้วสองแถวขึ้นไปใน
         curriculum เดียวกัน (สำหรับ plo) หรือ course เดียวกัน (สำหรับ clo) ได้ code ซ้ำกัน (ชน
         UniqueConstraint จริง) จะรายงานเป็น "ชนกัน - ต้องแก้มือก่อน" และไม่แตะแถวที่ชนกันเลยสักแถว (แถว
         อื่นที่ไม่ชนยังอัปเดตได้ตามปกติถ้า --apply) เพราะการชนแบบนี้แปลว่ามีข้อมูลซ้ำซ้อนจริงในระบบอยู่
         ก่อนแล้ว (เช่น "PLO4" กับ "PLO 4" สองแถวแยกกันในหลักสูตรเดียวกัน) ต้องให้แอดมินตัดสินใจเองว่าจะ
         เก็บแถวไหน ไม่ใช่ให้สคริปต์เดาลบ/รวมให้เอง

         --dry-run (ค่าเริ่มต้น) : อ่านอย่างเดียว รายงานแถวที่จะเปลี่ยน + แถวที่ชนกัน ไม่เขียนอะไรจริง
         --apply : อัปเดตจริงทั้งหมดในทรานแซกชันเดียว (engine.begin()) ข้ามแถวที่ชนกัน (ถ้ามี) แล้วเตือน
"""
from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text

from app.database import engine
from app.services.code_normalize import normalize_code


def _plan(conn) -> tuple[list[tuple[int, str, str]], list[tuple[int, str, str]], list[str], list[str]]:
    """คืน (plo_changes, clo_changes, plo_collision_messages, clo_collision_messages)
    *_changes = [(id, old_code, new_code), ...] เฉพาะแถวที่ normalize แล้วต่างจากเดิมจริงๆ และไม่ชนกับ
    แถวอื่นในกลุ่มเดียวกัน (curriculum สำหรับ plo, course สำหรับ clo)"""
    plo_rows = conn.execute(text("SELECT id, curriculum_id, code FROM plo ORDER BY curriculum_id, id")).all()
    clo_rows = conn.execute(text("SELECT id, course_id, code FROM clo ORDER BY course_id, id")).all()

    def _build(rows, group_col_name: str):
        # normalized_by_group[group_id][normalized_code] = [(id, old_code), ...] - รวมทั้งแถวที่ไม่ต้อง
        # เปลี่ยน (normalize แล้วเท่าเดิม) ด้วย เพื่อเช็คชนกับแถวที่ "จะ" เปลี่ยนเข้ามาอยู่ code เดียวกัน
        normalized_by_group: dict[int, dict[str, list[tuple[int, str]]]] = defaultdict(lambda: defaultdict(list))
        for row_id, group_id, old_code in rows:
            normalized_by_group[group_id][normalize_code(old_code)].append((row_id, old_code))

        changes = []
        collisions = []
        for group_id, by_normalized in normalized_by_group.items():
            for new_code, entries in by_normalized.items():
                if len(entries) > 1:
                    ids_and_codes = ", ".join(f"id={rid} code={old!r}" for rid, old in entries)
                    collisions.append(
                        f"{group_col_name}={group_id}: {len(entries)} แถวชนกันที่ code normalize แล้ว "
                        f"= {new_code!r} ({ids_and_codes}) - ข้ามทั้งหมด ต้องแก้มือก่อน"
                    )
                    continue
                row_id, old_code = entries[0]
                if old_code != new_code:
                    changes.append((row_id, old_code, new_code))
        return changes, collisions

    plo_changes, plo_collisions = _build(plo_rows, "curriculum_id")
    clo_changes, clo_collisions = _build(clo_rows, "course_id")
    return plo_changes, clo_changes, plo_collisions, clo_collisions


def _dry_run() -> None:
    with engine.connect() as conn:
        conn.execute(text("SET TRANSACTION READ ONLY"))
        plo_changes, clo_changes, plo_collisions, clo_collisions = _plan(conn)
        conn.execute(text("ROLLBACK"))

    print("=== normalize_plo_clo_codes.py --dry-run (อ่านอย่างเดียว ไม่แก้อะไรจริง) ===\n")

    print(f"plo.code ที่จะเปลี่ยน ({len(plo_changes)} แถว):")
    for row_id, old_code, new_code in plo_changes:
        print(f"   id={row_id}: {old_code!r} -> {new_code!r}")
    if not plo_changes:
        print("   (ไม่มี - normalize แล้วทุกแถว)")

    print(f"\nclo.code ที่จะเปลี่ยน ({len(clo_changes)} แถว):")
    for row_id, old_code, new_code in clo_changes:
        print(f"   id={row_id}: {old_code!r} -> {new_code!r}")
    if not clo_changes:
        print("   (ไม่มี - normalize แล้วทุกแถว)")

    if plo_collisions or clo_collisions:
        print(f"\n!! พบการชนกัน ({len(plo_collisions) + len(clo_collisions)} กลุ่ม) - แถวเหล่านี้จะถูกข้าม")
        print("   ตอน --apply เสมอ จนกว่าจะแก้ข้อมูลซ้ำซ้อนด้วยมือก่อน:")
        for msg in plo_collisions + clo_collisions:
            print(f"   - {msg}")
    else:
        print("\nไม่พบการชนกัน - ปลอดภัยที่จะรัน --apply")


def _apply() -> None:
    with engine.begin() as conn:
        plo_changes, clo_changes, plo_collisions, clo_collisions = _plan(conn)

        if plo_collisions or clo_collisions:
            print(f"!! พบการชนกัน ({len(plo_collisions) + len(clo_collisions)} กลุ่ม) - ข้ามแถวเหล่านี้:")
            for msg in plo_collisions + clo_collisions:
                print(f"   - {msg}")
            print()

        for row_id, old_code, new_code in plo_changes:
            conn.execute(text("UPDATE plo SET code = :new_code WHERE id = :id"), {"new_code": new_code, "id": row_id})
        for row_id, old_code, new_code in clo_changes:
            conn.execute(text("UPDATE clo SET code = :new_code WHERE id = :id"), {"new_code": new_code, "id": row_id})

        print(f"อัปเดต plo.code แล้ว {len(plo_changes)} แถว, clo.code แล้ว {len(clo_changes)} แถว")
        if plo_collisions or clo_collisions:
            print(f"ข้ามไป {len(plo_collisions) + len(clo_collisions)} กลุ่มที่ชนกัน (ดูรายละเอียดด้านบน)")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="แก้จริง (ไม่ใส่ = dry-run เท่านั้น)")
    args = parser.parse_args()

    if args.apply:
        _apply()
    else:
        _dry_run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
