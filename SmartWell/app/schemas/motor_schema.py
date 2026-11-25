from typing import Optional, Literal
from datetime import datetime
from pydantic import BaseModel, Field
from uuid import UUID

class MotorStartRequest(BaseModel):
    trigger_type: Literal["physical", "schedule", "app", "time"] = Field(default="app")
    customer_name: Optional[str] = None

class MotorStopRequest(BaseModel):
    customer_name: Optional[str] = None

class MotorLogResponse(BaseModel):
    id: UUID
    device_id: str
    session_id: Optional[UUID] = None
    command_id: Optional[UUID] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    duration_minutes: Optional[int] = None
    trigger_type: str
    customer_name: Optional[str] = None
    status: Optional[str] = None
    needs_review: bool = False
    review_reason: Optional[str] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class VFDResetRequest(BaseModel):
    confirm: bool = Field(..., description="Must be true to allow VFD reset")

class VFDReferenceFrequencyRequest(BaseModel):
    reference_frequency: float = Field(..., ge=0.0, le=50.0)

class VFDCommandResponse(BaseModel):
    command_id: str
    message: str
    device_id: str
    command: str
    device_uid: Optional[str] = None
    reference_frequency: Optional[float] = None