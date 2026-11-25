import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Boolean, Float, DateTime, ForeignKey, Table
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.db.base_class import Base

# Many-to-Many sharing table
device_assignments = Table(
    "device_assignments",
    Base.metadata,
    Column("device_id", UUID(as_uuid=True), ForeignKey("devices.id", ondelete="CASCADE"), primary_key=True),
    Column("user_id", UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("can_control", Boolean, default=False, nullable=False),
    Column("assigned_at", DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
)

class Device(Base):
    __tablename__ = "devices"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)  # Internal UUID
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)  # Owner UUID
    device_uid = Column(String(100), unique=True, index=True, nullable=False)  # ESP32 Provisioned Hardware UID
    device_name = Column(String(100), nullable=False)
    sim_number = Column(String(50), nullable=True)
    location = Column(String(200), nullable=True)
    reference_freq = Column(Float, default=25.0, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    # Relationships
    owner = relationship("User", back_populates="owned_devices", foreign_keys=[user_id])
    assigned_users = relationship("User", secondary=device_assignments, back_populates="assigned_devices")
    telemetry = relationship(
        "MotorTelemetry",
        back_populates="device",
        primaryjoin="Device.device_uid == foreign(MotorTelemetry.device_id)",
    )
    settings = relationship("DeviceSettings", back_populates="device", uselist=False, cascade="all, delete-orphan")
    automation = relationship("DeviceAutomation", back_populates="device", uselist=False, cascade="all, delete-orphan")