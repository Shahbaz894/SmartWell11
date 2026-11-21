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

# MASTER OFF cleanup dependencies.
from app.repositories.motor_timer_repository import MotorTimerRepository
from app.repositories.schedule_repo import ScheduleRepository


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

    # =========================================================
    # MASTER OFF AUTOMATION CLEANUP
    # =========================================================
    def clear_all_automation(self, device_id: str) -> dict:
        """
        Clear BOTH automation sources for one device:

        - stop/cancel any running MotorTimer
        - delete the saved Schedule

        This method does NOT publish a motor OFF command. It is cleanup only.
        It is used by:
        - app/manual OFF through stop_motor(clear_automation=True)
        - physical OFF transition through handle_physical_off()
        - manual timer stop_now()

        Natural schedule end and timer auto-end do NOT call this cleanup.
        """
        try:
            device = self._get_device(device_id)
            device_uid = str(device.device_uid)
            internal_id = str(device.id)

            timer_cleared = False
            schedule_cleared = False

            # -----------------------------------------------------
            # Cancel active timer
            # -----------------------------------------------------
            running_timer = MotorTimerRepository.get_running_timer(
                self.db,
                device_uid,
            )

            if running_timer:
                MotorTimerRepository.stop_timer(
                    self.db,
                    running_timer,
                )
                timer_cleared = True

                logger.info(
                    "MASTER OFF TIMER CLEARED | device=%s",
                    device_uid,
                )

            # -----------------------------------------------------
            # Delete saved schedule
            # -----------------------------------------------------
            schedule_repo = ScheduleRepository(self.db)

            saved_schedule = schedule_repo.get_by_device_id(
                internal_id
            )

            if saved_schedule:
                schedule_repo.delete_by_device_id(
                    internal_id
                )
                schedule_cleared = True

                logger.info(
                    "MASTER OFF SCHEDULE CLEARED | device=%s",
                    device_uid,
                )

            # A stale pending trigger must not leak into a later run.
            pending_commands.pop(
                device_uid,
                None,
            )

            self.db.commit()

            logger.info(
                "MASTER OFF AUTOMATION CLEARED | "
                "device=%s | timer=%s | schedule=%s",
                device_uid,
                timer_cleared,
                schedule_cleared,
            )

            return {
                "timer_cleared": timer_cleared,
                "schedule_cleared": schedule_cleared,
            }

        except AppException:
            self.db.rollback()
            raise

        except SQLAlchemyError as exc:
            self.db.rollback()
            logger.error(
                "DB error while clearing automation: %s",
                exc,
                exc_info=True,
            )
            raise AppException(
                500,
                f"Database error while clearing automation: {getattr(exc, 'orig', exc)}",
            )

        except Exception as exc:
            self.db.rollback()
            logger.error(
                "Unexpected error while clearing automation: %s",
                exc,
                exc_info=True,
            )
            raise AppException(
                500,
                f"Unexpected automation cleanup error: {type(exc).__name__}: {exc}",
            )

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
        clear_automation: bool = True,
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

            # -----------------------------------------------------
            # APP / MANUAL OFF = MASTER STOP
            # -----------------------------------------------------
            # Default is True so your existing /motor/.../stop endpoint
            # does not need to change.
            #
            # ScheduleService passes clear_automation=False for a normal
            # schedule-window end, so future schedule slots remain saved.
            if clear_automation:
                self.clear_all_automation(
                    device_uid
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

    # =========================================================
    # PHYSICAL OFF = MASTER STOP
    # =========================================================
    def handle_physical_off(
        self,
        device_id: str,
    ) -> MotorLog | None:
        """
        Called ONLY for a confirmed physical VFD ON -> OFF transition.

        The physical switch has already stopped the hardware, therefore
        this method does NOT publish another MQTT OFF command.

        It:
        - closes the current MotorLog if one exists
        - clears running timer
        - deletes saved schedule
        """
        try:
            device = self._get_device(device_id)
            device_uid = str(device.device_uid)

            log = self.repo.get_running_motor(
                device_uid
            )

            updated = None

            if log:
                end_time = datetime.utcnow()
                duration = end_time - log.start_time

                log.end_time = end_time
                log.duration_minutes = max(
                    1,
                    int(duration.total_seconds() / 60),
                )
                log.status = "OFF"

                updated = self.repo.update_log(log)

                logger.info(
                    "PHYSICAL OFF MOTOR LOG CLOSED | "
                    "device=%s log_id=%s",
                    device_uid,
                    updated.id,
                )

            # Physical OFF is authoritative: remove ALL automation.
            self.clear_all_automation(
                device_uid
            )

            logger.info(
                "PHYSICAL MASTER OFF COMPLETE | device=%s",
                device_uid,
            )

            return updated

        except AppException:
            raise

        except SQLAlchemyError as exc:
            self.db.rollback()
            logger.error(
                "DB error during physical master OFF: %s",
                exc,
                exc_info=True,
            )
            raise AppException(
                500,
                f"Database error during physical master OFF: {getattr(exc, 'orig', exc)}",
            )

        except Exception as exc:
            self.db.rollback()
            logger.error(
                "Unexpected physical master OFF error: %s",
                exc,
                exc_info=True,
            )
            raise AppException(
                500,
                f"Unexpected physical master OFF error: {type(exc).__name__}: {exc}",
            )

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
