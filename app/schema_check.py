"""
ทำอะไร : เทียบ schema จริงในฐานข้อมูล (live) กับ SQLAlchemy models ใน app/models/ (Base.metadata) - หา
         table/column ที่โมเดลคาดหวังไว้แต่ไม่มีจริงในฐานข้อมูล

เชื่อมกับ : เรียกจาก 2 ที่ - (1) app/main.py ตอน startup ของแอป (log ERROR ทุก gap ที่เจอ ไม่ crash แอป
            ให้ endpoint อื่นที่ไม่พึ่ง schema ที่หายไปยังใช้งานได้ปกติต่อไป) (2) scripts/check_schema.py
            เป็น CLI แยกต่างหาก เรียกเองก่อน deploy ได้ (exit code ไม่เป็นศูนย์ถ้าเจอ gap) - อ่าน schema
            จริงผ่าน SQLAlchemy Inspector เท่านั้น (information_schema ใต้ฝากระโปรง) ไม่แตะข้อมูลเลย

            เกิดจากบั๊กจริงที่เจอ 2026-09 (regression PLODashboard.jsx) : production ไม่มีคอลัมน์
            clo_plo_mapping.weight_percent อยู่นาน เพราะ scripts/migrate_add_clo_plo_mapping_weight.py
            ไม่เคยถูกรันหลัง deploy โค้ดที่เพิ่ม column นี้เข้า model - ไม่มีใครสังเกตจนกว่า endpoint ที่
            ใช้คอลัมน์นั้นถูกเรียกแล้วพัง (500 ที่วินิจฉัยยากเพราะตอนนั้นไม่มี logging เลยด้วย - ดู
            app/main.py's _CatchUnhandledExceptionsMiddleware)

ถ้าแก้ : เช็คแค่ "ตาราง/คอลัมน์ที่โมเดลคาดหวังมีอยู่จริงไหม" เท่านั้น (ไม่เช็ค type/nullable/constraint
         ละเอียด - schema เปลี่ยนบ่อยกว่าที่จะคุ้มค่า maintain เช็คละเอียดขนาดนั้น แค่ "หายไปทั้งคอลัมน์"
         ก็ครอบคลุมสาเหตุ 500 ประเภทนี้เกือบทั้งหมดแล้ว) ไม่ต้องแก้ไฟล์นี้เองตอนเพิ่ม model ใหม่ (อ่านจาก
         Base.metadata อัตโนมัติผ่าน app/models/__init__.py ที่ import ทุก model ไว้แล้ว ไม่ hardcode
         รายชื่อตาราง/คอลัมน์ไว้ในนี้)
"""
from __future__ import annotations

from sqlalchemy import inspect
from sqlalchemy.engine import Engine

from app.database import Base
import app.models  # noqa: F401 - import ให้ทุก model ลงทะเบียนคอลัมน์ไว้ใน Base.metadata ก่อนเช็ค


def check_schema(bind: Engine) -> list[str]:
    """คืน list ของข้อความ gap (ว่าง = schema ตรงกับโมเดลทั้งหมด) - อ่านอย่างเดียว ไม่เขียน/ไม่ล็อกอะไร"""
    inspector = inspect(bind)
    live_tables = set(inspector.get_table_names())

    gaps: list[str] = []
    for table_name, table in Base.metadata.tables.items():
        if table_name not in live_tables:
            gaps.append(f"ตาราง '{table_name}' หายไปจากฐานข้อมูล (โมเดลคาดหวังไว้)")
            continue
        live_columns = {col["name"] for col in inspector.get_columns(table_name)}
        for column in table.columns:
            if column.name not in live_columns:
                gaps.append(f"คอลัมน์ '{table_name}.{column.name}' หายไปจากฐานข้อมูล (โมเดลคาดหวังไว้)")
    return gaps
