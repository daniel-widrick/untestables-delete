"""SQLAlchemy model for scan tasks."""
from datetime import datetime
from typing import Optional, Dict, Any

from sqlalchemy import Column, String, Integer, DateTime, Text, JSON, func
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class ScanTask(Base):
    """Model for tracking scan tasks."""
    
    __tablename__ = 'scan_tasks'
    
    id = Column(String, primary_key=True)
    task_type = Column(String, nullable=False)  # 'scan_range', 'find_gaps', etc.
    status = Column(String, nullable=False)  # 'pending', 'running', 'completed', 'failed'
    
    # For scan_range tasks
    min_stars = Column(Integer, nullable=True)
    max_stars = Column(Integer, nullable=True)
    
    # Generic parameters and results
    parameters = Column(JSON, nullable=True)
    result = Column(JSON, nullable=True)
    error = Column(Text, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    
    # Progress tracking (e.g., {"current": 100, "total": 1000})
    progress = Column(JSON, nullable=True)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert task to dictionary representation."""
        return {
            'id': self.id,
            'task_type': self.task_type,
            'status': self.status,
            'min_stars': self.min_stars,
            'max_stars': self.max_stars,
            'parameters': self.parameters,
            'result': self.result,
            'error': self.error,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'progress': self.progress,
        }