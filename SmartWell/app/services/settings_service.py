from datetime import datetime, timezone
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from app.models.motor_parameter import DeviceSettings, DeviceAutomation
from app.schemas.settings_schema import SettingsPatch, AutomationSave

class SettingsService:

    @staticmethod
    def update_settings(db: Session, device_uid: str, patch: SettingsPatch) -> DeviceSettings:
        settings = db.query(DeviceSettings).filter(DeviceSettings.device_uid == device_uid).first()
        if not settings:
            settings = DeviceSettings(device_uid=device_uid)
            db.add(settings)

        # Optimistic concurrency revision check
        if patch.expected_revisions:
            if "direction" in patch.expected_revisions and patch.expected_revisions["direction"] != settings.direction_revision:
                raise HTTPException(status_code=409, detail="Direction revision conflict")
            if "frequency" in patch.expected_revisions and patch.expected_revisions["frequency"] != settings.frequency_revision:
                raise HTTPException(status_code=409, detail="Frequency revision conflict")

        if patch.direction is not None:
            settings.desired_direction = patch.direction
            settings.direction_revision += 1
            settings.direction_state = "pending"

        if patch.reference_frequency is not None:
            settings.desired_frequency = patch.reference_frequency
            settings.frequency_revision += 1
            settings.frequency_state = "pending"

        settings.last_snapshot_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(settings)
        return settings

    @staticmethod
    def save_automation(db: Session, device_uid: str, payload: AutomationSave) -> DeviceAutomation:
        automation = db.query(DeviceAutomation).filter(DeviceAutomation.device_uid == device_uid).first()
        if not automation:
            automation = DeviceAutomation(device_uid=device_uid)
            db.add(automation)

        if payload.expected_revision != automation.revision:
            raise HTTPException(status_code=409, detail="Automation revision conflict")

        auto_data = payload.automation_settings
        automation.auto_restart_enabled = auto_data.auto_restart_enabled
        automation.max_attempts = auto_data.max_attempts
        automation.retry_delay_seconds = auto_data.retry_delay_seconds
        automation.offline_stop_enabled = auto_data.offline_stop_enabled
        automation.offline_timeout_seconds = auto_data.offline_timeout_seconds

        automation.revision += 1
        automation.state = "pending"
        db.commit()
        db.refresh(automation)
        return automation