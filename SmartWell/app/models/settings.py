import uuid
from sqlalchemy import Column, String, Boolean, Float, Integer, DateTime, ForeignKey, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from app.db.base_class import Base

class DeviceSettings(Base):
    __tablename__ = "device_settings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    device_uid = Column(String(100), ForeignKey("devices.device_uid", ondelete="CASCADE"), unique=True, nullable=False)

    # Desired & Confirmed
    desired_direction = Column(String(20), default="FORWARD", nullable=True)
    confirmed_direction = Column(String(20), default="FORWARD", nullable=True)
    desired_frequency = Column(Float, default=25.0, nullable=True)
    confirmed_frequency = Column(Float, default=25.0, nullable=True)

    # Revisions & State
    direction_revision = Column(Integer, default=1, nullable=False)
    frequency_revision = Column(Integer, default=1, nullable=False)
    direction_state = Column(String(30), default="synced", nullable=False)
    frequency_state = Column(String(30), default="synced", nullable=False)
    last_snapshot_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    device = relationship("Device", back_populates="settings")

class DeviceAutomation(Base):
    __tablename__ = "device_automations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    device_uid = Column(String(100), ForeignKey("devices.device_uid", ondelete="CASCADE"), unique=True, nullable=False)

    auto_restart_enabled = Column(Boolean, default=False, nullable=False)
    max_attempts = Column(Integer, default=3, nullable=False)
    retry_delay_seconds = Column(Integer, default=30, nullable=False)
    offline_stop_enabled = Column(Boolean, default=False, nullable=False)
    offline_timeout_seconds = Column(Integer, default=60, nullable=False)

    revision = Column(Integer, default=1, nullable=False)
    state = Column(String(30), default="synced", nullable=False)
    confirmed_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    device = relationship("Device", back_populates="automation")