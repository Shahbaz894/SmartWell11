UUID
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.schemas.resolution_schema import (
    ResolutionRequest,
    ResolutionPreviewResponse,
    ResolutionResponse,
)
from app.services.resolution_service import ResolutionService

router = APIRouter(prefix="/records", tags=["Session Resolution & Audit"])


@router.post("/{kind}/{target_id}/resolution/preview", response_model=ResolutionPreviewResponse)
def preview_session_resolution(
    kind: str,
    target_id: UUID,
    payload: ResolutionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return ResolutionService.preview_resolution(db, target_id, payload)


@router.post("/{kind}/{target_id}/resolution", response_model=ResolutionResponse)
def execute_session_resolution(
    kind: str,
    target_id: UUID,
    payload: ResolutionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return ResolutionService.execute_resolution(db, target_id, current_user.id, payload)