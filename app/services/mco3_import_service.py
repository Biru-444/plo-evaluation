"""
ทำอะไร : เรียก Gemini (google-genai SDK) ให้แกะข้อมูลวิชาจากไฟล์ มคอ.3 (PDF) ออกมาเป็น JSON ที่มี
         โครงสร้างตายตัว (CourseImportFromMCO3Response) — Phase 1 ของฟีเจอร์ "นำเข้าข้อมูลวิชาจาก
         มคอ.3 ด้วย AI" แกะข้อมูลอย่างเดียว ไม่เขียนอะไรลง DB (ดู app/routes/course_import.py)

เชื่อมกับ : ใช้ google-genai==1.2.0 (ปักหมุดไว้ต่ำกว่าเวอร์ชันล่าสุดโดยตั้งใจ — ดูคอมเมนต์ท้ายไฟล์นี้
            เรื่อง thinking_level) เรียก client.models.generate_content ส่งไฟล์ PDF เป็น inline
            bytes (Part.from_bytes) พร้อม response_schema=CourseImportFromMCO3Response บังคับให้
            Gemini ตอบเป็น JSON ตรงตาม schema เป๊ะ ไม่ต้อง parse free text เอง

ถ้าแก้ : กฎการ flag ทั้ง 6 แบบ (category_mismatch/checkbox_ambiguous/duplicate_course_code/
         curriculum_mismatch/title_content_mismatch/plo_mapping_not_filled) อยู่ใน
         SYSTEM_INSTRUCTION ด้านล่างล้วนๆ ห้ามให้โมเดลเดาเอง — ถ้าจะ
         เปลี่ยนตัวเลือกหมวดหมู่วิชา (ตอนนี้คือ "วิชาแกน"/"วิชาบังคับ"/อื่นๆ) ต้องแก้ให้ตรงกับ
         FIXED_CATEGORY_OPTIONS ใน plo-frontend/src/pages/CurriculumCourses.jsx ด้วย ไม่งั้น flag
         category_mismatch จะขึ้นผิดพลาดทั้งที่ค่าจริงตรงกัน

หมายเหตุเรื่อง thinking_level : สเปกเดิมขอให้ตั้ง thinking_level="minimal" แต่ SDK เวอร์ชันที่รองรับ
    field นี้ (google-genai >= ~1.3x ขึ้นไป) ต้องการ anyio>=4.8/httpx>=0.28.1/pydantic>=2.12.5 ซึ่ง
    ชนกับ fastapi==0.104.1 ที่ปักหมุดไว้ทั้งระบบ (fastapi 0.104.1 ดึง starlette 0.27.0 ที่บังคับ
    anyio<4.0 - ทดสอบแล้วว่าถ้าฝืนอัปเกรด anyio/pydantic ตรงๆ แอปทั้งระบบพังทันทีตอน import เพราะ
    FastAPI 0.104.1 เข้ากันไม่ได้กับ pydantic รุ่นใหม่) ผู้ใช้ยืนยันแล้วให้ใช้ google-genai==1.2.0
    (เวอร์ชันใหม่สุดที่ยังเข้ากับ pin เดิมได้) ไปก่อน ซึ่งไม่มี thinking_level/thinking_budget เลย -
    จึงไม่ได้ตั้งค่านี้ ปล่อยให้โมเดลใช้ reasoning effort ปกติของมันเอง (งานนี้เป็น extraction ล้วน
    ผลต่างจาก "minimal" ที่ขอไว้น่าจะแค่ latency ช้ากว่าเล็กน้อย ไม่กระทบความถูกต้อง) ถ้าอัปเกรด
    fastapi ทั้งระบบในอนาคต ค่อยเปลี่ยน google-genai รุ่นแล้วเพิ่ม thinking_config ตรงนี้ได้
"""
from __future__ import annotations

import io
import os

from docx import Document
from docx.oxml.ns import qn
from docx.table import Table
from docx.text.paragraph import Paragraph
from google import genai
from google.genai import types

from app.schemas.course_import import CourseImportFromMCO3Response

SYSTEM_INSTRUCTION = """\
คุณคือผู้ช่วยแกะข้อมูลวิชาจากเอกสาร มคอ.3 (รายละเอียดของรายวิชา) ของมหาวิทยาลัยไทย ให้เป็น JSON
ตาม schema ที่กำหนด อ่านเอกสารที่แนบมา (อาจเป็นไฟล์ PDF จริง หรือข้อความที่แกะจากไฟล์ .docx มาแล้ว)
อย่างละเอียด แล้วกรอกข้อมูลตามนี้:

- course_code, name_th, name_en, credit: ข้อมูลพื้นฐานของวิชา (มักอยู่หมวดที่ 1) name_en ถ้าไม่มี
  ในเอกสารให้ใส่ null credit ให้ใส่เป็นจำนวนเต็มหน่วยกิตรวม (เช่นเอกสารเขียน "3(2-2-5)" ให้ใส่ 3)

- category_raw: ข้อความ "ประเภทวิชา"/"หมวดวิชา" ที่เจอในเอกสารตรงๆ คัดลอกมาเป๊ะๆ ไม่ต้องตีความ

- category_mapped: ระบบมีตัวเลือกหมวดหมู่วิชาอยู่แค่ 2 แบบคือ "วิชาแกน" กับ "วิชาบังคับ" (ค่าอื่น
  ทั้งหมดถือว่าไม่ตรง) ถ้า category_raw ตรงกับ 2 คำนี้ (หรือสื่อความหมายเดียวกันชัดเจน) ให้ใส่คำนั้น
  เป๊ะๆ ลงใน category_mapped ถ้าไม่ตรง (เช่น "วิชาเลือก", "General Education", "Major Elective" หรือ
  อะไรก็ตามที่ไม่ใช่ 2 คำนี้) ให้ใส่ category_mapped = null และเพิ่ม flag type "category_mismatch"
  พร้อมข้อความอธิบายว่าเอกสารเขียนว่าอะไร เทียบกับ 2 ตัวเลือกที่ระบบรองรับ

- clos: รายการ CLO (ผลลัพธ์การเรียนรู้ระดับวิชา) ทั้งหมดที่เจอในเอกสาร แต่ละข้อมี code (เช่น "CLO1"),
  description (คำอธิบายเต็ม), และ domain (โดเมนการเรียนรู้ของ CLO ข้อนั้น) - domain มีค่าได้แค่
  "knowledge"/"skills"/"ethics"/"character" เท่านั้น เอกสาร มคอ.3 มักกำกับโดเมนของแต่ละ CLO ด้วย
  ตัวย่อในวงเล็บท้ายข้อความ เช่น "(K)" = knowledge, "(S)" = skills, "(A)" = ethics (affective),
  "(C)" = character หรือบางเอกสารเขียนเป็นคำเต็มภาษาไทย "ความรู้"/"ทักษะ"/"จริยธรรม"/"ลักษณะบุคคล"
  แทน - ถ้าตัวย่อ/คำที่เจอแม็ปเข้า 4 ค่านี้ได้ตรงๆ ชัดเจนให้ใส่ค่านั้น ถ้าไม่มีตัวย่อ/คำกำกับเลย หรือ
  มีแต่กำกวมแม็ปเข้าค่าเดียวไม่ได้ชัดเจน (เช่น เขียนวงเล็บผสมแบบ "(E/C)" ที่ไม่ตรงกับ 4 ตัวย่อมาตรฐาน)
  ให้ใส่ domain = null ห้ามเดาว่าน่าจะเป็นค่าไหน

- clo_plo_mapping: คู่ (clo_code, plo_code) ที่เอกสารระบุชัดเจนว่า CLO ข้อไหนสัมพันธ์กับ PLO ข้อไหน
  ใส่เฉพาะคู่ที่มั่นใจจริงๆ เท่านั้น ห้ามเดา - ตารางความสัมพันธ์ PLO×CLO ในเอกสาร มคอ.3 มี 2 แบบ:
    (ก) ตารางที่ระบุ PLO เป็นข้อความ/รหัสตรงๆ ในแถวของแต่ละ CLO — แบบนี้อ่านแล้วใส่คู่ที่เจอได้เลย
    (ข) ตารางแบบกาเครื่องหมาย (checkbox หรือช่องว่างให้ทำเครื่องหมาย ✓) ที่มีแถวเป็น CLO
        คอลัมน์เป็น PLO — แบบนี้ต้องดูให้ออกจริงๆ ว่าช่องไหนถูกกา/ทำเครื่องหมายไว้ ถ้าคุณดึงข้อความ
        จาก PDF แล้วไม่เห็นเครื่องหมายที่ชัดเจนพอจะบอกได้ว่าช่องไหนถูกกา (เช่น ข้อความไม่มีสัญลักษณ์
        ✓/x/• หลงเหลือให้เห็นเลย เห็นแต่โครงตาราง) **ห้ามใส่คู่ clo_plo_mapping ใดๆ ของ CLO นั้นเด็ดขาด
        แม้แต่คู่เดียวที่ "ดูน่าจะใช่" ก็ห้าม** — การเดาแบบเจาะจง 1 ช่อง (เช่นเลือก PLO ที่คำอธิบาย CLO
        ดูใกล้เคียงที่สุด) อันตรายพอๆ กับการเดาว่าใช่ทุกช่อง เพราะแอดมินอาจเข้าใจผิดว่าเป็นข้อมูลที่
        อ่านได้จริงจากตาราง ทั้งที่จริงๆ คือการเดาของคุณเอง ให้เว้น clo_plo_mapping ของ CLO นั้นว่างไว้
        (ไม่ใส่คู่ใดๆ ของ CLO นั้นเลย ไม่ว่ากรณีใด) และเพิ่ม flag type "checkbox_ambiguous" บอกว่า
        ตาราง PLO×CLO ของวิชานี้เป็นแบบกาเครื่องหมายที่อ่านไม่ออกจากข้อความที่แกะได้ ต้องให้แอดมินเปิด
        ไฟล์ต้นฉบับเทียบเองว่าช่องไหนถูกกาจริง - ถ้าตารางนั้นมีคอลัมน์สรุปยอด เช่น "รวม" หรือ "จำนวน
        CLO ที่สนับสนุน PLO" (ตัวเลขนับจำนวนช่องที่ถูกกาในแถว/คอลัมน์นั้น) ให้แนบตัวเลขที่เจอลงใน
        message ด้วย เช่น "ตาราง PLO4 มีคอลัมน์ 'รวม' = 1 แต่ไม่สามารถระบุได้ว่า CLO ข้อไหนคือข้อที่
        ถูกกา ต้องเปิดไฟล์ต้นฉบับเทียบ" - ตัวเลขนี้ช่วยยืนยันว่ามีการกาจริง (สนับสนุนว่าควร flag
        checkbox_ambiguous ไม่ใช่ plo_mapping_not_filled) แต่ยังคงห้ามเดาตำแหน่งว่าเป็นช่องไหนอยู่ดี
        แม้จะรู้จำนวนรวมก็ตาม (clo_plo_mapping ของ CLO นั้นต้องว่างเหมือนเดิม)

- instructor_name: ชื่ออาจารย์ผู้สอน/ผู้รับผิดชอบรายวิชา ถ้าเอกสารระบุไว้ (มักอยู่หมวดที่ 1 หัวข้อ
  "อาจารย์ผู้รับผิดชอบรายวิชา/ผู้สอน") มีหลายคนให้รวมเป็นข้อความเดียวคั่นด้วยจุลภาค ไม่มีให้ใส่ null -
  ฟิลด์นี้ใช้แสดงอ้างอิงในหน้าตรวจสอบเท่านั้น ไม่ต้องกังวลเรื่องความแม่นยำระดับสูงสุด

- semester_display: ข้อความดิบเกี่ยวกับภาคการศึกษา/ชั้นปีที่เรียนที่เจอในเอกสาร (มักอยู่หมวดที่ 1
  หัวข้อ "ภาคการศึกษา/ชั้นปีที่เรียน") คัดลอกข้อความมาเกือบตรงๆ ได้เลย เช่น "1/2568 ชั้นปีที่ 1"
  ไม่ต้องพยายามแยกเป็นตัวเลขปี/เทอมแยกกัน ไม่มีให้ใส่ null - ฟิลด์นี้ใช้แสดงอ้างอิงเช่นกัน

- flags: รายการปัญหา/ข้อสังเกตที่แอดมินต้องตรวจสอบเอง ก่อนบันทึกข้อมูลจริง (Phase นี้ยังไม่บันทึก
  อะไรลงระบบ) แต่ละ flag มี type และ message (ภาษาไทย อธิบายให้แอดมินอ่านแล้วตัดสินใจเองได้ทันที
  ไม่ต้องเปิดเอกสารเทียบก่อนถึงจะเข้าใจว่าปัญหาคืออะไร) นอกจาก category_mismatch และ
  checkbox_ambiguous ด้านบน ยังมีอีก 4 กรณีที่ต้อง flag:
    - "duplicate_course_code": ถ้ารหัสวิชาที่ปรากฏในเอกสารขัดแย้งกันเอง เช่นรหัสวิชาในหมวดที่ 1
      (ข้อมูลทั่วไป) ไม่ตรงกับรหัสที่ระบุในหมวดที่ 2 (คำอธิบายรายวิชา/ความสัมพันธ์กับ PLO) หรือหมวดอื่น
      ของเอกสารเดียวกัน - ต้องเป็นคนละเลขกันไปเลยจริงๆ (เช่นหลักสิบ/หลักร้อยต่างกัน) ไม่ใช่แค่พิมพ์ผิด
      หลักเดียวที่อาจเป็น typo เฉยๆ **ตรวจจากตัวเอกสารที่แนบมาจริงเท่านั้น ห้ามอ้างอิงรหัสวิชาตัวอย่างใดๆ
      ที่เคยเห็นมาก่อน** ถ้าเจอให้ระบุในข้อความว่าเจอค่าไหนบ้างที่ตำแหน่งไหน (คัดลอกรหัสและตำแหน่งจาก
      เอกสารจริงเป๊ะๆ)
    - "curriculum_mismatch": ผู้ใช้จะบอกชื่อหลักสูตรเป้าหมาย (ที่แอดมินเลือกไว้ตอนอัปโหลด) มาในข้อความ
      ถัดจากนี้ ให้เทียบกับชื่อหลักสูตรที่ระบุในเอกสาร มคอ.3 เอง (มักอยู่หัวกระดาษหรือหมวดที่ 1 เช่น
      "หลักสูตร...สาขาวิชา...") ถ้าชื่อไม่ตรงกัน (คนละหลักสูตรกันจริงๆ ไม่ใช่แค่สะกดต่างเล็กน้อย) ให้ใส่
      flag นี้เป็นอันแรกสุดในลิสต์ เตือนแรงๆ ว่าเอกสารนี้อาจเป็นของหลักสูตรอื่น ไม่ใช่หลักสูตรที่เลือกไว้
    - "title_content_mismatch": หัวเรื่องบนสุดของเอกสาร (บรรทัดแบบ "รายละเอียดของรายวิชา...") ระบุ
      รหัส/ชื่อวิชาไว้ชัดเจน (ไม่ใช่แค่ชื่อเทมเพลตทั่วไปอย่าง "รายละเอียดของรายวิชาตามเกณฑ์คุณภาพ
      หลักสูตร...") **และ** รหัส/ชื่อวิชานั้นไม่ตรงกับรหัส/ชื่อวิชาที่ปรากฏจริงในเนื้อหาหมวดที่ 1/2 ของ
      เอกสารเดียวกัน (คนละวิชากันจริงๆ ไม่ใช่แค่สะกดต่างเล็กน้อย) - นี่คือคนละกรณีกับ duplicate_course_code
      (ซึ่งขัดแย้งกันเองภายในเนื้อหาหมวดต่างๆ) เพราะ title_content_mismatch คือหัวเรื่อง/ปก vs เนื้อหา
      ข้างใน **สำคัญมาก: ตรวจจากข้อความในเอกสารที่แนบมาจริงเท่านั้น ถ้าหัวเรื่องเป็นแค่ชื่อเทมเพลต/ประเภท
      เอกสารทั่วไปที่ไม่มีชื่อวิชาระบุอยู่เลย (ไม่ได้เจาะจงวิชาใดวิชาหนึ่ง) ห้าม flag นี้เด็ดขาด แม้จะนึกถึง
      ตัวอย่างสถานการณ์แบบนี้ได้ก็ตาม - ห้ามยกตัวอย่างชื่อวิชา/รหัสวิชาที่ไม่ได้มาจากเอกสารจริงที่แนบมา
      มาเป็นคำตอบเด็ดขาด**
    - "plo_mapping_not_filled": ตาราง PLO-CLO มีโครงตาราง (หัวคอลัมน์/แถวครบ) อยู่ในเอกสารจริง แต่ไม่มี
      เครื่องหมายหรือข้อมูลกรอกอยู่เลยแม้แต่ช่องเดียวทั้งตาราง (ตารางว่างเปล่าตั้งแต่ต้น อาจารย์ยังไม่ได้
      กรอกอะไรเลย) - **ต่างจาก checkbox_ambiguous ตรงที่ checkbox_ambiguous คือตารางมีข้อมูล/เครื่อง
      หมายกรอกไว้จริง แต่ดึงออกมาเป็นข้อความไม่ได้ (เอกสารกรอกแล้วแต่อ่านไม่ออก) ส่วน
      plo_mapping_not_filled คือไม่มีอะไรให้อ่านตั้งแต่ต้น** ทั้งสองแบบทำให้ clo_plo_mapping ว่างเหมือน
      กัน แต่ต้องเลือก flag type ให้ตรงกับสาเหตุจริง เพราะวิธีแก้ต่างกัน (checkbox_ambiguous ให้แอดมิน
      ไปเปิดไฟล์ต้นฉบับเทียบ, plo_mapping_not_filled ต้องไปถามอาจารย์ผู้สอนให้กรอกข้อมูลเพิ่มก่อน)
    - "other": ปัญหาอื่นที่ไม่เข้า 6 ประเภทข้างต้น แต่คิดว่าแอดมินควรรู้ก่อนบันทึกข้อมูล

หมายเหตุ : ไม่ต้องสนใจ/ไม่ต้องแกะข้อมูลแผนการสอนรายสัปดาห์ในเอกสาร ไม่อยู่ในขอบเขตงานนี้

ตอบเป็น JSON ตาม schema เท่านั้น ห้ามมีข้อความอื่นนอก JSON"""


def _build_client() -> genai.Client:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY environment variable is not set")
    return genai.Client(api_key=api_key)


def _run_extraction(document_content, curriculum_name: str) -> CourseImportFromMCO3Response:
    """ส่วนที่ใช้ร่วมกันระหว่าง path .pdf (ส่ง Part.from_bytes) กับ .docx (ส่ง text ที่แกะไว้แล้วเป็น
    string ธรรมดา) - document_content คือ types.Part หรือ str ก็ได้ (google-genai SDK รับ str ใน
    contents list แล้วห่อเป็น text part ให้อัตโนมัติ)"""
    client = _build_client()

    response = client.models.generate_content(
        model="gemini-3.5-flash-lite",
        contents=[
            document_content,
            f"หลักสูตรเป้าหมายที่แอดมินเลือกไว้ตอนอัปโหลดไฟล์นี้คือ: \"{curriculum_name}\"",
        ],
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_INSTRUCTION,
            response_mime_type="application/json",
            response_schema=CourseImportFromMCO3Response,
        ),
    )

    if response.parsed is None:
        raise RuntimeError(f"Gemini ไม่คืนผลลัพธ์ตาม schema ที่กำหนด: {response.text!r}")

    return response.parsed


def import_course_from_mco3_pdf(pdf_bytes: bytes, curriculum_name: str) -> CourseImportFromMCO3Response:
    """แกะข้อมูลวิชาจากไฟล์ มคอ.3 (PDF, เป็น bytes) ด้วย Gemini คืนค่าเป็น
    CourseImportFromMCO3Response ที่ validate แล้ว - ไม่แตะ DB เลย (Phase 1)"""
    part = types.Part.from_bytes(data=pdf_bytes, mime_type="application/pdf")
    return _run_extraction(part, curriculum_name)


def _iter_block_items(document: Document):
    """เดินเอกสาร .docx ตามลำดับจริงในไฟล์ (ย่อหน้า/ตาราง สลับกันได้) - python-docx เวอร์ชันพื้นฐาน
    แยก document.paragraphs กับ document.tables ให้แยกกันเฉยๆ ไม่เรียงตามลำดับจริง เทคนิคนี้เดิน
    XML element ของ document.element.body ตรงๆ แทน เป็นแพทเทิร์นมาตรฐานของ python-docx สำหรับกรณีนี้"""
    for child in document.element.body.iterchildren():
        if child.tag == qn("w:p"):
            yield Paragraph(child, document)
        elif child.tag == qn("w:tbl"):
            yield Table(child, document)


def _extract_docx_text(docx_bytes: bytes) -> str:
    """แปลง .docx เป็น plain text เรียงตามลำดับเอกสารจริง ไม่รักษา formatting (ไม่จำเป็นสำหรับงานนี้)
    ตารางแปลงเป็นแถวละ 1 บรรทัด คั่นแต่ละคอลัมน์ด้วย " | " - เซลล์ว่างจะเห็นเป็นช่องว่างระหว่าง | สองตัว
    ตรงๆ (ไม่ตัดทิ้ง) เพื่อให้ Gemini แยกออกว่าตารางไหน "มีโครงแต่ไม่มีใครกรอก" ได้ (ดู flag
    plo_mapping_not_filled ใน SYSTEM_INSTRUCTION)"""
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


def import_course_from_mco3_docx(docx_bytes: bytes, curriculum_name: str) -> CourseImportFromMCO3Response:
    """แกะข้อมูลวิชาจากไฟล์ มคอ.3 (.docx, เป็น bytes) ด้วย Gemini - ต่างจาก .pdf ตรงที่แปลงเป็น
    plain text ด้วย python-docx ก่อนแล้วค่อยส่งเป็น text (ไม่ใช่ inline file) เพราะ Gemini ไม่รับ
    .docx เป็น inline data โดยตรง"""
    text = _extract_docx_text(docx_bytes)
    wrapped = (
        "ข้อความต่อไปนี้คือเนื้อหาที่แกะออกมาจากไฟล์ .docx (Word) ของเอกสาร มคอ.3 แล้วด้วยโปรแกรม "
        "ไม่ใช่ภาพต้นฉบับ - ตารางในเอกสารถูกแปลงเป็นข้อความแถวละ 1 บรรทัด แต่ละคอลัมน์คั่นด้วย \" | \" "
        "เซลล์ที่ไม่มีข้อความอยู่เลยระหว่างเครื่องหมาย | หมายความว่าช่องนั้นว่างเปล่าจริงๆ ในเอกสารต้นฉบับ "
        "(ไม่ใช่ปัญหาจากการแกะข้อความ) - ถ้าตาราง PLO×CLO ทั้งตารางว่างแบบนี้ (มีหัวคอลัมน์/แถวครบแต่ไม่มี "
        "ข้อมูลกรอกเลยสักช่อง) ให้ flag เป็น \"plo_mapping_not_filled\" ไม่ใช่ \"checkbox_ambiguous\" "
        "(checkbox_ambiguous สงวนไว้สำหรับกรณีมีเครื่องหมายอยู่จริงแต่ข้อความที่แกะออกมาไม่มีสัญลักษณ์ "
        "ให้เห็น ซึ่งไม่ใช่กรณีนี้ เพราะข้อความจากไฟล์ .docx ได้ค่าเป๊ะตามที่กรอกไว้จริงเสมอ ไม่มีการ "
        "สูญหายจากการแปลงแบบที่ PDF อาจเจอ)\n\n" + text
    )
    return _run_extraction(wrapped, curriculum_name)
