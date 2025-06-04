"""Main FastAPI application."""
import os
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any

from fastapi import FastAPI, BackgroundTasks, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import create_engine, func
from sqlalchemy.orm import sessionmaker, Session

from untestables.models.scan_task import ScanTask, Base
from untestables.api.task_executor import TaskExecutor
from untestables.config import get_config


# Initialize FastAPI app
app = FastAPI(
    title="Untestables API",
    description="API for managing GitHub repository scanning for missing tests",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Database setup
config = get_config()
engine = create_engine(config.database_url)
Base.metadata.create_all(bind=engine)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Initialize task executor
task_executor = TaskExecutor(config)


# Dependency to get DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Pydantic models
class ScanRangeRequest(BaseModel):
    min_stars: int
    max_stars: int
    force_rescan: bool = False
    rescan_days: Optional[int] = None


class TaskResponse(BaseModel):
    id: str
    task_type: str
    status: str
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    min_stars: Optional[int] = None
    max_stars: Optional[int] = None
    progress: Optional[Dict[str, Any]] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class GapResponse(BaseModel):
    min_stars: int
    max_stars: int
    size: int


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "service": "Untestables API",
        "version": "1.0.0",
        "endpoints": {
            "scan": "/scan/range",
            "gaps": "/gaps",
            "tasks": "/tasks",
            "task_status": "/tasks/{task_id}",
            "health": "/health"
        }
    }


@app.get("/health")
async def health_check(db: Session = Depends(get_db)):
    """Health check endpoint."""
    try:
        # Check database connection
        db.execute("SELECT 1")
        
        # Get task statistics
        total_tasks = db.query(func.count(ScanTask.id)).scalar()
        pending_tasks = db.query(func.count(ScanTask.id)).filter(
            ScanTask.status == "pending"
        ).scalar()
        running_tasks = db.query(func.count(ScanTask.id)).filter(
            ScanTask.status == "running"
        ).scalar()
        
        return {
            "status": "healthy",
            "database": "connected",
            "task_stats": {
                "total": total_tasks,
                "pending": pending_tasks,
                "running": running_tasks
            }
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e)
        }


@app.post("/scan/range", response_model=TaskResponse)
async def create_scan_task(
    request: ScanRangeRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Create a new scan task for a star range."""
    # Create task record
    task_id = str(uuid.uuid4())
    task = ScanTask(
        id=task_id,
        task_type="scan_range",
        status="pending",
        min_stars=request.min_stars,
        max_stars=request.max_stars,
        parameters={
            "force_rescan": request.force_rescan,
            "rescan_days": request.rescan_days
        }
    )
    
    db.add(task)
    db.commit()
    db.refresh(task)
    
    # Add to background tasks
    background_tasks.add_task(
        task_executor.execute_scan_task,
        task_id=task_id,
        min_stars=request.min_stars,
        max_stars=request.max_stars,
        force_rescan=request.force_rescan,
        rescan_days=request.rescan_days
    )
    
    return TaskResponse(**task.to_dict())


@app.get("/gaps", response_model=List[GapResponse])
async def get_gaps(
    min_size: Optional[int] = None,
    limit: Optional[int] = 100
):
    """Get current gaps in star range coverage."""
    from untestables.analyzer import AnalyzerService
    
    analyzer = AnalyzerService()
    gaps = analyzer.find_gaps()
    
    # Filter by minimum size if specified
    if min_size:
        gaps = [g for g in gaps if (g["max_stars"] - g["min_stars"]) >= min_size]
    
    # Limit results
    gaps = gaps[:limit]
    
    return [
        GapResponse(
            min_stars=gap["min_stars"],
            max_stars=gap["max_stars"],
            size=gap["max_stars"] - gap["min_stars"]
        )
        for gap in gaps
    ]


@app.get("/tasks", response_model=List[TaskResponse])
async def list_tasks(
    status: Optional[str] = None,
    task_type: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    db: Session = Depends(get_db)
):
    """List tasks with optional filtering."""
    query = db.query(ScanTask)
    
    if status:
        query = query.filter(ScanTask.status == status)
    if task_type:
        query = query.filter(ScanTask.task_type == task_type)
    
    # Order by created_at descending (newest first)
    query = query.order_by(ScanTask.created_at.desc())
    
    # Apply pagination
    tasks = query.offset(offset).limit(limit).all()
    
    return [TaskResponse(**task.to_dict()) for task in tasks]


@app.get("/tasks/{task_id}", response_model=TaskResponse)
async def get_task_status(
    task_id: str,
    db: Session = Depends(get_db)
):
    """Get status of a specific task."""
    task = db.query(ScanTask).filter(ScanTask.id == task_id).first()
    
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    return TaskResponse(**task.to_dict())


@app.post("/tasks/{task_id}/cancel")
async def cancel_task(
    task_id: str,
    db: Session = Depends(get_db)
):
    """Cancel a pending or running task."""
    task = db.query(ScanTask).filter(ScanTask.id == task_id).first()
    
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    if task.status not in ["pending", "running"]:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot cancel task in status: {task.status}"
        )
    
    # Update task status
    task.status = "cancelled"
    task.completed_at = datetime.utcnow()
    db.commit()
    
    return {"message": "Task cancelled", "task_id": task_id}


@app.get("/stats/repositories")
async def get_repository_stats(db: Session = Depends(get_db)):
    """Get statistics about scanned repositories."""
    from untestables.github.models import Repository
    
    total_repos = db.query(func.count(Repository.id)).scalar()
    repos_without_tests = db.query(func.count(Repository.id)).filter(
        Repository.missing_test_directory == True,
        Repository.missing_test_files == True,
        Repository.missing_test_config == True,
        Repository.missing_ci_config == True,
        Repository.missing_readme_mention == True
    ).scalar()
    
    # Get star distribution
    star_distribution = db.query(
        func.floor(Repository.star_count / 100) * 100,
        func.count(Repository.id)
    ).group_by(
        func.floor(Repository.star_count / 100)
    ).order_by(
        func.floor(Repository.star_count / 100)
    ).all()
    
    return {
        "total_repositories": total_repos,
        "repositories_without_tests": repos_without_tests,
        "percentage_without_tests": (
            round(repos_without_tests / total_repos * 100, 2) 
            if total_repos > 0 else 0
        ),
        "star_distribution": [
            {
                "range_start": int(start),
                "range_end": int(start + 99),
                "count": count
            }
            for start, count in star_distribution
        ]
    }


@app.post("/orchestrate/start")
async def start_orchestration(
    duration_hours: int = 24,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Start the orchestration process to automatically find and scan gaps."""
    # Create orchestration task
    task_id = str(uuid.uuid4())
    task = ScanTask(
        id=task_id,
        task_type="orchestration",
        status="pending",
        parameters={
            "duration_hours": duration_hours
        }
    )
    
    db.add(task)
    db.commit()
    
    # Add to background tasks
    background_tasks.add_task(
        task_executor.execute_orchestration,
        task_id=task_id,
        duration_hours=duration_hours
    )
    
    return {
        "task_id": task_id,
        "message": f"Orchestration started for {duration_hours} hours"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)