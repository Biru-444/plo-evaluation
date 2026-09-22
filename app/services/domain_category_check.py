"""
ทำอะไร : เทียบ clo.domain (knowledge/skills/ethics/character) กับ plo.category (ข้อความไทยอิสระ -
         ปกติเป็นหนึ่งใน "ความรู้"/"ทักษะ"/"จริยธรรม"/"ลักษณะบุคคล" หรือ "อื่นๆ"/ข้อความที่พิมพ์เอง)
         แล้วคืนข้อความเตือนถ้าไม่ตรงกัน (ไม่บล็อกอะไร แค่เตือนให้แอดมินเห็น) — ดู
         แผนการแก้ไขครั้งใหญ่-PLO-CLO.md Workstream 4

เชื่อมกับ : ฟังก์ชันเดียวนี้ถูกเรียกใช้ 2 จุด (ตามที่แผนระบุ - ไม่เขียนตรรกะเทียบซ้ำสองชุด):
            1. GET /clo-plo-mapping/domain-check - แอดมินผูก CLO-PLO เองด้วยมือ เรียกเช็ค real-time
               ตอนเลือกครบทั้งคู่ในฟอร์ม (ดู app/routes/clo_plo_mapping.py)
            2. app/routes/course_import.py - หลัง Gemini แกะข้อมูลจาก มคอ.3 เสร็จ (Phase 1) เทียบ
               domain ของแต่ละ CLO ที่แกะได้ กับ category จริงของ PLO ที่ clo_plo_mapping ผูกไว้ (ดึงจาก
               DB จริง ไม่ใช่ให้ Gemini เดา) แล้วเติมเป็น flag type "domain_category_mismatch" เพิ่มเข้าไป
               ใน response - Workstream 2 (มคอ.2 import) ก็จะเรียกฟังก์ชันนี้ซ้ำแบบเดียวกันตอนสร้าง

ถ้าแก้ : DOMAIN_TO_CATEGORY_TH ต้องตรงกับ PLO_CATEGORY_OPTIONS ใน plo-frontend/src/pages/admin/
         AdminPLO.jsx เป๊ะ (ค่าที่เก็บจริงเป็นคำไทยล้วน) และ CLODomain literal ใน app/schemas/clo.py -
         เปลี่ยนฝั่งใดฝั่งหนึ่งแล้วไม่แก้อีกฝั่ง การเทียบจะพังเงียบๆ (เทียบไม่ตรงทั้งที่ควรตรง)
"""
from __future__ import annotations

# ต้องตรงกับ PLO_CATEGORY_OPTIONS ใน plo-frontend/src/pages/admin/AdminPLO.jsx เป๊ะ (ค่าที่เก็บจริงเป็น
# คำไทยล้วน ไม่ใช่รหัสภาษาอังกฤษ) - ใช้เทียบว่า plo.category ตรงกับ clo.domain ไหม
DOMAIN_TO_CATEGORY_TH = {
    "knowledge": "ความรู้",
    "skills": "ทักษะ",
    "ethics": "จริยธรรม",
    "character": "ลักษณะบุคคล",
}

DOMAIN_LABEL_TH = {
    "knowledge": "ความรู้ (Knowledge)",
    "skills": "ทักษะ (Skills)",
    "ethics": "จริยธรรม (Ethics)",
    "character": "ลักษณะบุคคล (Character)",
}


def check_domain_category_mismatch(clo_domain: str | None, plo_category: str | None) -> str | None:
    """คืนข้อความเตือน (ภาษาไทย พร้อมใช้แสดงตรงๆ) ถ้า clo_domain กับ plo_category ไม่ตรงกัน คืน None
    ถ้าตรงกัน หรือถ้าไม่มีข้อมูลพอจะเทียบ (clo_domain เป็น None = ยังไม่ได้ระบุโดเมนของ CLO นี้ - ไม่ถือ
    เป็นความขัดแย้ง แค่ไม่มีอะไรให้เทียบ ไม่เตือน)"""
    if not clo_domain:
        return None
    expected_category = DOMAIN_TO_CATEGORY_TH.get(clo_domain)
    if expected_category is None or plo_category == expected_category:
        return None
    return (
        f'CLO นี้มีโดเมน "{DOMAIN_LABEL_TH.get(clo_domain, clo_domain)}" แต่ PLO ที่ผูกมีประเภท '
        f'"{plo_category}" ซึ่งไม่ตรงกัน - ไม่ได้บล็อกการบันทึก แค่แจ้งเตือนให้ตรวจสอบว่าตั้งใจผูกแบบนี้จริงหรือไม่'
    )
