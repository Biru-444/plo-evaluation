"""
CLI สำหรับ app/schema_check.py::check_schema() - รันเองก่อน deploy ได้ (เช็ค schema ของ DATABASE_URL
ที่ตั้งไว้ตอนนี้ เทียบกับ SQLAlchemy models) exit code ไม่เป็นศูนย์ถ้าเจอ gap (เช่น migration ค้างไม่ได้รัน)

ตัวอย่างเช็ค production ก่อน deploy: DATABASE_URL="<production URL>" python scripts/check_schema.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import engine
from app.schema_check import check_schema


def main() -> int:
    gaps = check_schema(engine)
    if not gaps:
        print("Schema ตรงกับ SQLAlchemy models ทั้งหมด - ไม่มี gap")
        return 0

    print(f"พบ {len(gaps)} จุดที่ schema ไม่ตรงกับโมเดล (อาจมี scripts/migrate_*.py ค้างไม่ได้รัน):")
    for gap in gaps:
        print(f"  - {gap}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
