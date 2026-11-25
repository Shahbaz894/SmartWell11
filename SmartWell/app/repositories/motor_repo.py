from typing import Optional, List, Tuple
from uuid import UUID
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from app.models.motor_log import MotorLog, ResolutionAuditLog
from app.models.vfd_command_log import VFDCommandLog

class MotorRepository:

    @staticmethod
    def get_log_by_id(db: Session, log_id: UUID) -> Optional[MotorLog]:
        return db.query(MotorLog).filter(MotorLog.id == log_id).first()

    @staticmethod
    def create_start_session(db: Session, device_uid: str, customer_name: str, trigger_type: str, command_id: UUID) -> MotorLog:
        log = MotorLog(
            device_id=device_uid,
            session_id=command_id,
            command_id=command_id,
            customer_name=customer_name,
            trigger_type=trigger_type,
            status="PENDING_START",
            needs_review=False
        )
        db.add(log)
        db.commit()
        db.refresh(log)
        return log

    @staticmethod
    def get_running_session(db: Session, device_uid: str) -> Optional[MotorLog]:
        return db.query(MotorLog).filter(
            MotorLog.device_id == device_uid,
            MotorLog.status.in_(["PENDING_START", "ON"])
        ).first()

    @staticmethod
    def get_recent_sessions(db: Session, device_uid: str, limit: int = 5) -> List[MotorLog]:
        return db.query(MotorLog).filter(
            MotorLog.device_id == device_uid
        ).order_by(MotorLog.created_at.desc()).limit(limit).all()

    @staticmethod
    def create_command_log(db: Session, command_id: UUID, device_uid: str, command: str, ref_freq: Optional[float] = None) -> VFDCommandLog:
        cmd = VFDCommandLog(
            command_id=command_id,
            device_uid=device_uid,
            command=command,
            reference_frequency=ref_freq,
            status="PUBLISHED",
            published_at=datetime.now(timezone.utc)
        )
        db.add(cmd)
        db.commit()
        db.refresh(cmd)
        return cmd

    @staticmethod
    def get_command_status(db: Session, device_uid: str, command_id: Optional[UUID] = None) -> Optional[VFDCommandLog]:
        if command_id:
            return db.query(VFDCommandLog).filter(VFDCommandLog.command_id == command_id).first()
        return db.query(VFDCommandLog).filter(VFDCommandLog.device_uid == device_uid).order_by(VFDCommandLog.requested_at.desc()).first()