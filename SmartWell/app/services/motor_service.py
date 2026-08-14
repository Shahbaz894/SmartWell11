from datetime import datetime
from uuid import UUID

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.exceptions import AppException
from app.core.logger import logger
from app.models.device import Device
from app.models.motor_log import MotorLog
from app.repositories.motor_repo import MotorRepository
from app.services.mqtt_service import MQTTService
from app.core.state import pending_commands


class MotorService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = MotorRepository(db)
        self.mqtt = MQTTService()

    def _get_device(self, device_id: str) -> Device:
        # The public device UID (e.g. ESP32_001_TW) is the canonical identifier.
        device = (
            self.db.query(Device)
            .filter(Device.device_uid == device_id)
            .first()
        )
        if device:
            return device

        # Also accept the internal Device UUID for compatibility with older clients.
        try:
            parsed_uuid = UUID(str(device_id))
        except (ValueError, TypeError, AttributeError):
            parsed_uuid = None

        if parsed_uuid:
            device = (
                self.db.query(Device)
                .filter(Device.id == parsed_uuid)
                .first()
            )

        if not device:
            raise AppException(404, f"Device '{device_id}' not found")
        return device

    @staticmethod
    def _normalize_trigger(trigger_type) -> str:
        value = getattr(trigger_type, "value", trigger_type)
        value = (value or "app").strip().lower()
        # Keep this exactly aligned with TriggerType in schemas/enums.py.
        aliases = {"timer": "time", "mobile": "app", "manual": "app"}
        value = aliases.get(value, value)
        allowed = {"app", "schedule", "time", "physical"}
        if value not in allowed:
            raise AppException(400, "Invalid motor trigger type. Mobile app must use trigger type app.")
        return value

    def start_motor(
        self,
        device_id: str,
        trigger_type: str = "app",
        customer_name: str | None = None,
    ) -> MotorLog:
        try:
            device = self._get_device(device_id)
            device_uid = device.device_uid
            normalized_trigger = self._normalize_trigger(trigger_type)

            customer = (customer_name or "").strip()
            if normalized_trigger == "app" and not customer:
                raise AppException(400, "customer_name is required for app starts")

            running = self.repo.get_running_motor(device_uid)
            if running:
                logger.warning("Motor already running: device_uid=%s log_id=%s", device_uid, running.id)
                return running

            # IMPORTANT: save the DB log first. Previously MQTT ON was sent before
            # the insert, which allowed the physical motor to run while the API
            # returned a log-save error.
            log = MotorLog(
                device_id=device_uid,
                start_time=datetime.utcnow(),
                trigger_type=normalized_trigger,
                customer_name=customer or f"{normalized_trigger.capitalize()} Start",
                status="ON",
            )
            created = self.repo.create_log(log)

            try:
                self.mqtt.publish_command(
                    device_uid=device_uid,
                    payload={
                        "command": "ON",
                        "action": "ON",
                        "device_id": device_uid,
                        "device_uid": device_uid,
                        "trigger_type": normalized_trigger,
                    },
                )
            except Exception:
                # Do not leave a fake running session if MQTT delivery fails.
                self.db.delete(created)
                self.db.commit()
                raise

            logger.info(
                "Motor started: device_uid=%s trigger=%s log_id=%s",
                device_uid, normalized_trigger, created.id,
            )
            return created

        except AppException:
            self.db.rollback()
            raise
        except SQLAlchemyError as exc:
            self.db.rollback()
            logger.error("DB error while starting motor: %s", exc, exc_info=True)
            raise AppException(500, f"Database error: {getattr(exc, 'orig', exc)}")
        except Exception as exc:
            self.db.rollback()
            logger.error("Unexpected error while starting motor: %s", exc, exc_info=True)
            raise AppException(500, f"Unexpected error: {type(exc).__name__}: {exc}")

    def stop_motor(
        self,
        device_id: str,
        customer_name: str | None = None,
    ) -> MotorLog | None:
        try:
            device = self._get_device(device_id)
            device_uid = device.device_uid
            log = self.repo.get_running_motor(device_uid)

            # Always send OFF, even if the DB session is missing.
            self.mqtt.publish_command(
                device_uid=device_uid,
                payload={
                    "command": "OFF",
                    "action": "OFF",
                    "device_id": device_uid,
                    "device_uid": device_uid,
                },
            )

            if not log:
                logger.warning("Stop requested but no running motor log exists: %s", device_uid)
                return None

            end_time = datetime.utcnow()
            duration = end_time - log.start_time
            log.end_time = end_time
            log.duration_minutes = max(1, int(duration.total_seconds() / 60))
            log.status = "OFF"
            if customer_name and customer_name.strip():
                log.customer_name = customer_name.strip()

            updated = self.repo.update_log(log)
            logger.info("Motor stopped: device_uid=%s log_id=%s", device_uid, updated.id)
            return updated

        except AppException:
            raise
        except SQLAlchemyError as exc:
            self.db.rollback()
            logger.error("DB error while stopping motor: %s", exc, exc_info=True)
            raise AppException(500, f"Database error while stopping motor: {getattr(exc, 'orig', exc)}")
        except Exception as exc:
            logger.error("Unexpected error while stopping motor: %s", exc, exc_info=True)
            raise AppException(500, f"Unexpected error: {type(exc).__name__}: {exc}")

    def is_motor_running(self, device_id: str) -> bool:
        device = self._get_device(device_id)
        return self.repo.get_running_motor(device.device_uid) is not None

    def get_running_log(self, device_id: str):
        device = self._get_device(device_id)
        return self.repo.get_running_motor(device.device_uid)

    def get_motor_logs(self, device_id: str):
        try:
            device = self._get_device(device_id)
            return (
                self.db.query(MotorLog)
                .filter(MotorLog.device_id == device.device_uid)
                .order_by(MotorLog.start_time.desc())
                .all()
            )
        except AppException:
            raise
        except SQLAlchemyError as exc:
            self.db.rollback()
            raise AppException(500, f"Database error while fetching motor logs: {getattr(exc, 'orig', exc)}")

    def delete_motor_log(self, log_id: str) -> None:
        try:
            try:
                parsed_log_id = int(log_id)
            except (TypeError, ValueError):
                raise AppException(400, "Invalid motor log id")

            log = self.db.query(MotorLog).filter(MotorLog.id == parsed_log_id).first()
            if not log:
                raise AppException(404, "Motor log not found")
            self.db.delete(log)
            self.db.commit()
        except AppException:
            self.db.rollback()
            raise
        except SQLAlchemyError as exc:
            self.db.rollback()
            raise AppException(500, f"Database error while deleting motor log: {getattr(exc, 'orig', exc)}")

    def clear_motor_logs(self, device_id: str) -> int:
        try:
            device = self._get_device(device_id)
            logs = self.db.query(MotorLog).filter(MotorLog.device_id == device.device_uid).all()
            count = len(logs)
            for log in logs:
                self.db.delete(log)
            self.db.commit()
            return count
        except AppException:
            self.db.rollback()
            raise
        except SQLAlchemyError as exc:
            self.db.rollback()
            raise AppException(500, f"Database error while clearing motor logs: {getattr(exc, 'orig', exc)}")
    def sync_motor_state(
        self,
        device_id: str,
        status_code: int,
    ):
        device = self._get_device(device_id)

        running_log = self.repo.get_running_motor(
            device.device_uid
        )

        active_trigger = pending_commands.pop(
            device.device_uid,
            "physical",
        )

        if status_code == 1 and not running_log:

            self.start_motor(
                device_id=device.device_uid,
                trigger_type=active_trigger,
                customer_name=f"{active_trigger.capitalize()} Start",
            )

        elif status_code == 0 and running_log:

            self.stop_motor(
                device_id=device.device_uid,
            )