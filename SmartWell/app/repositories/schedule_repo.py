from typing import Optional, List
from uuid import UUID
from sqlalchemy.orm import Session
from app.models.schedule import Schedule
from app.schemas.schedule_schema import ScheduleCreate

class ScheduleRepository:

    @staticmethod
    def get_by_id(db: Session, schedule_id: UUID) -> Optional[Schedule]:
        return db.query(Schedule).filter(Schedule.id == schedule_id).first()

    @staticmethod
    def get_by_device(db: Session, device_uid: str) -> Optional[Schedule]:
        return db.query(Schedule).filter(Schedule.device_id == device_uid).first()

    @staticmethod
    def create_or_update(db: Session, schedule_in: ScheduleCreate) -> Schedule:
        existing = db.query(Schedule).filter(Schedule.device_id == schedule_in.device_id).first()
        if existing:
            existing.schedule_type = schedule_in.schedule_type
            existing.pattern = schedule_in.pattern
            existing.schedule_name = schedule_in.schedule_name
            existing.is_active = True
            db.commit()
            db.refresh(existing)
            return existing

        schedule = Schedule(
            device_id=schedule_in.device_id,
            schedule_type=schedule_in.schedule_type,
            pattern=schedule_in.pattern,
            schedule_name=schedule_in.schedule_name,
            is_active=True
        )
        db.add(schedule)
        db.commit()
        db.refresh(schedule)
        return schedule

    @staticmethod
    def delete_by_device(db: Session, device_uid: str) -> bool:
        db.query(Schedule).filter(Schedule.device_id == device_uid).delete()
        db.commit()
        return True