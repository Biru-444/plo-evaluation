"""
ทำอะไร : จุดเริ่มต้นของ backend ทั้งระบบ — สร้าง FastAPI app, ตั้งค่า CORS, สร้างตารางฐานข้อมูลถ้ายัง
         ไม่มี และลงทะเบียน router ของทุก endpoint (auth, PLO, YLO, CLO, courses, students ฯลฯ)

เชื่อมกับ : import router จากทุกไฟล์ใน app/routes/ — ลำดับ app.include_router() ด้านล่างมีผลต่อการ
            ทำงานจริง (ดูคอมเมนต์กำกับไว้ตรงจุดนั้น) รันด้วย `uvicorn app.main:app` (หรือรันไฟล์นี้ตรง ๆ
            ตอน dev local)

ถ้าแก้ : ลืมเพิ่ม app.include_router(...) ให้ router ใหม่ = endpoint นั้นเรียกไม่ได้เลย (404) ทั้งที่โค้ด
         ถูกต้อง — ต้องเพิ่มทั้ง import และ include_router คู่กันเสมอ
"""
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.database import Base, engine
from app.routes import (
    assessment,
    auth,
    clo,
    clo_calculation,
    clo_plo_mapping,
    course_import,
    course_offering,
    course_plo,
    courses,
    curriculum,
    curriculum_import,
    enrollment,
    item_clo,
    plo,
    plo_calculation,
    roster_import,
    study_plan,
    students,
    users,
    ylo,
    ylo_calculation,
    ylo_plo_mapping,
)

# สร้างตารางในฐานข้อมูลตาม model ทั้งหมดที่ import ไว้ ถ้ายังไม่มี (ตารางที่มีอยู่แล้วจะไม่ถูกแตะ) —
# ไม่ใช่ migration tool เต็มรูปแบบ ใช้ได้แค่ตอน "สร้างใหม่" เท่านั้น การแก้ schema ของตารางเดิมต้องเขียน
# migration script แยก (ดู plo-evaluation/scripts/migrate_*.py)
Base.metadata.create_all(bind=engine)

# สร้าง instance หลักของ FastAPI app
app = FastAPI(
    title="PLO Evaluation System API",
    description="Backend API for Program Learning Outcomes Evaluation",
    version="1.0.0",
)

# Add CORS middleware for React frontend - อ่านจาก env var ALLOWED_ORIGINS (คั่นด้วย comma) เพื่อ
# ให้ตั้งค่า origin ของ frontend ที่ deploy จริง (เช่น Vercel) ได้โดยไม่ต้องแก้โค้ด ถ้าไม่ได้ตั้งค่าไว้
# (เช่นตอน dev local) จะ fallback ไปใช้ localhost เดิมเหมือนก่อนหน้านี้
_allowed_origins_env = os.getenv("ALLOWED_ORIGINS")
ALLOWED_ORIGINS = (
    [origin.strip() for origin in _allowed_origins_env.split(",") if origin.strip()]
    if _allowed_origins_env
    else ["http://localhost:3000", "http://localhost:8080"]
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    # Content-Disposition ไม่ถูก expose ให้ JS ฝั่ง browser อ่านได้โดย default ข้าม origin (CORS spec -
    # allow_headers ควบคุมแค่ request header ที่ browser ส่งได้ ไม่ใช่ response header ที่ JS อ่านได้)
    # ต้องเปิดชื่อ header ที่ frontend ต้องอ่านเองตรงๆ ผ่าน expose_headers - จำเป็นเพราะ
    # exportOfferingMco5Excel() (api/client.js) ดึงชื่อไฟล์จาก header นี้มาตั้งชื่อตอนดาวน์โหลด (ดู
    # TASK-export-mco5.md) ไม่งั้นจะได้ response.headers['content-disposition'] เป็น undefined เงียบๆ
    # ทั้งที่ backend ส่งมาถูกต้องแล้ว (เคยเจอจริงตอนทดสอบ - ไฟล์ดาวน์โหลดได้แต่ชื่อไฟล์ผิดเป็นชื่อ
    # fallback เสมอ)
    expose_headers=["Content-Disposition"],
)


# endpoint หน้าแรกของ API — ใช้เช็คว่า backend รันอยู่และดูลิงก์ไปหน้า docs (/docs, Swagger UI อัตโนมัติ
# ของ FastAPI) ไม่ได้ใช้งานจริงจากฝั่ง frontend
@app.get("/")
def read_root():
    """Welcome endpoint"""
    return {
        "message": "PLO Evaluation System API",
        "version": "1.0.0",
        "docs": "/docs"
    }


# endpoint เช็คสถานะ (health check) — Render ใช้ endpoint แบบนี้เป็นมาตรฐานเพื่อตรวจว่า service ยังตอบ
# สนองอยู่ (ไม่ error, ไม่ค้าง) ไม่ต้อง auth เพราะต้องเรียกได้จากระบบ monitoring ภายนอก
@app.get("/health")
def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}


# ลงทะเบียน router ทั้งหมด — ทุก endpoint ในระบบขึ้นอยู่กับบล็อกนี้ (ไม่ include = 404 แม้โค้ด
# endpoint จะถูกต้อง) เรียงตามกลุ่มงานคร่าว ๆ (auth -> ผู้ใช้ -> หลักสูตร -> PLO/YLO/CLO -> วิชา/
# นักศึกษา -> คะแนน -> นำเข้าข้อมูล) ยกเว้นจุดที่มีคอมเมนต์กำกับไว้ด้านล่างว่าลำดับมีผลจริง ห้ามสลับ
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(curriculum.router)
app.include_router(curriculum_import.router)
# plo_calculation.router's literal /plo/achievement(/cohort) paths must be
# registered before plo.router's /plo/{plo_id} - Starlette matches routes in
# registration order, and the dynamic segment would otherwise shadow them.
app.include_router(plo_calculation.router)
app.include_router(clo_calculation.router)
app.include_router(plo.router)
app.include_router(ylo.router)
app.include_router(ylo_calculation.router)
app.include_router(ylo_plo_mapping.router)
app.include_router(courses.router)
app.include_router(course_import.router)
app.include_router(course_plo.router)
app.include_router(study_plan.router)
app.include_router(course_offering.router)
app.include_router(students.router)
app.include_router(enrollment.router)
app.include_router(clo.router)
app.include_router(clo_plo_mapping.router)
app.include_router(assessment.router)
app.include_router(item_clo.router)
app.include_router(roster_import.router)


# ให้รันไฟล์นี้ตรง ๆ ได้ตอน dev local (python app/main.py) โดยไม่ต้องพิมพ์คำสั่ง uvicorn เอง —
# reload=True คือ auto-reload เมื่อแก้โค้ด (ใช้เฉพาะตอน dev เท่านั้น ไม่ใช้ path นี้ตอน deploy จริงบน
# Render ซึ่งเรียก uvicorn ผ่าน start command ของตัวเองแทน)
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
