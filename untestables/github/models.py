"""SQLAlchemy models for GitHub data."""
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

Base = declarative_base()


class Repository(Base):
    __tablename__ = 'repositories'
    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)  # Repository name (e.g., "my-project")
    description = Column(Text, nullable=True)
    star_count = Column(Integer, nullable=False, index=True)
    url = Column(String(255), nullable=False)  # HTML URL (e.g., "https://github.com/owner/my-project")
    missing_test_directories = Column(Boolean, nullable=False)
    missing_test_files = Column(Boolean, nullable=False)
    missing_test_config_files = Column(Boolean, nullable=False)
    missing_cicd_configs = Column(Boolean, nullable=False)
    missing_readme_mentions = Column(Boolean, nullable=False)
    last_scanned_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    language = Column(String(50), nullable=True)
    last_push_time = Column(DateTime, nullable=True)
    last_metadata_update_time = Column(DateTime, nullable=True)
    creation_time = Column(DateTime, nullable=True)
    is_active = Column(Boolean, nullable=True, default=True)  # Track if the repository is still active

    def __repr__(self):
        return f"<Repository(name='{self.name}', url='{self.url}', last_scanned_at='{self.last_scanned_at}')>" 
