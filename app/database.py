"""
ทำอะไร : ตั้งค่าการเชื่อมต่อฐานข้อมูล PostgreSQL — สร้าง SQLAlchemy engine, session factory, และ
         Base class ที่ทุก model (app/models/*.py) ต้องสืบทอด

เชื่อมกับ : ทุก route ที่ต้องเข้าถึงฐานข้อมูลใช้ Depends(get_db) เป็น dependency เพื่อขอ session —
            app/main.py เรียก Base.metadata.create_all() ตอนสตาร์ทแอปเพื่อสร้างตารางที่ยังไม่มี

ถ้าแก้ : DATABASE_URL มาจาก environment variable (.env) เท่านั้น — ถ้าค่าไม่ถูกต้องหรือฐานข้อมูล
         ต่อไม่ได้ แอปจะพังตั้งแต่ import ไฟล์นี้ เปลี่ยน pool_size/max_overflow กระทบจำนวน connection
         พร้อมกันสูงสุดที่ต่อฐานข้อมูลได้ (ค่าสูงเกินไปอาจชนกับ connection limit ของ Postgres ฝั่ง
         hosting เช่น Render)
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from dotenv import load_dotenv
import os

# โหลดตัวแปรจากไฟล์ .env เข้า environment (เช่น DATABASE_URL) — ไม่มีผลถ้า .env ไม่มีไฟล์ (เช่นตอน
# deploy จริงที่ตั้งค่า env var ผ่านระบบ hosting โดยตรงแทน)
load_dotenv()

# อ่าน connection string ของฐานข้อมูลจาก .env
DATABASE_URL = os.getenv("DATABASE_URL")

# สร้าง engine เชื่อมต่อฐานข้อมูล — echo=True พิมพ์ SQL ทุกคำสั่งออก log (มีประโยชน์ตอน dev/debug
# แต่ทำให้ log รกและช้าลงเล็กน้อยตอนใช้งานจริง) pool_size/max_overflow จำกัดจำนวน connection พร้อมกัน
engine = create_engine(
    DATABASE_URL,
    echo=True,  # Set to False in production
    pool_size=10,
    max_overflow=20,
)

# factory สำหรับสร้าง session ใหม่แต่ละ request (autocommit/autoflush ปิดไว้ ต้องเรียก db.commit() เอง)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# คลาสฐานที่ทุก model ใน app/models/*.py ต้องสืบทอด (ใช้ประกาศ __tablename__, Column ฯลฯ)
Base = declarative_base()


# Dependency for FastAPI
def get_db():
    """
    ทำอะไร : สร้าง database session ใหม่ให้ endpoint 1 request ใช้งาน แล้วปิด session ให้อัตโนมัติเมื่อ
             request จบ (ไม่ว่าจะสำเร็จหรือ error)

    เชื่อมกับ : ทุก route ที่แตะฐานข้อมูลประกาศ `db: Session = Depends(get_db)` — FastAPI จะเรียก
                generator นี้ให้อัตโนมัติต่อ request

    ถ้าแก้ : yield ทำให้โค้ดหลัง yield (db.close()) รันหลัง endpoint ทำงานเสร็จเสมอ แม้ endpoint จะ
             raise exception ก็ตาม (try/finally) — ห้ามลบ finally ไม่งั้น connection จะรั่วสะสม
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
