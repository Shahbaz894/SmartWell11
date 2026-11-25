from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field
from uuid import UUID

class MotorTimerCreate(BaseModel):
    device_id: str = Field(..., min_length=1)
    start_time: datetime
    stop_time: datetime
    duration_minutes: int
    customer_name: Optional[str] = None

class MotorTimerResponse(BaseModel):
    id: UUID
    device_id: str
    start_time: datetime
    stop_time: datetime
    duration_minutes: int
    is_running: bool
    customer_name: Optional[str] = None
    command_id: Optional[UUID] = None

    class Config:
        from_attributes = True