import uuid
from sqlalchemy import Column, String, DateTime, ForeignKey, JSON
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime, timezone
from app.db.base_class import Base

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