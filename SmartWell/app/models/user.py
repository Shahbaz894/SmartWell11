import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Boolean, DateTime, true
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.db.base_class import Base

class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column("password_hash", String(255), nullable=False)
    role = Column(String(20), default="user", nullable=False)  # 'user', 'admin', 'super_admin'
    is_active = Column(Boolean, default=True, server_default=true(), nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    # Relationships
    owned_devices = relationship("Device", back_populates="owner", foreign_keys="Device.user_id")
    assigned_devices = relationship("Device", secondary="device_assignments", back_populates="assigned_users")