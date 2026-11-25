from typing import Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field
from uuid import UUID

class ScheduleCreate(BaseModel):
    device_id: str = Field(..., min_length=1)  # device_uid
    schedule_type: str = Field(..., min_length=1)
    pattern: Dict[str, Any] = Field(...)
    schedule_name: Optional[str] = None

class ScheduleResponse(BaseModel):
    id: UUID
    device_id: str
    schedule_type: str
    pattern: Dict[str, Any]
    is_active: bool
    schedule_name: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True