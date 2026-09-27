"""
ทำอะไร : เช็คว่า CLO กับ PLO ที่กำลังจะผูกกัน (clo_plo_mapping) อยู่หลักสูตรเดียวกันไหม
         (clo.course.curriculum_id ต้องตรงกับ plo.curriculum_id เป๊ะ) ถ้าไม่ตรง raise 422 ทันที -
         ต่างจาก app/services/domain_category_check.py ที่แค่เตือนไม่บล็อก อันนี้บล็อกจริง เพราะข้าม
         หลักสูตรไม่มีความหมายอะไรเลย (การคำนวณ % บรรลุ PLO นับตาม curriculum เป็นหน่วย)

เชื่อมกับ : เรียกจาก 3 จุดที่รับ clo_id+plo_id คู่จาก client โดยตรงแล้วสร้างแถว clo_plo_mapping ใหม่:
            1. app/routes/clo_plo_mapping.py::create_clo_plo_mapping (POST /clo-plo-mapping)
            2. app/routes/clo.py::create_clo (plo_ids bulk-bind ตอนสร้าง CLO)
            3. app/routes/clo.py::update_clo (plo_ids bulk-bind ตอนแก้ไข CLO)

            ไม่ต้องเรียกจาก app/routes/course_import.py (มคอ.3 import) เพราะที่นั่น query PLO กรองด้วย
            payload.curriculum_id อยู่แล้วตั้งแต่ต้น (ข้ามหลักสูตรไม่ได้โดยโครงสร้าง ไม่ต้องเช็คซ้ำ)

ถ้าแก้ : ต้องเรียกตอนที่ clo/plo ยังอยู่ใน session ที่เปิดอยู่ (ใช้ clo.course relationship lazy-load -
         ใช้ได้ทั้งกับ CLO ที่เพิ่ง db.flush() ไปหมาดๆ และ CLO ที่ query มาจาก DB ตรงๆ)
"""
from __future__ import annotations

from fastapi import HTTPException

from app.models import CLO, PLO


def require_same_curriculum(clo: CLO, plo: PLO) -> None:
    if clo.course.curriculum_id != plo.curriculum_id:
        raise HTTPException(
            status_code=422,
            detail="CLO และ PLO ต้องอยู่ในหลักสูตรเดียวกัน",
        )
