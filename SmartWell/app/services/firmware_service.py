import hashlib
import re
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID, uuid4

from fastapi import HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.device import Device
from app.models.vfd_command_log import FirmwareRelease

MAX_FIRMWARE_BYTES = 1_310_720
VERSION = re.compile(r"[0-9]+\.[0-9]+\.[0-9]+")


class FirmwareService:
    @staticmethod
    def upload_draft(
        db: Session, version: str, model: str, target_scope: str, target_uids: list[str],
        notes: str, user_id: UUID, file: UploadFile,
    ) -> FirmwareRelease:
        content = file.file.read(MAX_FIRMWARE_BYTES + 1)
        if len(content) > MAX_FIRMWARE_BYTES:
            raise HTTPException(413, "Firmware exceeds 1,310,720 bytes")
        if len(content) < 24 or content[0] != 0xE9:
            raise HTTPException(422, "Expected an ESP32 application image")

        version_match = select(FirmwareRelease.id).where(
            FirmwareRelease.model == model, FirmwareRelease.version == version,
        )
        if db.scalar(version_match) is not None:
            raise HTTPException(409, "Version already exists for this model")

        release_id = uuid4()
        directory = Path(settings.FIRMWARE_DIR).resolve()
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"{release_id}.bin"
        release = FirmwareRelease(
            id=release_id, version=version, model=model, size_bytes=len(content),
            sha256=hashlib.sha256(content).hexdigest(), notes=notes, target_scope=target_scope,
            target_uids=target_uids, state="draft", uploaded_by=user_id, file_path=str(path),
        )
        try:
            path.write_bytes(content)
            db.add(release)
            db.commit()
        except IntegrityError as exc:
            db.rollback()
            path.unlink(missing_ok=True)
            if db.scalar(version_match) is not None:
                raise HTTPException(409, "Version already exists for this model") from exc
            raise
        except Exception:
            db.rollback()
            path.unlink(missing_ok=True)
            raise
        return release

    @staticmethod
    def binary_path(release: FirmwareRelease) -> Path:
        path = Path(release.file_path).resolve()
        if not path.is_relative_to(Path(settings.FIRMWARE_DIR).resolve()) or not path.is_file():
            raise HTTPException(404, "Firmware binary unavailable")
        return path

    @staticmethod
    def transition(db: Session, release_id: UUID, state: str) -> FirmwareRelease:
        release = db.get(FirmwareRelease, release_id, with_for_update=True)
        if release is None:
            raise HTTPException(404, "Release not found")
        if release.state == state:
            return release
        if state == "published":
            if release.state != "draft":
                raise HTTPException(409, "Only draft releases can be published")
            path = FirmwareService.binary_path(release)
            content = path.read_bytes()
            if len(content) != release.size_bytes or hashlib.sha256(content).hexdigest() != release.sha256:
                raise HTTPException(409, "Firmware binary integrity check failed")
            release.published_at = datetime.now(timezone.utc)
        release.state = state
        db.commit()
        return release

    @staticmethod
    def check_ota(db: Session, device_uid: str, current_version: str, model: str) -> FirmwareRelease | None:
        if len(current_version) > 20 or not VERSION.fullmatch(current_version):
            raise HTTPException(422, "version must have three numeric components")
        if db.scalar(select(Device.id).where(Device.device_uid == device_uid)) is None:
            return None
        installed = tuple(map(int, current_version.split(".")))
        releases = db.scalars(select(FirmwareRelease).where(
            FirmwareRelease.model == model, FirmwareRelease.state == "published",
        ).order_by(FirmwareRelease.published_at.desc(), FirmwareRelease.id))
        candidates = []
        for release in releases:
            if release.target_scope != "all_model" and device_uid not in release.target_uids:
                continue
            if not VERSION.fullmatch(release.version):
                continue
            version = tuple(map(int, release.version.split(".")))
            if version > installed:
                candidates.append((version, release))
        return max(candidates, key=lambda item: item[0])[1] if candidates else None
