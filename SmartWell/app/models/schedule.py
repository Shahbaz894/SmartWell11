import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Boolean, DateTime, JSON
from sqlalchemy.dialects.postgresql import UUID
from app.db.base_class import Base

class Schedule(Base):
    __tablename__ = "schedules"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    device_id = Column(String(100), index=True, nullable=False)  # device_uid
    schedule_type = Column(String(30), nullable=False)           # 'daily', 'weekly', 'monthly'
    pattern = Column(JSON, nullable=False)                        # Dynamic JSON pattern
    schedule_name = Column(String(100), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))