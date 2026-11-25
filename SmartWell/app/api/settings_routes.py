from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.schemas.settings_schema import (
    SettingsPatch,
    SettingsViewResponse,
    AutomationSave,
    AutomationSettingsViewResponse,
)
from app.services.settings_service import SettingsService

router = APIRouter(tags=["Motor Settings & Automation"])


@router.patch("/motor-settings/{device_uid}")
def patch_motor_settings(
    device_uid: str,
    patch: SettingsPatch,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    updated = SettingsService.update_settings(db, device_uid, patch)
    return {
        "device_uid": device_uid,
        "desired": {
            "direction": updated.desired_direction,
            "reference_frequency": updated.desired_frequency,
        },
        "confirmed": {
            "direction": updated.confirmed_direction,
            "reference_frequency": updated.confirmed_frequency,
        },
        "revisions": {
            "direction": updated.direction_revision,
            "frequency": updated.frequency_revision,
        },
    }


@router.patch("/motor-settings/{device_uid}/automation")
def save_automation_settings(
    device_uid: str,
    payload: AutomationSave,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    auto = SettingsService.save_automation(db, device_uid, payload)
    return {
        "device_uid": device_uid,
        "revision": auto.revision,
        "state": auto.state,
        "automation_settings": {
            "auto_restart_enabled": auto.auto_restart_enabled,
            "max_attempts": auto.max_attempts,
            "retry_delay_seconds": auto.retry_delay_seconds,
            "offline_stop_enabled": auto.offline_stop_enabled,
            "offline_timeout_seconds": auto.offline_timeout_seconds,
        },
    }