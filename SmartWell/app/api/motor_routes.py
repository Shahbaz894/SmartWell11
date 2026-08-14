from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.exceptions import AppException
from app.db.session import get_db
from app.schemas.motor_schema import MotorStartRequest, MotorStopRequest, MotorLogResponse
from app.services.motor_service import MotorService

router = APIRouter(prefix="/motor", tags=["Motor"])


def _raise_http_error(exc: AppException):
    raise HTTPException(
        status_code=getattr(exc, "status_code", 500),
        detail=getattr(exc, "detail", str(exc)),
    )


@router.post(
    "/{device_id}/start",
    response_model=MotorLogResponse,
    status_code=status.HTTP_200_OK,
)
def start_motor(device_id: str, payload: MotorStartRequest, db: Session = Depends(get_db)):
    try:
        return MotorService(db).start_motor(
            device_id=device_id,
            trigger_type=payload.trigger_type,
            customer_name=payload.customer_name,
        )
    except AppException as exc:
        _raise_http_error(exc)
    except Exception as exc:
        raise HTTPException(500, f"Unexpected motor start error: {type(exc).__name__}: {exc}")


@router.post(
    "/{device_id}/stop",
    response_model=MotorLogResponse,
    status_code=status.HTTP_200_OK,
)
def stop_motor(device_id: str, payload: MotorStopRequest, db: Session = Depends(get_db)):
    try:
        log = MotorService(db).stop_motor(
            device_id=device_id,
            customer_name=payload.customer_name,
        )
        if log is None:
            # Keep response shape valid when hardware must be forced OFF but no
            # database session existed. id=0 is a sentinel, not a DB row.
            from datetime import datetime
            now = datetime.utcnow()
            return {
                "id": 0,
                "device_id": device_id,
                "start_time": now,
                "end_time": now,
                "duration_minutes": 0,
                "trigger_type": "app",
                "customer_name": payload.customer_name or "Mobile App",
                "status": "OFF",
            }
        return log
    except AppException as exc:
        _raise_http_error(exc)
    except Exception as exc:
        raise HTTPException(500, f"Unexpected motor stop error: {type(exc).__name__}: {exc}")


@router.get("/{device_id}/logs", response_model=List[MotorLogResponse])
def get_motor_logs(device_id: str, db: Session = Depends(get_db)):
    try:
        return MotorService(db).get_motor_logs(device_id)
    except AppException as exc:
        _raise_http_error(exc)


@router.get("/running/{device_id}", response_model=Optional[MotorLogResponse])
def get_running_motor(device_id: str, db: Session = Depends(get_db)):
    try:
        return MotorService(db).get_running_log(device_id)
    except AppException as exc:
        _raise_http_error(exc)


@router.delete("/logs/{log_id}")
def delete_motor_log(log_id: str, db: Session = Depends(get_db)):
    try:
        MotorService(db).delete_motor_log(log_id)
        return {"detail": "Motor log deleted successfully", "log_id": log_id}
    except AppException as exc:
        _raise_http_error(exc)


@router.delete("/{device_id}/logs")
def clear_motor_logs(device_id: str, db: Session = Depends(get_db)):
    try:
        count = MotorService(db).clear_motor_logs(device_id)
        return {"detail": "Motor logs cleared successfully", "device_id": device_id, "deleted_count": count}
    except AppException as exc:
        _raise_http_error(exc)
