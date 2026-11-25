import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Boolean, Integer, DateTime, ForeignKey, JSON
from sqlalchemy.dialects.postgresql import UUID
from app.db.base_class import Base

class MotorLog(Base):
    __tablename__ = "motor_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(UUID(as_uuid=True), nullable=True)
    command_id = Column(UUID(as_uuid=True), nullable=True)
    device_id = Column(String(100), nullable=False)  # device_uid
    customer_name = Column(String(100), nullable=True)
    trigger_type = Column(String(20), default="app", nullable=False)  # 'app', 'physical', 'schedule', 'time'
    status = Column(String(30), default="PENDING_START", nullable=False)  # 'PENDING_START', 'ON', 'COMPLETED', etc.
    start_time = Column(DateTime(timezone=True), nullable=True)
    end_time = Column(DateTime(timezone=True), nullable=True)
    duration_minutes = Column(Integer, nullable=True)
    runtime_seconds = Column(Integer, nullable=True)
    needs_review = Column(Boolean, default=False, nullable=False)
    review_reason = Column(String(500), nullable=True)
    editable = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

class ResolutionAuditLog(Base):
    __tablename__ = "resolution_audit_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    request_id = Column(UUID(as_uuid=True), unique=True, nullable=False)
    target_kind = Column(String(20), nullable=False)  # 'session' or 'legacy'
    target_id = Column(UUID(as_uuid=True), nullable=False)
    action = Column(String(20), nullable=False)       # 'complete' or 'cancel'
    reason = Column(String(2000), nullable=False)
    resolved_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    result_snapshot = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))