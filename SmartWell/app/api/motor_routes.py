from typing import Optional, List
from uuid import UUID
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.schemas.motor_schema import (
    MotorStartRequest,
    MotorStopRequest,
    MotorLogResponse,
    VFDResetRequest,
    VFDReferenceFrequencyRequest,
    VFDCommandResponse,
)
from app.schemas.motor_timer_schema import MotorTimerCreate, MotorTimerResponse
from app.services.motor_service import MotorService
from app.repositories.motor_repo import MotorRepository

router = APIRouter(tags=["Motor, VFD & Command Tracking"])


# ==========================================
# 1. PRIMARY MOTOR CONTROL (/motor/...)
# ==========================================

@router.post("/motor/{device_id}/start", response_model=MotorLogResponse, status_code=status.HTTP_200_OK)
def start_motor(
    device_id: str,
    req: MotorStartRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Reserves a customer session, runs safety preflight, and emits an ON MQTT command.
    """
    return MotorService.start_motor(db, device_id, req)


@router.post("/motor/{device_id}/stop", response_model=MotorLogResponse, status_code=status.HTTP_200_OK)
def stop_motor(
    device_id: str,
    req: Optional[MotorStopRequest] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Emits an OFF MQTT command and completes the active running session.
    """
    return MotorService.stop_motor(db, device_id)


@router.get("/motor/{device_id}/logs", response_model=List[MotorLogResponse])
def get_motor_logs(
    device_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Fetches historical motor activity logs for a device.
    """
    return MotorRepository.get_recent_sessions(db, device_id, limit=100)


@router.delete("/motor/{device_id}/logs")
def clear_motor_logs(
    device_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Bulk clears motor activity logs for a specific device.
    """
    deleted_count = MotorRepository.clear_logs_by_device(db, device_id)
    return {
        "detail": "Motor logs cleared successfully",
        "device_id": device_id,
        "deleted_count": deleted_count,
    }


@router.get("/motor/running/{device_id}", response_model=Optional[MotorLogResponse])
def get_running_motor(
    device_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Returns the currently active/running motor session, or null if stopped.
    """
    return MotorRepository.get_running_session(db, device_id)


@router.delete("/motor/logs/{log_id}")
def delete_single_motor_log(
    log_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Deletes a single motor log record by UUID.
    """
    MotorRepository.delete_log_by_id(db, log_id)
    return {
        "detail": "Motor log deleted successfully",
        "log_id": str(log_id),
    }


# ==========================================
# 2. VFD HARDWARE COMMANDS (/vfd/...)
# ==========================================

@router.post("/vfd/{device_id}/reset", response_model=VFDCommandResponse)
def reset_vfd(
    device_id: str,
    payload: VFDResetRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Triggers a VFD hardware reset command via MQTT (requires confirm: true).
    """
    return MotorService.reset_vfd(db, device_id, payload)


@router.post("/vfd/{device_id}/reference-frequency", response_model=VFDCommandResponse)
def set_vfd_reference_frequency(
    device_id: str,
    payload: VFDReferenceFrequencyRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Sets the desired VFD operational reference frequency (0.0 - 50.0 Hz).
    """
    return MotorService.set_reference_frequency(db, device_id, payload)


# ==========================================
# 3. COMMAND STATUS & SESSIONS (/commands/...)
# ==========================================

@router.get("/commands/{device_id}/status")
def get_command_status(
    device_id: str,
    command_id: Optional[UUID] = Query(None, description="Exact command UUID to poll"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Polls execution status and correlation confirmation for a specific command UUID.
    """
    return MotorService.get_command_status(db, device_id, command_id)


@router.get("/commands/{device_id}/sessions")
def get_customer_sessions(
    device_id: str,
    limit: int = Query(5, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Returns recent customer operational session evidence rows (recommended limit=5).
    """
    sessions = MotorRepository.get_recent_sessions(db, device_id, limit=limit)
    return {
        "sessions": sessions,
        "unresolved_events": 0,
    }


@router.get("/commands/{device_id}/events")
def get_motor_events(
    device_id: str,
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Returns stored hardware event evidence rows.
    """
    events = MotorRepository.get_events(db, device_id, limit=limit)
    return events


# ==========================================
# 4. MOTOR TIMERS (/motor-timer/...)
# ==========================================

@router.post("/motor-timer/start")
def start_motor_timer(
    payload: MotorTimerCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Starts a timed motor run session with automatic expiration.
    """
    return MotorService.start_timer(db, payload)


@router.post("/motor-timer/stop/{device_id}")
def stop_motor_timer(
    device_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Immediately stops a timed motor run.
    """
    return MotorService.stop_timer(db, device_id)


@router.get("/motor-timer/status/{device_id}")
def get_motor_timer_status(
    device_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Checks if a motor timer is actively running for the given device.
    """
    return MotorService.get_timer_status(db, device_id)