import uuid
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
from uuid import UUID
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from app.models.motor_log import MotorLog
from app.models.vfd_command_log import VFDCommandLog

# Standard VFD Status Code Mappings
STATUS_MAP = {
    0: ("STOPPED", "Motor is stopped"),
    1: ("RUNNING_FORWARD", "Motor is running forward"),
    2: ("RUNNING_REVERSE", "Motor is running in reverse"),
    3: ("STANDBY", "Motor is in standby / ready state"),
    4: ("FAULT", "VFD fault detected"),
    5: ("ACCELERATING", "Motor is accelerating"),
    6: ("DECELERATING", "Motor is decelerating"),
}

# Standard VFD Fault Code Mappings
FAULT_MAP = {
    0: ("NO_FAULT", "System operating normally"),
    1: ("OVERCURRENT", "VFD Overcurrent fault detected"),
    2: ("OVERVOLTAGE", "DC Bus Overvoltage fault detected"),
    3: ("UNDERVOLTAGE", "DC Bus Undervoltage fault detected"),
    4: ("OVERHEAT", "VFD Heat sink temperature exceeded limit"),
    5: ("OVERLOAD", "Motor overload protection tripped"),
    6: ("PHASE_LOSS", "Input/output phase loss fault"),
}

class MotorTelemetryService:

    @staticmethod
    def _resolve_status_info(status_code: int) -> tuple[str, str]:
        """Resolves status_code to (status_name, status_description)."""
        return STATUS_MAP.get(status_code, ("UNKNOWN", f"Unknown status code ({status_code})"))

    @staticmethod
    def _resolve_fault_info(fault: int, fault_code: int) -> tuple[str, str, bool]:
        """Resolves fault flags to (fault_name, fault_description, has_fault)."""
        has_fault = bool(fault != 0 or fault_code != 0)
        if not has_fault:
            return "NO_FAULT", "System operating normally", False
        name, desc = FAULT_MAP.get(fault_code, ("GENERIC_FAULT", f"Hardware fault code {fault_code}"))
        return name, desc, True

    def create_telemetry_from_mqtt(self, db: Session, device_uid: str, payload: Dict[str, Any]) -> Any:
        """
        Parses raw MQTT JSON payload and persists telemetry to PostgreSQL.
        """
        from app.models.telemetry import MotorTelemetry  # Import model

        status_code = int(payload.get("status_code", 0))
        fault = int(payload.get("fault", 0))
        fault_code = int(payload.get("fault_code", 0))

        status_name, status_desc = self._resolve_status_info(status_code)
        fault_name, fault_desc, has_fault = self._resolve_fault_info(fault, fault_code)

        # Parse epoch timestamp or default to current UTC time
        raw_ts = payload.get("timestamp")
        if raw_ts and isinstance(raw_ts, (int, float)) and raw_ts > 0:
            created_at = datetime.fromtimestamp(raw_ts, tz=timezone.utc)
        else:
            created_at = datetime.now(timezone.utc)

        telemetry = MotorTelemetry(
            id=uuid.uuid4(),
            device_id=device_uid,
            timestamp=int(raw_ts or created_at.timestamp()),
            freq=float(payload.get("freq", 0.0)),
            current=float(payload.get("current", 0.0)),
            voltage=float(payload.get("voltage", 0.0)),
            dcbus=float(payload.get("dcbus", 0.0)),
            power=float(payload.get("power", 0.0)),
            energy_in=float(payload.get("energy_in", 0.0)),
            reference_freq=float(payload.get("reference_freq", 25.0)),
            motor_speed=float(payload.get("motor_speed", 0.0)),
            power_percent=float(payload.get("power_percent", 0.0)),
            torque_percent=float(payload.get("torque_percent", 0.0)),
            fault=fault,
            fault_code=fault_code,
            status_code=status_code,
            is_live=int(payload.get("is_live", 1)),
            trigger_type=payload.get("trigger_type", "physical"),
            # Derived descriptors
            status_name=status_name,
            status_description=status_desc,
            fault_name=fault_name,
            fault_description=fault_desc,
            has_fault=has_fault,
            # Context & Protocol Correlation fields
            session_id=payload.get("session_id"),
            operation_id=payload.get("operation_id"),
            run_source=payload.get("run_source"),
            uptime_ms=payload.get("uptime_ms"),
            clock_valid=payload.get("clock_valid"),
            automation_state=payload.get("automation_state"),
            session_recovery_protocol=payload.get("session_recovery_protocol"),
            created_at=created_at
        )

        db.add(telemetry)
        db.commit()
        db.refresh(telemetry)
        return telemetry

    def get_latest_telemetry(self, db: Session, device_uid: str) -> Optional[Dict[str, Any]]:
        """
        Returns the latest telemetry record for a device with optional RAM sidecar fields (vfd, firmwareversion).
        """
        from app.models.telemetry import MotorTelemetry

        record = db.query(MotorTelemetry).filter(
            MotorTelemetry.device_id == device_uid
        ).order_by(MotorTelemetry.created_at.desc()).first()

        if not record:
            return None

        # Build response dict matching LiveMotorTelemetryResponse schema
        data = {col.name: getattr(record, col.name) for col in record.__table__.columns}

        # Attach transient live-only RAM metadata
        data["vfd"] = 1 if record.voltage > 100 else 0
        data["firmwareversion"] = "1.1.2"
        return data

    def get_telemetry_history(self, db: Session, device_uid: str, limit: int = 100) -> List[Any]:
        """
        Returns historical telemetry records for a device.
        """
        from app.models.telemetry import MotorTelemetry

        return db.query(MotorTelemetry).filter(
            MotorTelemetry.device_id == device_uid
        ).order_by(MotorTelemetry.created_at.desc()).limit(limit).all()

    def delete_telemetry_record(self, db: Session, telemetry_id: UUID) -> Dict[str, Any]:
        """
        Deletes a single telemetry record by UUID.
        """
        from app.models.telemetry import MotorTelemetry

        record = db.query(MotorTelemetry).filter(MotorTelemetry.id == telemetry_id).first()
        if not record:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Telemetry record {telemetry_id} not found"
            )

        db.delete(record)
        db.commit()
        return {
            "detail": "Telemetry deleted successfully",
            "telemetry_id": str(telemetry_id)
        }
