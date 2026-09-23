"""
ทำอะไร : normalize รหัส PLO/CLO ("PLO 4", "plo4", "PLO๔" ฯลฯ) ให้เป็นรูปแบบเดียวกันเสมอ ("PLO4") - ตัวพิมพ์
         ใหญ่ทั้งหมด ไม่มีช่องว่างเลย เลขไทยแปลงเป็นเลขอารบิกก่อนเทียบ

เชื่อมกับ : เรียกใช้ทั้งตอนเขียน (write path - ค่าที่เก็บจริงใน DB ต้องเป็น canonical form เสมอ) และตอน
            เทียบ (comparison path - แม้ค่าใน DB จะเป็น canonical แล้ว แต่ input จากภายนอกอาจยังไม่ใช่)
            รายชื่อจุดที่เรียกจริง ณ ตอนเขียน (2026-09-23, บั๊ก: มคอ.2 บันทึก "PLO 1"..."PLO 9" มีช่องว่าง
            แต่ มคอ.3 extraction คืน "PLO4"..."PLO9" ไม่มีช่องว่าง - เทียบ exact string แล้วไม่ match) :
              - เขียน : app/routes/plo.py (create_plo/update_plo ผ่าน PLOCreateSchema/PLOUpdateSchema
                field_validator), app/routes/clo.py (create_clo/update_clo ผ่าน CLOCreateSchema/
                CLOUpdateSchema field_validator เดียวกัน), app/routes/curriculum_import.py (มคอ.2 save -
                ผ่าน MCO2PLOItem field_validator), app/routes/course_import.py (มคอ.3 save - ผ่าน
                MCO3CLOItem field_validator + normalize มือใน save_course_from_mco3 ตอน resolve
                clo_code/plo_code ของ clo_plo_mapping)
              - เทียบ : app/routes/course_import.py (_add_domain_category_mismatch_flags, เช็ค
                unknown_clo_refs/unknown_plo_refs ตอน save), scripts/normalize_plo_clo_codes.py
                (migration - เทียบ code เดิมกับ normalize(code เดิม) เพื่อหาว่าแถวไหนต้องแก้)
                ฝั่ง frontend มี normalizeCode() คู่กันใน
                plo-frontend/src/utils/codeNormalize.js (พอร์ตกฎเดียวกันนี้เป็น JS ล้วนๆ - ไม่มีทาง
                import ข้าม backend/frontend ได้ ต้องคง 2 ไฟล์ให้ตรงกันด้วยมือ ถ้าแก้กฎตรงนี้ต้องแก้
                ไฟล์นั้นตามด้วยเสมอ)

ถ้าแก้ : เปลี่ยนกฎ normalize ตรงนี้กระทบการจับคู่รหัส PLO/CLO ทั้งระบบทันที (การบันทึกใหม่ + การจับคู่ตอน
         นำเข้า มคอ.3) - ต้องรัน scripts/normalize_plo_clo_codes.py ใหม่ (dry-run ก่อนเสมอ) ถ้าเปลี่ยนกฎ
         หลังจากมีข้อมูลจริงในระบบแล้ว ไม่งั้นข้อมูลเก่ากับใหม่จะไม่ตรงกฎเดียวกัน
"""
from __future__ import annotations

_THAI_DIGIT_TO_ARABIC = str.maketrans("๐๑๒๓๔๕๖๗๘๙", "0123456789")


def normalize_code(code: str | None) -> str:
    """canonical form ของรหัส PLO/CLO - ตัวพิมพ์ใหญ่ทั้งหมด ไม่มีช่องว่างเลย (ลบทุกช่องว่าง ไม่ใช่แค่ตัด
    หัวท้าย) เลขไทยแปลงเป็นเลขอารบิกก่อน - "PLO 4"/"plo4"/"PLO ๔"/"  Plo4  " ทั้งหมดคืน "PLO4" คืนค่าว่าง
    เปล่า ("") ถ้า code เป็น None หรือมีแต่ช่องว่างล้วน"""
    if not code:
        return ""
    translated = code.translate(_THAI_DIGIT_TO_ARABIC)
    return "".join(translated.split()).upper()
