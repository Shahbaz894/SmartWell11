from typing import Optional, List
from uuid import UUID
from sqlalchemy.orm import Session
from app.models.vfd_command_log import FirmwareRelease

class FirmwareRepository:

    @staticmethod
    def get_by_id(db: Session, release_id: UUID) -> Optional[FirmwareRelease]:
        return db.query(FirmwareRelease).filter(FirmwareRelease.id == release_id).first()

    @staticmethod
    def get_all(db: Session) -> List[FirmwareRelease]:
        return db.query(FirmwareRelease).order_by(FirmwareRelease.created_at.desc()).all()

    @staticmethod
    def get_latest_published(db: Session, model: str) -> Optional[FirmwareRelease]:
        return db.query(FirmwareRelease).filter(
            FirmwareRelease.model == model,
            FirmwareRelease.state == "published"
        ).order_by(FirmwareRelease.created_at.desc()).first()