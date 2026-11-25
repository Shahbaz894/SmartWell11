from typing import Optional, List, Literal
from datetime import datetime
from pydantic import BaseModel, Field
from uuid import UUID

class DeviceCreate(BaseModel):
    device_name: str = Field(..., min_length=1, max_length=100)
    device_uid: str = Field(..., min_length=1, max_length=100)
    sim_number: Optional[str] = None
    location: Optional[str] = None
    reference_freq: Optional[float] = 25.0

class DeviceUpdate(BaseModel):
    device_name: Optional[str] = None
    sim_number: Optional[str] = None
    location: Optional[str] = None
    reference_freq: Optional[float] = None

class DeviceResponse(BaseModel):
    id: UUID
    user_id: UUID
    device_name: str
    device_uid: str
    sim_number: Optional[str] = None
    location: Optional[str] = None
    reference_freq: Optional[float] = 25.0
    created_at: Optional[datetime] = None
    is_online: bool = False

    class Config:
        from_attributes = True

class LiveDeviceResponse(DeviceResponse):
    is_owner: bool = False
    can_control: bool = False
    vfd: Optional[Literal[1]] = None
    firmwareversion: Optional[str] = None

class GrantAssignment(BaseModel):
    can_control: bool = Field(default=False)

class TransferOwnership(BaseModel):
    new_owner_id: UUID
    confirm: bool = Field(default=False)