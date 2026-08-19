# PLO Evaluation System - Backend

FastAPI backend สำหรับระบบประเมินผลลัพธ์การเรียนรู้ (Program Learning Outcomes)

## 🚀 เริ่มต้น

### 1. Setup Virtual Environment
```bash
python -m venv venv
source venv/bin/activate  # Mac/Linux
# หรือ
venv\Scripts\activate      # Windows
```

### 2. ติดตั้ง Dependencies
```bash
pip install -r requirements.txt
```

### 3. ตั้งค่า Environment Variables
```bash
cp .env.example .env
# แล้วแก้ไข .env ใส่ PostgreSQL credentials ของคุณ
```

### 4. รัน Server
```bash
python app/main.py
# หรือ
uvicorn app.main:app --reload
```

Server จะเปิดที่ `http://localhost:8000`

## 📚 API Documentation
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## 📁 Project Structure
```
PLO/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI app entry point
│   ├── database.py          # DB connection & session
│   ├── models/              # SQLAlchemy ORM models
│   ├── schemas/             # Pydantic request/response schemas
│   └── routes/              # API endpoints
├── requirements.txt         # Python dependencies
├── .env.example            # Environment variables template
├── .gitignore
└── README.md
```

## 🛠️ Technology Stack
- **FastAPI** - Modern web framework
- **SQLAlchemy** - ORM for database
- **PostgreSQL** - Database
- **Pydantic** - Data validation
- **Uvicorn** - ASGI server

## 📝 Database Schema
16 tables: User, Curriculum, PLO, YLO, Course, CLO, Student, Enrollment, Assessment Item, etc.

See `plo_evaluation_system_schema_postgresql.sql` for full schema.
