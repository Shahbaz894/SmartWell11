import uuid
from typing import Dict, Any, Optional
from fastapi import HTTPException
from sqlalchemy.orm import Session
from app.repositories.motor_repo import MotorRepository
from app.repositories.device_repo import DeviceRepository
from app.schemas.motor_schema import MotorStartRequest

class MotorService:

    @staticmethod
    def start_motor(db: Session, device_uid: str, req: MotorStartRequest) -> Dict[str, Any]:
        device = DeviceRepository.get_by_uid(db, device_uid)
        if not device:
            raise HTTPException(status_code=404, detail="Device not found")

        if not req.customer_name or not req.customer_name.strip():
            raise HTTPException(status_code=400, detail="A non-empty customer_name is required to start motor")

        command_id = uuid.uuid4()
        log = MotorRepository.create_start_session(db, device_uid, req.customer_name.strip(), req.trigger_type, command_id)
        MotorRepository.create_command_log(db, command_id, device_uid, "ON")

        return {
            "id": log.id,
            "device_id": device_uid,
            "session_id": log.session_id,
            "command_id": command_id,
            "start_time": None,
            "end_time": None,
            "duration_minutes": None,
            "trigger_type": req.trigger_type,
            "customer_name": req.customer_name,
            "status": "PENDING_START",
            "created_at": log.created_at,
            "needs_review": False,
            "review_reason": None
        }

    @staticmethod
    def stop_motor(db: Session, device_uid: str) -> Dict[str, Any]:
        device = DeviceRepository.get_by_uid(db, device_uid)
        if not device:
            raise HTTPException(status_code=404, detail="Device not found")

        running = MotorRepository.get_running_session(db, device_uid)
        command_id = uuid.uuid4()

        if running:
            running.status = "COMPLETED"
            db.commit()

        MotorRepository.create_command_log(db, command_id, device_uid, "OFF")

        return {
            "id": running.id if running else uuid.uuid4(),
            "device_id": device_uid,
            "session_id": running.session_id if running else None,
            "command_id": command_id,
            "start_time": running.start_time if running else None,
            "end_time": None,
            "duration_minutes": None,
            "trigger_type": "app",
            "customer_name": running.customer_name if running else None,
            "status": "ON",
            "created_at": running.created_at if running else None,
            "needs_review": False,
            "review_reason": None
        }