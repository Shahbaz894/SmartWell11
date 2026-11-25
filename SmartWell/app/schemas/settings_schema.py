from typing import Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field, conint

class SettingsPatch(BaseModel):
    direction: Optional[str] = Field(None, description="FORWARD or REVERSE")
    reference_frequency: Optional[float] = Field(None, ge=0.0, le=50.0)
    expected_revisions: Optional[Dict[str, int]] = Field(
        None, description="Keys: 'direction', 'frequency' (e.g. {'direction': 1, 'frequency': 1})"
    )

    class Config:
        extra = "forbid"

class SettingsViewResponse(BaseModel):
    device_uid: str
    desired: Dict[str, Any]
    confirmed: Dict[str, Any]
    sync_requested: bool
    discovery_complete: bool
    unsupported: bool
    last_snapshot_at: Optional[datetime] = None
    fields: Dict[str, Any]
    requested_commands: Optional[Dict[str, Optional[str]]] = None

class AutomationSettingsDict(BaseModel):
    auto_restart_enabled: bool = Field(default=False)
    max_attempts: conint(ge=1, le=10) = Field(default=3)  # type: ignore
    retry_delay_seconds: conint(ge=5, le=3600) = Field(default=30)  # type: ignore
    offline_stop_enabled: bool = Field(default=False)
    offline_timeout_seconds: conint(ge=10, le=86400) = Field(default=60)  # type: ignore

class AutomationSave(BaseModel):
    automation_settings: AutomationSettingsDict
    expected_revision: int = Field(..., description="Integer revision sequence")

    class Config:
        extra = "forbid"

class AutomationSettingsViewResponse(BaseModel):
    device_uid: str
    desired: AutomationSettingsDict
    confirmed: AutomationSettingsDict
    revision: int
    state: str
    error: Optional[str] = None
    settings_saved: bool
    settings_valid: bool
    run_source: Optional[str] = None
    queried: bool
    supported: bool
    online: bool
    automation_state: Optional[Dict[str, Any]] = None
    pending_command_id: Optional[str] = None
    query_command_id: Optional[str] = None
    confirmed_at: Optional[datetime] = None
    last_snapshot_at: Optional[datetime] = None