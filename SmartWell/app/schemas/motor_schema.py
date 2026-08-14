from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_validator

from app.schemas.enums import TriggerType


class MotorStartRequest(BaseModel):
    # Mobile/app start is the default.
    # Legacy client values are normalized so older Flutter builds
    # sending "mobile", "manual" or "timer" are still accepted.
    trigger_type: TriggerType = TriggerType.app
    customer_name: Optional[str] = None

    @field_validator("trigger_type", mode="before")
    @classmethod
    def normalize_trigger_type(cls, value):
        if value is None or value == "":
            return TriggerType.app

        if isinstance(value, str):
            aliases = {
                "mobile": "app",
                "manual": "app",
                "timer": "time",
            }

            value = aliases.get(
                value.strip().lower(),
                value.strip().lower(),
            )

        return value


class MotorStopRequest(BaseModel):
    customer_name: Optional[str] = None


class MotorLogResponse(BaseModel):
    # PostgreSQL motor_logs.id is UUID
    id: UUID

    # Public device identifier, e.g. ESP32_001_TW.
    device_id: str

    start_time: datetime
    end_time: Optional[datetime] = None
    duration_minutes: Optional[int] = None

    trigger_type: TriggerType

    customer_name: Optional[str] = None
    status: Optional[str] = None
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)