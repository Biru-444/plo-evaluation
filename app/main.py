"""
FastAPI Main Application
PLO Evaluation System - Backend
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.database import Base, engine
from app.routes import (
    assessment,
    auth,
    clo,
    clo_calculation,
    clo_plo_mapping,
    course_offering,
    course_plo,
    courses,
    curriculum,
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


app.include_router(auth.router)
app.include_router(users.router)
app.include_router(curriculum.router)
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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
