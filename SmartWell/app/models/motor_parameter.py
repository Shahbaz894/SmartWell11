import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, BigInteger, String, Boolean, Float, Integer, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base_class import Base

class DeviceSettings(Base):
    __tablename__ = "device_settings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    device_uid = Column(String(100), ForeignKey("devices.device_uid", ondelete="CASCADE"), unique=True, nullable=False)

    # Desired vs Confirmed values
    desired_direction = Column(String(20), default="FORWARD", nullable=True)
    confirmed_direction = Column(String(20), default="FORWARD", nullable=True)
    desired_frequency = Column(Float, default=25.0, nullable=True)
    confirmed_frequency = Column(Float, default=25.0, nullable=True)

    # Concurrency revision fields
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

    # Mandatory 5 Automation Policy Fields
    auto_restart_enabled = Column(Boolean, default=False, nullable=False)
    max_attempts = Column(Integer, default=3, nullable=False)             # 1-10
    retry_delay_seconds = Column(Integer, default=30, nullable=False)     # 5-3600 seconds
    offline_stop_enabled = Column(Boolean, default=False, nullable=False)
    offline_timeout_seconds = Column(Integer, default=60, nullable=False) # 10-86400 seconds

    revision = Column(Integer, default=1, nullable=False)
    state = Column(String(30), default="synced", nullable=False)
    confirmed_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    device = relationship("Device", back_populates="automation")

class MotorTelemetry(Base):
    __tablename__ = "motor_telemetry"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # STRING — stores Device.device_uid, example: ESP32_001_TW
    device_id = Column(String(100), nullable=False, index=True)

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )

    timestamp = Column(BigInteger, nullable=False, index=True)

    freq = Column(Float)
    current = Column(Float)
    voltage = Column(Float)
    dcbus = Column(Float)
    power = Column(Float)
    energy_in = Column(Float)

    trigger_type = Column(String(20), nullable=True)

    fault = Column(Integer)
    fault_code = Column(Integer)
    status_code = Column(Integer)
    reference_freq = Column(Float)
    motor_speed = Column(Float)
    power_percent = Column(Float)
    torque_percent = Column(Float)
    is_live = Column(Integer)

    device = relationship(
        "Device",
        back_populates="telemetry",
        primaryjoin="foreign(MotorTelemetry.device_id) == Device.device_uid",
    )