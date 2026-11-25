import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Numeric, Boolean, DateTime, ForeignKey, JSON
from sqlalchemy.dialects.postgresql import UUID
from app.db.base_class import Base

class KhataEntry(Base):
    __tablename__ = "khata_entries"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    device_id = Column(String(100), nullable=False)  # device_uid
    customer_name = Column(String(100), nullable=False)
    motor_log_id = Column(UUID(as_uuid=True), nullable=True)
    date = Column(String(10), nullable=False)  # YYYY-MM-DD
    run_hours = Column(Numeric(10, 2), default=0.0, nullable=False)
    price_per_hour = Column(Numeric(10, 2), default=150.0, nullable=False)
    total_bill = Column(Numeric(10, 2), default=0.0, nullable=False)
    cash_received = Column(Numeric(10, 2), default=0.0, nullable=False)
    balance = Column(Numeric(10, 2), default=0.0, nullable=False)
    advance_amount = Column(Numeric(10, 2), default=0.0, nullable=False)
    is_cleared = Column(Boolean, default=False, nullable=False)
    payment_status = Column(String(20), default="unpaid", nullable=False)  # 'paid', 'partial', 'unpaid'
    started_at = Column(DateTime(timezone=True), nullable=True)
    ended_at = Column(DateTime(timezone=True), nullable=True)
    is_open = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

class KhataPaymentReceipt(Base):
    __tablename__ = "khata_payment_receipts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)  # receipt_id
    request_id = Column(UUID(as_uuid=True), unique=True, index=True, nullable=False)  # Idempotency token
    device_uid = Column(String(100), nullable=False)
    customer_name = Column(String(100), nullable=False)
    from_date = Column(String(10), nullable=False)
    to_date = Column(String(10), nullable=False)
    amount = Column(Numeric(10, 2), nullable=False)
    revision = Column(String(64), nullable=False)
    allocations = Column(JSON, nullable=False)  # List of {"id": session_id, "amount": str}
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))