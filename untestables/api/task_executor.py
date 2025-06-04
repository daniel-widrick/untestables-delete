"""Task executor for background processing."""
import subprocess
import shlex
import time
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from untestables.models.scan_task import ScanTask
from untestables.analyzer import AnalyzerService
from untestables.config import Config
from common.logging import LoggingManager


class TaskExecutor:
    """Executes background tasks for scanning."""
    
    def __init__(self, config: Config):
        self.config = config
        self.engine = create_engine(config.database_url)
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        self.logger = LoggingManager.setup_logger("app.task_executor")
    
    def _get_session(self):
        """Get a new database session."""
        return self.SessionLocal()
    
    def _update_task_status(
        self,
        task_id: str,
        status: str,
        started_at: Optional[datetime] = None,
        completed_at: Optional[datetime] = None,
        result: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
        progress: Optional[Dict[str, Any]] = None
    ):
        """Update task status in database."""
        db = self._get_session()
        try:
            task = db.query(ScanTask).filter(ScanTask.id == task_id).first()
            if task:
                task.status = status
                if started_at:
                    task.started_at = started_at
                if completed_at:
                    task.completed_at = completed_at
                if result:
                    task.result = result
                if error:
                    task.error = error
                if progress:
                    task.progress = progress
                db.commit()
        finally:
            db.close()
    
    def execute_scan_task(
        self,
        task_id: str,
        min_stars: int,
        max_stars: int,
        force_rescan: bool = False,
        rescan_days: Optional[int] = None
    ):
        """Execute a scan task in the background."""
        self.logger.info(f"Starting scan task {task_id}: stars {min_stars}-{max_stars}")
        
        # Update task status to running
        self._update_task_status(
            task_id=task_id,
            status="running",
            started_at=datetime.utcnow()
        )
        
        try:
            # Build command
            command = f"poetry run untestables find-repos --min-stars {min_stars} --max-stars {max_stars}"
            
            if force_rescan:
                command += " --force-rescan"
            elif rescan_days:
                command += f" --rescan-days {rescan_days}"
            
            self.logger.info(f"Executing command: {command}")
            
            # Execute subprocess
            process = subprocess.Popen(
                shlex.split(command),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            # Wait for completion
            stdout, stderr = process.communicate()
            
            if process.returncode == 0:
                # Success
                self.logger.info(f"Task {task_id} completed successfully")
                
                # Try to parse output for results
                result = {
                    "exit_code": 0,
                    "stdout": stdout[-1000:] if stdout else None,  # Last 1000 chars
                }
                
                # Extract repository count if possible
                if "Found" in stdout and "repositories" in stdout:
                    try:
                        # Parse lines like "Found 123 repositories"
                        for line in stdout.split('\n'):
                            if "Found" in line and "repositories" in line:
                                parts = line.split()
                                idx = parts.index("Found")
                                if idx + 1 < len(parts):
                                    result["repositories_found"] = int(parts[idx + 1])
                    except:
                        pass
                
                self._update_task_status(
                    task_id=task_id,
                    status="completed",
                    completed_at=datetime.utcnow(),
                    result=result
                )
            else:
                # Failure
                self.logger.error(f"Task {task_id} failed with exit code {process.returncode}")
                self._update_task_status(
                    task_id=task_id,
                    status="failed",
                    completed_at=datetime.utcnow(),
                    error=f"Process exited with code {process.returncode}. stderr: {stderr[-1000:]}"
                )
        
        except Exception as e:
            self.logger.error(f"Task {task_id} failed with exception: {str(e)}")
            self._update_task_status(
                task_id=task_id,
                status="failed",
                completed_at=datetime.utcnow(),
                error=str(e)
            )
    
    def execute_orchestration(self, task_id: str, duration_hours: int):
        """Execute orchestration task."""
        self.logger.info(f"Starting orchestration task {task_id} for {duration_hours} hours")
        
        # Update task status to running
        self._update_task_status(
            task_id=task_id,
            status="running",
            started_at=datetime.utcnow()
        )
        
        analyzer = AnalyzerService()
        start_time = datetime.utcnow()
        end_time = start_time + timedelta(hours=duration_hours)
        
        tasks_created = 0
        
        try:
            while datetime.utcnow() < end_time:
                # Check if task was cancelled
                db = self._get_session()
                task = db.query(ScanTask).filter(ScanTask.id == task_id).first()
                db.close()
                
                if task and task.status == "cancelled":
                    self.logger.info(f"Orchestration task {task_id} was cancelled")
                    break
                
                # Find gaps
                gaps = analyzer.find_gaps()
                
                if gaps:
                    # Process first gap
                    gap = gaps[0]
                    
                    # Create a new scan task
                    scan_task_id = str(uuid.uuid4())
                    scan_task = ScanTask(
                        id=scan_task_id,
                        task_type="scan_range",
                        status="pending",
                        min_stars=gap["min_stars"],
                        max_stars=gap["max_stars"],
                        parameters={"orchestrated": True}
                    )
                    
                    db = self._get_session()
                    db.add(scan_task)
                    db.commit()
                    db.close()
                    
                    # Execute scan task
                    self.execute_scan_task(
                        task_id=scan_task_id,
                        min_stars=gap["min_stars"],
                        max_stars=gap["max_stars"]
                    )
                    
                    tasks_created += 1
                    
                    # Update orchestration progress
                    self._update_task_status(
                        task_id=task_id,
                        status="running",
                        progress={
                            "tasks_created": tasks_created,
                            "current_gap": gap,
                            "remaining_gaps": len(gaps) - 1
                        }
                    )
                    
                    # Short sleep between tasks
                    time.sleep(60)  # 1 minute
                else:
                    # No gaps found, sleep longer
                    self.logger.info("No gaps found, sleeping for 1 hour")
                    time.sleep(3600)  # 1 hour
            
            # Mark orchestration as completed
            self._update_task_status(
                task_id=task_id,
                status="completed",
                completed_at=datetime.utcnow(),
                result={
                    "tasks_created": tasks_created,
                    "duration_hours": duration_hours
                }
            )
            
        except Exception as e:
            self.logger.error(f"Orchestration task {task_id} failed: {str(e)}")
            self._update_task_status(
                task_id=task_id,
                status="failed",
                completed_at=datetime.utcnow(),
                error=str(e)
            )


# Import uuid at the top of the file
import uuid