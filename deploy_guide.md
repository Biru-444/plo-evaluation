# Deploy Guide

Backend รันบน [Render](https://render.com) เป็น Web Service (FastAPI + Uvicorn) ต่อกับ Render
Postgres instance ชื่อ `plo-db` (Free plan, Singapore, PostgreSQL 18, quota 1 GB)

## Environment variables ที่ต้องตั้งค่าบน Render

ดู `.env.example` สำหรับรายการเต็ม — ที่สำคัญที่สุด:

- `DATABASE_URL` — External Database URL ของ `plo-db` (ต้องมี `?sslmode=require` ต่อท้ายถ้าต่อจาก
  นอกเครือข่ายภายในของ Render เช่นตอน dev local ต่อเข้ามา)
- `SECRET_KEY` — เปลี่ยนจาก default เสมอ, generate ด้วย
  `python -c "import secrets; print(secrets.token_hex(32))"`
- `ALLOWED_ORIGINS` — URL จริงของ frontend ที่ deploy แล้ว (คั่นด้วย comma ถ้ามีหลายตัว)

## ⚠️ รหัสผ่าน default ต้องเปลี่ยนก่อนเปิดให้คนอื่นใช้งานจริง

`create_admin.py` สร้าง user `admin` ด้วยรหัสผ่าน `admin123` (สำหรับทดสอบเท่านั้น) —
**ต้องเปลี่ยนรหัสผ่านนี้ก่อนเปิดระบบให้คนอื่นใช้งานจริง** (ยืนยันแล้วว่า ณ 2026-09-18 ยังไม่ได้เปลี่ยน
จาก default บน `plo-db` จริง)

## Database `plo_db_test` (เพิ่ม 2026-09-19)

นอกจาก `plo_db` (ข้อมูลจริง) ยังมีฐานข้อมูลที่สอง **`plo_db_test`** อยู่บน Render instance เดียวกัน —
สร้างขึ้นระหว่างงานคืนระบบ `clo_plo_mapping` (ดู PR #10) เพราะ `conftest.py` ต้องการฐานข้อมูลแยกต่างหาก
เพื่อรัน pytest โดยไม่แตะข้อมูลจริง (derive ชื่อจาก `DATABASE_URL` ต่อท้ายด้วย `_test` — ดูคอมเมนต์หัวไฟล์
`conftest.py`) ตอนสร้างพบว่าฐานนี้ไม่เคยมีอยู่มาก่อนเลยบน instance นี้ (ทั้งที่ repo มี test suite อยู่แล้ว)
เลยสร้างเพิ่มให้ ณ ตอนนั้น

- **ไม่ต้องสร้างเองซ้ำ** — มีอยู่แล้วถาวรบน instance เดียวกับ `plo-db` ตัว user ที่ `DATABASE_URL` ใช้อยู่
  มีสิทธิ์ `CREATEDB` อยู่แล้ว เผื่อวันไหนถูกลบไปโดยไม่ตั้งใจก็สร้างใหม่เองได้ทันทีไม่ต้องขอสิทธิ์เพิ่ม
- `conftest.py`'s `_create_test_schema` fixture สร้างตารางทั้งหมดในนี้ตอนเริ่ม test session และ
  DROP ทิ้งตอนจบ session ทุกครั้ง แต่ละเทสเองก็ใช้ SAVEPOINT-based transaction ที่ rollback อัตโนมัติ
  หลังจบเทส — ฐานนี้จึงไม่มีข้อมูลสะสมค้างจริง มีแค่ schema overhead
- **ขนาด (เช็ค 2026-09-19)**: `plo_db_test` ~8.2 MB เทียบกับ `plo_db` ~11 MB และ quota รวม 1 GB ของ
  instance (รวมทุกฐานบน instance นี้ใช้ไปแค่ ~41 MB หรือ ~4% ของ quota) — เล็กพอที่จะเก็บไว้ถาวรได้โดย
  ไม่ต้องกังวลเรื่อง quota

## ⚠️ Deploy checklist — รัน migration ค้างก่อน/พร้อมกับทุก deploy ที่เพิ่ม script ใหม่

พบบั๊กจริง (2026-09-23) ที่ production พังเพราะ `scripts/migrate_add_clo_plo_mapping_weight.py` ถูก merge
เข้า model แล้ว แต่ไม่เคยถูกรันบน `plo-db` จริง — `clo_plo_mapping.weight_percent` เลยไม่มีอยู่จริงบน
production ทำให้ endpoint ที่ SELECT คอลัมน์นี้ 500 ทุกครั้ง (`/plo/achievement/cohort`,
`/plo/achievement/by-year` และอื่นๆ) กว่าจะรู้ก็ตอนมีคนใช้งานจริงเจอ error

**ทุกครั้งที่ deploy ที่มี `scripts/migrate_*.py` ใหม่ (หรือ merge PR ที่มี):**

1. รัน migration script ใหม่นั้นบน production ก่อนหรือพร้อมกับ deploy โค้ดที่พึ่งพา schema ใหม่นั้น —
   `DATABASE_URL="<production URL>" ./venv/Scripts/python.exe scripts/migrate_xxx.py`
2. เช็คว่า schema ตรงกับโมเดลจริงหลังรัน —
   `DATABASE_URL="<production URL>" ./venv/Scripts/python.exe scripts/check_schema.py`
   (exit code ไม่เป็นศูนย์ = ยังมี gap ค้างอยู่ ห้าม deploy โค้ดที่พึ่งพา schema นั้นจนกว่าจะแก้)
3. ตัว `check_schema()` เดียวกันนี้ยังถูกเรียกอัตโนมัติตอนแอป startup ด้วย (ดู `app/main.py`) — ถ้ามี gap
   จะ log เป็น ERROR ใน Render logs ทันที (ไม่ crash แอป) เป็นตาข่ายรองรับชั้นสุดท้ายเผื่อลืมทำขั้นตอน 1-2
   ข้างบน แต่ **อย่าพึ่งพาตาข่ายนี้อย่างเดียว** — ควรรัน migration ก่อน deploy เสมอ เพราะระหว่างที่ยังไม่ได้
   รัน endpoint ที่พึ่งพา schema นั้นจะ 500 ไปเรื่อยๆ จนกว่าจะรันจริง
