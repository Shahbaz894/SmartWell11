
import uuid
from sqlalchemy import Column, String, Integer, Boolean, DateTime, ForeignKey, JSON
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime, timezone
from app.db.base_class import Base

class FirmwareRelease(Base):
    __tablename__ = "firmware_releases"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    version = Column(String(20), nullable=False, index=True)
    model = Column(String(50), nullable=False, default="tubewell-esp32dev")
    size_bytes = Column(Integer, nullable=False)
    sha256 = Column(String(64), nullable=False)
    notes = Column(String(5000), default="", nullable=True)
    target_scope = Column(String(20), nullable=False)  # 'selected' or 'all_model'
    target_uids = Column(JSON, default=list, nullable=False)  # List of device UIDs
    state = Column(String(20), default="draft", nullable=False)  # draft, published, withdrawn
    uploaded_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    file_path = Column(String(500), nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    published_at = Column(DateTime(timezone=True), nullable=True)