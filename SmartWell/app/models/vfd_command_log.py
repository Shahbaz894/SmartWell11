import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Boolean, Float, Integer, DateTime, ForeignKey, JSON, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from app.db.base_class import Base

class VFDCommandLog(Base):
    __tablename__ = "vfd_command_logs"

    command_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    device_uid = Column(String(100), index=True, nullable=False)
    command = Column(String(50), nullable=False)  # 'ON', 'OFF', 'SET_REFERENCE_FREQUENCY', 'RESET_VFD'
    reference_frequency = Column(Float, nullable=True)
    status = Column(String(30), default="PENDING", nullable=False)  # PENDING, PUBLISHED, ACKNOWLEDGED, OBSERVED, FAILED
    requested_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    published_at = Column(DateTime(timezone=True), nullable=True)
    observed_at = Column(DateTime(timezone=True), nullable=True)
    deadline_at = Column(DateTime(timezone=True), nullable=True)
    execution_acknowledged = Column(Boolean, default=False, nullable=False)
    acknowledgment_message = Column(String(500), nullable=True)
    error = Column(String(500), nullable=True)

class FirmwareRelease(Base):
    __tablename__ = "firmware_releases"
    __table_args__ = (UniqueConstraint("model", "version", name="uq_firmware_model_version"),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    version = Column(String(20), nullable=False, index=True)
    model = Column(String(50), default="tubewell-esp32dev", nullable=False)
    size_bytes = Column(Integer, nullable=False)
    sha256 = Column(String(64), nullable=False)
    notes = Column(String(5000), default="", nullable=True)
    target_scope = Column(String(20), nullable=False)  # 'selected' or 'all_model'
    target_uids = Column(JSON, default=list, nullable=False)
    state = Column(String(20), default="draft", nullable=False)  # 'draft', 'published', 'withdrawn'
    uploaded_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    file_path = Column(String(500), nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    published_at = Column(DateTime(timezone=True), nullable=True)