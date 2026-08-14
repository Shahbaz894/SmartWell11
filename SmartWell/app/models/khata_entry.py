"""
KhataEntry model.

Stores customer billing/session information for motor usage.

device_id stores Device.device_uid, for example:
    ESP32_001_TW

motor_log_id stores MotorLog.id, which is a PostgreSQL UUID.
"""

import uuid

from sqlalchemy import (
    Column,
    String,
    TIMESTAMP,
    Numeric,
    Boolean,
    ForeignKey,
    Date,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.db.base_class import Base


class KhataEntry(Base):
    __tablename__ = "khata_entries"

    # ------------------------------------------------------------------
    # Primary Key
    # ------------------------------------------------------------------

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False,
        index=True,
    )

    # ------------------------------------------------------------------
    # Owner
    # ------------------------------------------------------------------

    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # ------------------------------------------------------------------
    # Device
    #
    # Stores Device.device_uid, e.g. ESP32_001_TW.
    # This is NOT Device.id.
    # ------------------------------------------------------------------

    device_id = Column(
        String(100),
        nullable=False,
        index=True,
    )

    # ------------------------------------------------------------------
    # Motor Log
    #
    # MotorLog.id is UUID, therefore motor_log_id must also be UUID.
    # ------------------------------------------------------------------

    motor_log_id = Column(
        UUID(as_uuid=True),
        ForeignKey(
            "motor_logs.id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    # ------------------------------------------------------------------
    # Customer
    # ------------------------------------------------------------------

    customer_name = Column(
        String(100),
        nullable=False,
        index=True,
    )

    # ------------------------------------------------------------------
    # Motor Session
    # ------------------------------------------------------------------

    date = Column(
        Date,
        nullable=False,
        index=True,
    )

    started_at = Column(
        TIMESTAMP,
        nullable=True,
        index=True,
    )

    ended_at = Column(
        TIMESTAMP,
        nullable=True,
        index=True,
    )

    is_open = Column(
        Boolean,
        nullable=False,
        default=True,
        server_default=text("true"),
        index=True,
    )

    # ------------------------------------------------------------------
    # Billing
    # ------------------------------------------------------------------

    run_hours = Column(
        Numeric(10, 2),
        nullable=False,
        default=0,
        server_default=text("0"),
    )

    price_per_hour = Column(
        Numeric(10, 2),
        nullable=False,
        default=0,
        server_default=text("0"),
    )

    total_bill = Column(
        Numeric(10, 2),
        nullable=False,
        default=0,
        server_default=text("0"),
    )

    cash_received = Column(
        Numeric(10, 2),
        nullable=False,
        default=0,
        server_default=text("0"),
    )

    balance = Column(
        Numeric(10, 2),
        nullable=False,
        default=0,
        server_default=text("0"),
    )

    advance_amount = Column(
        Numeric(10, 2),
        nullable=False,
        default=0,
        server_default=text("0"),
    )

    is_cleared = Column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false"),
        index=True,
    )

    # ------------------------------------------------------------------
    # Timestamps
    # ------------------------------------------------------------------

    created_at = Column(
        TIMESTAMP,
        nullable=False,
        server_default=text("now()"),
    )

    updated_at = Column(
        TIMESTAMP,
        nullable=True,
        onupdate=text("now()"),
    )

    # ------------------------------------------------------------------
    # Relationships
    # ------------------------------------------------------------------

    owner = relationship(
        "User",
        back_populates="khata_entries",
    )

    device = relationship(
        "Device",
        back_populates="khata_entries",
        primaryjoin="foreign(KhataEntry.device_id) == Device.device_uid",
        viewonly=True,
    )

    motor_log = relationship(
        "MotorLog",
        back_populates="khata_entries",
    )

    # ------------------------------------------------------------------
    # Debug
    # ------------------------------------------------------------------

    def __repr__(self):
        return (
            f"<KhataEntry "
            f"id={self.id} "
            f"user_id={self.user_id} "
            f"device_id={self.device_id} "
            f"customer={self.customer_name} "
            f"open={self.is_open} "
            f"total={self.total_bill} "
            f"balance={self.balance} "
            f"cleared={self.is_cleared}>"
        )