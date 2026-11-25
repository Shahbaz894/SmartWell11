from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.security import get_current_user, require_admin
from app.models.user import User
from app.schemas.device_schema import (
    DeviceCreate,
    DeviceUpdate,
    DeviceResponse,
    LiveDeviceResponse,
    GrantAssignment,
    TransferOwnership,
)
from app.services.device_service import DeviceService

router = APIRouter(tags=["Devices & Sharing"])


# ==========================================
# 1. USER & LEGACY DEVICE ENDPOINTS (/devices/)
# ==========================================

@router.post("/devices/", response_model=DeviceResponse, status_code=status.HTTP_201_CREATED)
def create_device(
    device_in: DeviceCreate,
    user_id: UUID = Query(..., description="Owner user UUID"),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    Registers a new well device associated with the specified owner UUID.
    """
    return DeviceService.register_device(db, user_id, device_in)


@router.get("/devices/", response_model=List[LiveDeviceResponse])
def get_user_devices(
    user_id: Optional[UUID] = Query(None, description="User UUID whose owned/assigned devices are listed"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Gets owned and assigned devices for a user account.
    """
    target_user_id = user_id or current_user.id
    if target_user_id != current_user.id:
        require_admin(current_user)
    return DeviceService.list_accessible_devices(db, target_user_id)


@router.put("/devices/{device_id}", response_model=DeviceResponse)
def update_device(
    device_id: UUID,
    device_in: DeviceUpdate,
    user_id: UUID = Query(..., description="Owner user UUID"),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    Updates device metadata (device_name, sim_number, location, reference_freq) by internal database UUID.
    """
    return DeviceService.update_device(db, device_id, user_id, device_in)


@router.delete("/devices/{device_id}")
def delete_device(
    device_id: UUID,
    user_id: UUID = Query(..., description="Owner user UUID"),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    Deletes a device and all associated device-scoped historical records.
    """
    return DeviceService.delete_device(db, device_id, user_id)


# ==========================================
# 2. ACCESSIBLE DEVICES (/access/devices)
# ==========================================

@router.get("/access/devices", response_model=List[LiveDeviceResponse])
def list_accessible_devices(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Lists owned and assigned devices with live RAM status flags (vfd, firmwareversion).
    """
    return DeviceService.list_accessible_devices(db, current_user.id)


# ==========================================
# 3. ADMIN ASSIGNMENT & SHARING (/admin/devices/...)
# ==========================================

@router.get("/admin/devices/{device_id}/assignments")
def get_device_assignments(
    device_id: UUID,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    Returns owner_id and list of current user assignments for a device.
    """
    return DeviceService.get_assignments(db, device_id)


@router.put("/admin/devices/{device_id}/assignments/{user_id}")
def grant_or_update_assignment(
    device_id: UUID,
    user_id: UUID,
    payload: GrantAssignment,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    Grants or updates control permissions (can_control) for a assigned user.
    """
    return DeviceService.grant_assignment(db, device_id, user_id, payload.can_control)


@router.delete("/admin/devices/{device_id}/assignments/{user_id}")
def revoke_assignment(
    device_id: UUID,
    user_id: UUID,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    Revokes user access assignment from a device.
    """
    return DeviceService.revoke_assignment(db, device_id, user_id)


@router.post("/admin/devices/{device_id}/transfer")
def transfer_ownership(
    device_id: UUID,
    payload: TransferOwnership,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    Transfers device ownership to a new user account (requires confirm: true).
    """
    return DeviceService.transfer_ownership(db, device_id, payload)