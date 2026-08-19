"""
FastAPI Main Application
PLO Evaluation System - Backend
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.database import Base, engine
from app.routes import assessment, courses, curriculum, enrollment, plo_calculation, students

# Create tables in database
Base.metadata.create_all(bind=engine)

# Initialize FastAPI app
app = FastAPI(
    title="PLO Evaluation System API",
    description="Backend API for Program Learning Outcomes Evaluation",
    version="1.0.0",
)

# Add CORS middleware for React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:8080"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Root endpoint
@app.get("/")
def read_root():
    """Welcome endpoint"""
    return {
        "message": "PLO Evaluation System API",
        "version": "1.0.0",
        "docs": "/docs"
    }


@app.get("/health")
def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}


app.include_router(curriculum.router)
app.include_router(courses.router)
app.include_router(students.router)
app.include_router(enrollment.router)
app.include_router(assessment.router)
app.include_router(plo_calculation.router)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
