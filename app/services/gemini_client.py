"""
ทำอะไร : สร้าง google-genai client ตัวเดียว ใช้ร่วมกันระหว่าง mco3_import_service.py (นำเข้าวิชาจาก
         มคอ.3) กับ mco2_import_service.py (นำเข้าหลักสูตร/PLO จาก มคอ.2) - แยกออกมาเพราะเป็นฟังก์ชัน
         เดียวกันเป๊ะทั้งสองที่ ไม่มีอะไรต่างกันเลย (อ่าน GEMINI_API_KEY จาก env แล้วสร้าง genai.Client)

ถ้าแก้ : ปักหมุด google-genai==1.2.0 ไว้ (ดูเหตุผลเรื่อง thinking_level/anyio conflict กับ
         fastapi==0.104.1 ในคอมเมนต์ท้าย mco3_import_service.py - เหตุผลเดียวกันใช้กับทุกจุดที่เรียก
         genai.Client ในระบบนี้)
"""
from __future__ import annotations

import os

from google import genai


def build_gemini_client() -> genai.Client:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY environment variable is not set")
    return genai.Client(api_key=api_key)
