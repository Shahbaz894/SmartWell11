

from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.core.exceptions import AppException
from app.core.logger import logger
from app.models.device import Device
from app.models.motor_parameter import MotorTelemetry
from app.models.motor_timer import MotorTimer
from app.repositories.motor_telemetry_repo import MotorTelemetryRepository
from app.schemas.motor_telemetry_schema import MotorTelemetryCreate
from app.schemas.enums import TriggerType
from app.services.motor_service import MotorService


class MotorTelemetryService:
    def __init__(self):
        self.repo = MotorTelemetryRepository()

    def _get_device_by_uid_or_id(self, db: Session, device_id: str) -> Optional[Device]:
        try:
            device_key = str(device_id).strip()

            # First: match public/custom device UID, example ESP32_001_TW
            device = db.query(Device).filter(Device.device_uid == device_key).first()
            if device:
                return device

            # Second: fallback match internal UUID
            try:
                device = db.query(Device).filter(Device.id == UUID(device_key)).first()
                if device:
                    return device
            except (ValueError, TypeError):
                pass

            return None

        except Exception as exc:
            logger.error(
                "Critical error resolving device %s: %s",
                device_id,
                str(exc),
                exc_info=True,
            )
            raise AppException(
                status_code=500,
                detail=f"Database error while resolving device '{device_id}'",
            )

    def _to_int_or_default(self, value: Any, default: int) -> int:
        if value is None:
            return default
        if isinstance(value, bool):
            return 1 if value else 0
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    def _to_float_or_default(self, value: Any, default: float = 0.0) -> float:
        if value is None:
            return default
        try:
            val = float(value)
            return val if val >= 0 else default
        except (TypeError, ValueError):
            return default

    def _normalize_mqtt_payload(self, payload: dict) -> dict:
        normalized = dict(payload or {})
        now_ts = int(datetime.now(timezone.utc).timestamp())

        normalized["timestamp"] = self._to_int_or_default(
            normalized.get("timestamp"),
            now_ts,
        )

        normalized["freq"] = self._to_float_or_default(normalized.get("freq"))
        normalized["current"] = self._to_float_or_default(normalized.get("current"))
        normalized["voltage"] = self._to_float_or_default(normalized.get("voltage"))
        normalized["dcbus"] = self._to_float_or_default(normalized.get("dcbus"))
        normalized["power"] = self._to_float_or_default(normalized.get("power"))
        normalized["energy_in"] = self._to_float_or_default(normalized.get("energy_in"))

        normalized["reference_freq"] = self._to_float_or_default(
            normalized.get("reference_freq")
        )
        normalized["motor_speed"] = self._to_float_or_default(
            normalized.get("motor_speed")
        )
        normalized["power_percent"] = self._to_float_or_default(
            normalized.get("power_percent")
        )
        normalized["torque_percent"] = self._to_float_or_default(
            normalized.get("torque_percent")
        )

        normalized["fault"] = self._to_int_or_default(normalized.get("fault"), 0)
        normalized["fault_code"] = self._to_int_or_default(
            normalized.get("fault_code"),
            0,
        )
        normalized["status_code"] = self._to_int_or_default(
            normalized.get("status_code"),
            0,
        )
        normalized["is_live"] = self._to_int_or_default(normalized.get("is_live"), 0)

        return normalized

    def _determine_trigger_type(
        self,
        db: Session,
        device_uid: str,
        current_trigger: Optional[TriggerType] = None,
    ) -> TriggerType:
        if isinstance(current_trigger, TriggerType):
            return current_trigger

        if isinstance(current_trigger, str):
            try:
                return TriggerType(current_trigger.lower())
            except ValueError:
                pass

        # IMPORTANT: MotorTimer.device_id stores Device.device_uid, not Device.id
        active_timer = (
            db.query(MotorTimer)
            .filter(
                MotorTimer.device_id == str(device_uid),
                MotorTimer.is_running.is_(True),
            )
            .first()
        )

        return TriggerType.time if active_timer else TriggerType.physical

    def _build_telemetry_model(
        self,
        device: Device,
        data: MotorTelemetryCreate,
    ) -> MotorTelemetry:
        trigger_value = data.trigger_type

        if isinstance(trigger_value, TriggerType):
            trigger_value = trigger_value.value

        return MotorTelemetry(
            # IMPORTANT:
            # Store public device UID, example ESP32_001_TW.
            # Do NOT store internal Device.id UUID here.
            device_id=device.device_uid,

            trigger_type=trigger_value,
            timestamp=data.timestamp,
            freq=data.freq,
            current=data.current,
            voltage=data.voltage,
            dcbus=data.dcbus,
            power=data.power,
            energy_in=data.energy_in,
            fault=data.fault,
            fault_code=data.fault_code,
            status_code=data.status_code,
            reference_freq=data.reference_freq,
            motor_speed=data.motor_speed,
            power_percent=data.power_percent,
            torque_percent=data.torque_percent,
            is_live=data.is_live,
        )

    def _save_telemetry(
        self,
        db: Session,
        device: Device,
        data: MotorTelemetryCreate,
    ) -> MotorTelemetry:
        telemetry = self._build_telemetry_model(device, data)
        created = self.repo.create(db, telemetry)

        db.commit()
        db.refresh(created)

        return created

    def create_telemetry_from_mqtt(
        self,
        db: Session,
        device_uid: str,
        payload: dict,
    ) -> MotorTelemetry:
        try:
            device = self._get_device_by_uid_or_id(db, device_uid)

            if not device:
                raise AppException(
                    status_code=404,
                    detail=f"Device UID '{device_uid}' not found.",
                )

            # Keep the previous physical VFD state so we only react to
            # a REAL ON -> OFF transition. Repeated OFF telemetry must
            # never delete a newly-created schedule while the motor is idle.
            previous_telemetry = self.repo.get_latest(
                db,
                device.device_uid,
            )

            normalized_payload = self._normalize_mqtt_payload(payload)

            raw_trigger = payload.get("trigger_type") if payload else None
            incoming_trigger = None

            try:
                if raw_trigger:
                    incoming_trigger = TriggerType(str(raw_trigger).lower())
            except ValueError:
                logger.warning("Invalid trigger_type received: %s", raw_trigger)

            trigger = self._determine_trigger_type(
                db,
                device.device_uid,
                current_trigger=incoming_trigger,
            )

            normalized_payload["trigger_type"] = trigger

            try:
                data = MotorTelemetryCreate(**normalized_payload)
            except ValidationError as exc:
                raise AppException(
                    status_code=400,
                    detail={
                        "message": "Invalid payload",
                        "errors": exc.errors(),
                    },
                )

            created = self._save_telemetry(db, device, data)

            # -----------------------------------------------------
            # PHYSICAL OFF = MASTER STOP
            # -----------------------------------------------------
            # Only trigger this when:
            #   previous VFD state was RUNNING (1/2)
            #   new VFD state is OFF/STANDBY (3; also tolerate 0/5)
            #   ESP32 explicitly reports trigger_type=physical
            #
            # This prevents repeated standby telemetry from clearing
            # schedules/timers while the motor is already OFF.
            previous_status = self._to_int_or_default(
                getattr(previous_telemetry, "status_code", None),
                0,
            )

            current_status = self._to_int_or_default(
                data.status_code,
                0,
            )

            raw_trigger_value = (
                str(raw_trigger).strip().lower()
                if raw_trigger is not None
                else ""
            )

            physical_off_transition = (
                previous_status in (1, 2)
                and current_status in (0, 3, 5)
                and raw_trigger_value == "physical"
            )

            if physical_off_transition:
                try:
                    MotorService(db).handle_physical_off(
                        device.device_uid,
                    )

                    logger.info(
                        "PHYSICAL MASTER OFF | device=%s | "
                        "schedule cleared | timer cancelled",
                        device.device_uid,
                    )

                except Exception as cleanup_exc:
                    # Telemetry itself was already stored successfully.
                    # Do not lose live telemetry if automation cleanup fails.
                    logger.error(
                        "PHYSICAL MASTER OFF CLEANUP FAILED | "
                        "device=%s | error=%s",
                        device.device_uid,
                        cleanup_exc,
                        exc_info=True,
                    )

            return created

        except AppException:
            db.rollback()
            raise

        except Exception as exc:
            db.rollback()
            logger.error(
                "MQTT telemetry create failed: device_uid=%s error=%s",
                device_uid,
                str(exc),
                exc_info=True,
            )
            raise AppException(
                status_code=500,
                detail={"message": str(exc)},
            )

    def create_telemetry(
        self,
        db: Session,
        device_id: str,
        data: MotorTelemetryCreate,
    ) -> MotorTelemetry:
        try:
            device = self._get_device_by_uid_or_id(db, device_id)

            if not device:
                raise AppException(
                    status_code=404,
                    detail=f"Device '{device_id}' not found.",
                )

            normalized_payload = self._normalize_mqtt_payload(data.model_dump())

            trigger = self._determine_trigger_type(
                db,
                device.device_uid,
                current_trigger=data.trigger_type,
            )

            normalized_payload["trigger_type"] = trigger

            try:
                normalized_data = MotorTelemetryCreate(**normalized_payload)
            except ValidationError as exc:
                raise AppException(
                    status_code=400,
                    detail={
                        "message": "Invalid payload",
                        "errors": exc.errors(),
                    },
                )

            return self._save_telemetry(db, device, normalized_data)

        except AppException:
            db.rollback()
            raise

        except Exception as exc:
            db.rollback()
            logger.error(
                "HTTP telemetry create failed: device_id=%s error=%s",
                device_id,
                str(exc),
                exc_info=True,
            )
            raise AppException(
                status_code=500,
                detail={"message": str(exc)},
            )

    def get_device_telemetry(self, db: Session, device_id: str):
        try:
            device = self._get_device_by_uid_or_id(db, device_id)

            if not device:
                return []

            # IMPORTANT: query by device_uid, not internal UUID
            return self.repo.get_by_device(db, device.device_uid)

        except Exception as exc:
            raise AppException(status_code=500, detail=str(exc))

    def get_latest_live(self, db: Session, device_id: str):
        try:
            device = self._get_device_by_uid_or_id(db, device_id)

            if not device:
                return None

            # IMPORTANT: query by device_uid, not internal UUID
            return self.repo.get_latest(db, device.device_uid)

        except Exception as exc:
            raise AppException(status_code=500, detail=str(exc))

    def delete_telemetry(self, db: Session, telemetry_id: UUID):
        try:
            deleted = self.repo.delete(db, str(telemetry_id))
            db.commit()
            return deleted

        except Exception as exc:
            db.rollback()
            raise AppException(status_code=500, detail=str(exc))