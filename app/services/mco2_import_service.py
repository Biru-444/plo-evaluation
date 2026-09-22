"""
ทำอะไร : เรียก Gemini (google-genai SDK) ให้แกะข้อมูลหลักสูตร+PLO จากไฟล์ มคอ.2 (PDF/.docx) ออกมาเป็น
         JSON ที่มีโครงสร้างตายตัว (CurriculumImportFromMCO2Response) — Phase 1 ของฟีเจอร์ "นำเข้า
         หลักสูตร/PLO จาก มคอ.2 ด้วย AI" (Workstream 2) แกะข้อมูลอย่างเดียว ไม่เขียนอะไรลง DB (ดู
         app/routes/curriculum_import.py) เลียนแบบ app/services/mco3_import_service.py ทุกประการ
         (โครงสร้างไฟล์, การแยก .pdf/.docx, การใช้ response_schema บังคับ Gemini) แต่ขอบเขตแคบกว่า
         มาก (ไม่มี CLO/checkbox table ให้แกะ)

เชื่อมกับ : ใช้ google-genai==1.2.0 ผ่าน app/services/gemini_client.py (client builder เดียวกับที่
            มคอ.3 ใช้ - ดูเหตุผลเรื่อง thinking_level/anyio conflict ที่นั่น) ส่งไฟล์ PDF เป็น inline
            bytes (Part.from_bytes) พร้อม response_schema=CurriculumImportFromMCO2Response

ถ้าแก้ : กฎการ flag 3 แบบที่ Gemini ตัดสินเอง (duplicate_plo_code/category_unclear/other) อยู่ใน
         SYSTEM_INSTRUCTION ด้านล่างล้วนๆ ห้ามให้โมเดลเดาเอง - ถ้าจะเปลี่ยนตัวเลือกหมวดหมู่ PLO (ตอนนี้
         คือ "ความรู้"/"ทักษะ"/"จริยธรรม"/"ลักษณะบุคคล") ต้องแก้ MCO2PLOCategory ใน
         app/schemas/curriculum_import.py และ PLO_CATEGORY_OPTIONS ใน
         plo-frontend/src/pages/admin/AdminPLO.jsx ให้ตรงกันทั้งคู่ด้วย ไม่งั้น flag category_unclear
         จะขึ้นผิดพลาดทั้งที่ค่าจริงตรง
"""
from __future__ import annotations

import io

from docx import Document
from docx.oxml.ns import qn
from docx.table import Table
from docx.text.paragraph import Paragraph
from google.genai import types

from app.schemas.curriculum_import import CurriculumImportFromMCO2Response
from app.services.gemini_client import build_gemini_client

SYSTEM_INSTRUCTION = """\
คุณคือผู้ช่วยแกะข้อมูลหลักสูตรจากเอกสาร มคอ.2 (รายละเอียดของหลักสูตร) ของมหาวิทยาลัยไทย ให้เป็น JSON
ตาม schema ที่กำหนด อ่านเอกสารที่แนบมา (อาจเป็นไฟล์ PDF จริง หรือข้อความที่แกะจากไฟล์ .docx มาแล้ว)
อย่างละเอียด แล้วกรอกข้อมูลตามนี้ - งานนี้แกะเฉพาะชื่อ/ปีหลักสูตร กับรายการ PLO เท่านั้น ไม่ต้องแกะ
ข้อมูลรายวิชา โครงสร้างหลักสูตร แผนการเรียน หรือสิ่งอื่นใดในเอกสารเลย:

- curriculum_name: ชื่อเต็มของหลักสูตร (เช่น "หลักสูตรวิทยาศาสตรบัณฑิต สาขาวิชาวิทยาการคอมพิวเตอร์")
  มักอยู่หน้าปกหรือหมวดที่ 1 ของเอกสาร ถ้าเอกสารระบุว่าเป็น "หลักสูตรปรับปรุง" ให้ใช้ชื่อหลักสูตรตามที่
  ระบุไว้ตรงๆ ไม่ต้องเติมคำว่า "ปรับปรุง" เข้าไปในชื่อเอง เว้นแต่เอกสารเขียนไว้แบบนั้นจริงๆ

- curriculum_year: ปี พ.ศ. ที่หลักสูตรนี้เริ่มใช้ (เช่นเอกสารเขียน "หลักสูตรปรับปรุง พ.ศ. 2565" หรือ
  "ปีการศึกษาที่เริ่มใช้หลักสูตร: 2565" ให้ใส่ 2565) ถ้าเอกสารมีหลายปีที่ดูใกล้เคียงกัน (เช่น ปีที่
  อนุมัติ vs ปีที่เริ่มใช้จริง) ให้ใช้ปีที่เริ่มใช้หลักสูตรเป็นหลัก

- plos: รายการ PLO (Program Learning Outcomes - ผลลัพธ์การเรียนรู้ระดับหลักสูตร) ทั้งหมดที่เจอในเอกสาร
  (มักอยู่หมวดที่ 2 "ข้อมูลเฉพาะของหลักสูตร" หัวข้อ "ผลลัพธ์การเรียนรู้ที่คาดหวังของหลักสูตร" หรือหมวด
  มาตรฐานผลการเรียนรู้) แต่ละข้อมี:
    - code: รหัส PLO ตามที่เอกสารกำหนด (เช่น "PLO1") ถ้าเอกสารไม่ได้ตั้งรหัสไว้ชัดเจน ให้ตั้งรหัสตาม
      ลำดับที่ปรากฏในเอกสารเอง (PLO1, PLO2, ...)
    - description_th: คำอธิบาย PLO ข้อนั้นเป็นภาษาไทยเต็มๆ ตามที่ปรากฏในเอกสาร
    - description_en: คำอธิบายภาษาอังกฤษ ถ้าเอกสารมีคู่กัน ถ้าไม่มีให้ใส่ null
    - category: หมวดหมู่ของ PLO ข้อนี้ มีค่าได้แค่ "ความรู้"/"ทักษะ"/"จริยธรรม"/"ลักษณะบุคคล" เท่านั้น
      เอกสาร มคอ.2 มักจัดกลุ่ม PLO ตามหมวดเหล่านี้อยู่แล้ว (เช่นหัวข้อย่อย "ด้านความรู้", "ด้านทักษะ",
      "ด้านคุณธรรมจริยธรรม", "ด้านลักษณะบุคคล" หรือคำใกล้เคียงที่สื่อความหมายเดียวกันชัดเจน) ถ้า PLO
      ข้อไหนไม่ได้อยู่ใต้หมวดหมู่ที่ระบุชัดเจน หรือหมวดที่เอกสารใช้ไม่ตรงกับ 4 ค่านี้เลย ให้ใส่
      category = null ห้ามเดาว่าน่าจะเป็นหมวดไหน

- flags: รายการปัญหา/ข้อสังเกตที่แอดมินต้องตรวจสอบเอง ก่อนบันทึกข้อมูลจริง (Phase นี้ยังไม่บันทึกอะไร
  ลงระบบ) แต่ละ flag มี type และ message (ภาษาไทย อธิบายให้แอดมินอ่านแล้วตัดสินใจเองได้ทันที):
    - "duplicate_plo_code": รหัส PLO เดียวกัน (เช่น "PLO3") ปรากฏซ้ำในเอกสารแต่คำอธิบายไม่ตรงกัน หรือ
      ขัดแย้งกันเอง (คนละข้อความกันจริงๆ ไม่ใช่แค่คัดลอกซ้ำคำต่อคำ) - บอกรหัสที่ชนกันและคำอธิบายทั้งสอง
      แบบที่เจอในข้อความ
    - "category_unclear": PLO ข้อไหนที่ต้องใส่ category = null ตามกฎด้านบน ให้ flag แบบนี้บอกว่า PLO
      ข้อไหน (ระบุ code) และเอกสารเขียนหมวดหมู่ไว้ว่าอะไร (หรือไม่ได้ระบุเลย)
    - "other": ปัญหาอื่นที่ไม่เข้า 2 ประเภทข้างต้น แต่คิดว่าแอดมินควรรู้ก่อนบันทึกข้อมูล เช่นเอกสารดู
      เหมือนไม่ใช่ มคอ.2 เลย หรือแกะรายการ PLO ไม่ได้เลยทั้งเอกสาร

ตอบเป็น JSON ตาม schema เท่านั้น ห้ามมีข้อความอื่นนอก JSON"""


def _run_extraction(document_content) -> CurriculumImportFromMCO2Response:
    """ส่วนที่ใช้ร่วมกันระหว่าง path .pdf (ส่ง Part.from_bytes) กับ .docx (ส่ง text ที่แกะไว้แล้วเป็น
    string ธรรมดา) - เหมือน _run_extraction ของ mco3_import_service.py ทุกประการ ต่างแค่ไม่มี
    curriculum_name ส่งเสริมเข้าไปเทียบ (มคอ.2 ไม่มีหลักสูตรเป้าหมายที่เลือกไว้ล่วงหน้าให้เทียบ)"""
    client = build_gemini_client()

    response = client.models.generate_content(
        model="gemini-3.5-flash-lite",
        contents=[document_content],
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_INSTRUCTION,
            response_mime_type="application/json",
            response_schema=CurriculumImportFromMCO2Response,
        ),
    )

    if response.parsed is None:
        raise RuntimeError(f"Gemini ไม่คืนผลลัพธ์ตาม schema ที่กำหนด: {response.text!r}")

    return response.parsed


def import_curriculum_from_mco2_pdf(pdf_bytes: bytes) -> CurriculumImportFromMCO2Response:
    """แกะข้อมูลหลักสูตร/PLO จากไฟล์ มคอ.2 (PDF, เป็น bytes) ด้วย Gemini คืนค่าเป็น
    CurriculumImportFromMCO2Response ที่ validate แล้ว - ไม่แตะ DB เลย (Phase 1)"""
    part = types.Part.from_bytes(data=pdf_bytes, mime_type="application/pdf")
    return _run_extraction(part)


def _iter_block_items(document: Document):
    """เดินเอกสาร .docx ตามลำดับจริงในไฟล์ - เหมือน mco3_import_service.py ทุกประการ (ก๊อปมาเพราะเป็น
    helperภายในไฟล์ ไม่ได้ export ให้ใช้ร่วมข้ามไฟล์)"""
    for child in document.element.body.iterchildren():
        if child.tag == qn("w:p"):
            yield Paragraph(child, document)
        elif child.tag == qn("w:tbl"):
            yield Table(child, document)


def _extract_docx_text(docx_bytes: bytes) -> str:
    """แปลง .docx เป็น plain text เรียงตามลำดับเอกสารจริง - เหมือน mco3_import_service.py ทุกประการ"""
    document = Document(io.BytesIO(docx_bytes))
    lines: list[str] = []
    for block in _iter_block_items(document):
        if isinstance(block, Paragraph):
            text = block.text.strip()
            if text:
                lines.append(text)
        else:
            for row in block.rows:
                lines.append(" | ".join(cell.text.strip() for cell in row.cells))
            lines.append("")
    return "\n".join(lines)


def import_curriculum_from_mco2_docx(docx_bytes: bytes) -> CurriculumImportFromMCO2Response:
    """แกะข้อมูลหลักสูตร/PLO จากไฟล์ มคอ.2 (.docx, เป็น bytes) ด้วย Gemini - แปลงเป็น plain text ด้วย
    python-docx ก่อนแล้วค่อยส่งเป็น text (ไม่ใช่ inline file) เพราะ Gemini ไม่รับ .docx เป็น inline
    data โดยตรง (เหมือน มคอ.3)"""
    text = _extract_docx_text(docx_bytes)
    wrapped = (
        "ข้อความต่อไปนี้คือเนื้อหาที่แกะออกมาจากไฟล์ .docx (Word) ของเอกสาร มคอ.2 แล้วด้วยโปรแกรม "
        "ไม่ใช่ภาพต้นฉบับ - ตารางในเอกสารถูกแปลงเป็นข้อความแถวละ 1 บรรทัด แต่ละคอลัมน์คั่นด้วย \" | \"\n\n"
        + text
    )
    return _run_extraction(wrapped)
