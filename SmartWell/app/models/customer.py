import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Numeric, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from app.db.base_class import Base

class Customer(Base):
    __tablename__ = "customers"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    device_uid = Column(String(100), ForeignKey("devices.device_uid", ondelete="CASCADE"), nullable=False)
    customer_key = Column(String(100), index=True, nullable=False)  # Lowercase trimmed key
    customer_name = Column(String(100), nullable=False)             # Display label
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    __table_args__ = (UniqueConstraint("device_uid", "customer_key", name="uix_device_customer_key"),)

class CustomerRate(Base):
    __tablename__ = "customer_rates"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    device_uid = Column(String(100), ForeignKey("devices.device_uid", ondelete="CASCADE"), nullable=False)
    customer_key = Column(String(100), index=True, nullable=False)
    price_per_hour = Column(Numeric(10, 2), nullable=False, default=150.00)
    version = Column(UUID(as_uuid=True), default=uuid.uuid4, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    __table_args__ = (UniqueConstraint("device_uid", "customer_key", name="uix_device_customer_rate"),)