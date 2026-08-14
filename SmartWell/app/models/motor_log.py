"""
MotorLog model.

device_id stores Device.device_uid, e.g. "ESP32_001_TW".
"""

import uuid

from sqlalchemy import DateTime, Integer, String, text,Column
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.db.base_class import Base


class MotorLog(Base):
    __tablename__ = "motor_logs"

    # PostgreSQL UUID primary key
    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False,
        index=True,
    )

    # Stores Device.device_uid, e.g. "ESP32_001_TW"
    device_id = Column(
        String(255),
        nullable=False,
        index=True,
    )

    # Motor start time
    start_time = Column(
        DateTime,
        nullable=False,
        index=True,
    )

    # Motor stop time
    end_time = Column(
        DateTime,
        nullable=True,
    )

    # Calculated duration in minutes
    duration_minutes = Column(
        Integer,
        nullable=True,
    )

    # "app", "physical", "schedule", "manual", etc.
    trigger_type = Column(
        String(20),
        nullable=False,
    )

    # Customer who started the motor session
    customer_name = Column(
        String(100),
        nullable=False,
        index=True,
    )

    # ON while running, OFF after stopping
    status = Column(
        String(10),
        nullable=False,
        server_default=text("'ON'"),
        index=True,
    )

    # Database creation timestamp
    created_at = Column(
        DateTime,
        nullable=False,
        server_default=text("now()"),
    )

    # Logical relationship with Device.device_uid
    device = relationship(
        "Device",
        back_populates="motor_logs",
        primaryjoin="foreign(MotorLog.device_id) == Device.device_uid",
    )

    # Relationship with KhataEntry
    khata_entries = relationship(
        "KhataEntry",
        back_populates="motor_log",
    )