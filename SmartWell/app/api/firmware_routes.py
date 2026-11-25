import json
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, Response, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.security import require_admin
from app.db.session import get_db
from app.models.user import User
from app.models.vfd_command_log import FirmwareRelease
from app.repositories.firmware_repo import FirmwareRepository
from app.schemas.firmware_schema import FirmwareCheckResponse, FirmwareConfirm, FirmwareReleaseResponse
from app.services.firmware_service import FirmwareService

router = APIRouter(tags=["Firmware OTA Management"])
admin = APIRouter(prefix="/api/admin/firmware", dependencies=[Depends(require_admin)])


def release_url(request: Request, release: FirmwareRelease) -> str:
    return str(request.url_for("download_firmware", release_id=str(release.id)))


def release_view(request: Request, release: FirmwareRelease) -> FirmwareReleaseResponse:
    fields = {name: getattr(release, name) for name in FirmwareReleaseResponse.model_fields if name != "url"}
    return FirmwareReleaseResponse(**fields, url=release_url(request, release))


@admin.get("", response_model=list[FirmwareReleaseResponse])
def list_releases(request: Request, db: Session = Depends(get_db)):
    return [release_view(request, item) for item in FirmwareRepository.get_all(db)]


@admin.post("", response_model=FirmwareReleaseResponse, status_code=201)
def upload_firmware_binary(
    request: Request,
    version: str = Form(..., pattern=r"^[0-9]+\.[0-9]+\.[0-9]+$", max_length=20),
    model: str = Form(..., min_length=1, max_length=50),
    target_scope: Literal["selected", "all_model"] = Form(...),
    target_uids: str = Form("[]"),
    notes: str = Form("", max_length=5000),
    build_confirmed: bool = Form(False),
    file: UploadFile = File(...),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    if not build_confirmed:
        raise HTTPException(400, "Confirm that the upload is an application firmware build")
    try:
        uids = json.loads(target_uids)
    except json.JSONDecodeError as exc:
        raise HTTPException(422, "target_uids must be a JSON list") from exc
    if not isinstance(uids, list) or any(
        not isinstance(uid, str) or not uid.strip() or len(uid) > 100 for uid in uids
    ):
        raise HTTPException(422, "target_uids must contain device UIDs")
    if bool(uids) != (target_scope == "selected"):
        raise HTTPException(422, "Provide target UIDs only for selected releases")
    release = FirmwareService.upload_draft(
        db, version, model, target_scope, list(dict.fromkeys(uids)), notes, current_user.id, file
    )
    return release_view(request, release)


@admin.post("/{release_id}/publish", response_model=FirmwareReleaseResponse)
def publish_release(
    request: Request, release_id: UUID, payload: FirmwareConfirm, db: Session = Depends(get_db)
):
    if not payload.confirm:
        raise HTTPException(400, "Publication requires confirmation")
    return release_view(request, FirmwareService.transition(db, release_id, "published"))


@admin.post("/{release_id}/withdraw", response_model=FirmwareReleaseResponse)
def withdraw_release(
    request: Request, release_id: UUID, payload: FirmwareConfirm, db: Session = Depends(get_db)
):
    if not payload.confirm:
        raise HTTPException(400, "Withdrawal requires confirmation")
    return release_view(request, FirmwareService.transition(db, release_id, "withdrawn"))


@router.get("/api/firmware/check", response_model=FirmwareCheckResponse, responses={204: {"description": "No update"}})
def check_firmware_update(request: Request, db: Session = Depends(get_db)):
    params = request.query_params
    for key in ("device_uid", "version", "model"):
        if len(params.getlist(key)) != 1 or not params[key].strip():
            raise HTTPException(422, f"Provide {key} exactly once")
    release = FirmwareService.check_ota(db, params["device_uid"], params["version"], params["model"])
    if release is None:
        return Response(status_code=204)
    return FirmwareCheckResponse(
        version=release.version, model=release.model, url=release_url(request, release),
        size=release.size_bytes, sha256=release.sha256,
    )


@router.get("/firmware/{release_id}/firmware.bin", response_class=FileResponse)
def download_firmware(release_id: UUID, db: Session = Depends(get_db)):
    release = FirmwareRepository.get_by_id(db, release_id)
    if release is None or release.published_at is None:
        raise HTTPException(404, "Published release not found")
    return FileResponse(
        FirmwareService.binary_path(release), media_type="application/octet-stream",
        filename="firmware.bin", headers={"Cache-Control": "public, max-age=31536000, immutable"},
    )


router.include_router(admin)
