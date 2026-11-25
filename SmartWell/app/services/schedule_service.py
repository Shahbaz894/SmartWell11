from typing import Dict, Any
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from app.repositories.schedule_repo import ScheduleRepository
from app.schemas.schedule_schema import ScheduleCreate

class ScheduleService:

    @staticmethod
    def save_schedule(db: Session, payload: ScheduleCreate) -> Any:
        """
        Creates or updates a schedule for a device using device_uid.
        """
        return ScheduleRepository.create_or_update(db, payload)

    @staticmethod
    def get_schedule(db: Session, device_uid: str) -> Any:
        """
        Retrieves the active schedule for a given device_uid.
        """
        sched = ScheduleRepository.get_by_device(db, device_uid)
        if not sched:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No active schedule found for device {device_uid}"
            )
        return sched

    @staticmethod
    def delete_schedule(db: Session, device_uid: str) -> Dict[str, Any]:
        """
        Deletes the schedule associated with a device_uid.
        """
        sched = ScheduleRepository.get_by_device(db, device_uid)
        if not sched:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No active schedule found for device {device_uid}"
            )

        ScheduleRepository.delete_by_device(db, device_uid)
        return {
            "detail": "Schedule deleted successfully",
            "device_id": device_uid
        }
