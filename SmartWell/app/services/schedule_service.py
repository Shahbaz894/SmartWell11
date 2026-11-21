import uuid
from datetime import datetime, time
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.exceptions import AppException, NotFoundException
from app.core.logger import logger
from app.models.device import Device
from app.models.schedule import Schedule
from app.repositories.schedule_repo import ScheduleRepository
from app.schemas.schedule_schema import ScheduleCreate
from app.services.motor_service import MotorService


class ScheduleService:
    """
    Schedule service.

    Schedule -> MotorService -> MQTTService -> ESP32

    Schedule ON:
        trigger_type = "schedule"

    Schedule OFF:
        trigger_type = "schedule"

    MQTT topic:
        tubewell/{device_uid}/motor
    """

    def __init__(self, db: Session):
        self.db = db
        self.repo = ScheduleRepository(db)
        self.motor_service = MotorService(db)

    # =========================================================
    # DEVICE
    # =========================================================

    def _get_device(self, device_id: str) -> Device:
        """
        Resolve device using either:
        - device_uid: ESP32_001_TW
        - internal UUID
        """

        device = (
            self.db.query(Device)
            .filter(Device.device_uid == str(device_id))
            .first()
        )

        if device:
            return device

        try:
            parsed_id = UUID(str(device_id))
        except (ValueError, TypeError, AttributeError):
            parsed_id = None

        if parsed_id is not None:
            device = (
                self.db.query(Device)
                .filter(Device.id == parsed_id)
                .first()
            )

        if not device:
            logger.error(
                "SCHEDULE DEVICE NOT FOUND | device_id=%s",
                device_id,
            )

            raise AppException(
                status_code=404,
                detail=f"Device '{device_id}' not found",
            )

        return device

    # =========================================================
    # CREATE / UPDATE
    # =========================================================

    def create_schedule(
        self,
        device_id: str,
        schedule_in: ScheduleCreate,
    ) -> Schedule:

        try:
            device = self._get_device(device_id)

            device_uid = str(device.device_uid)
            internal_id = str(device.id)

            logger.info(
                "SCHEDULE SAVE | input=%s | uuid=%s | uid=%s | type=%s",
                device_id,
                internal_id,
                device_uid,
                schedule_in.schedule_type,
            )

            existing = self.repo.get_by_device_id(
                internal_id
            )

            if existing:

                existing.schedule_type = schedule_in.schedule_type
                existing.pattern = schedule_in.pattern
                existing.schedule_name = schedule_in.schedule_name
                existing.is_active = True

                saved = self.repo.update(existing)

                logger.info(
                    "SCHEDULE UPDATED | id=%s | device=%s",
                    saved.id,
                    device_uid,
                )

            else:

                schedule = Schedule(
                    id=str(uuid.uuid4()),
                    device_id=internal_id,
                    schedule_type=schedule_in.schedule_type,
                    pattern=schedule_in.pattern,
                    schedule_name=schedule_in.schedule_name,
                    is_active=True,
                )

                saved = self.repo.create(schedule)

                logger.info(
                    "SCHEDULE CREATED | id=%s | device=%s",
                    saved.id,
                    device_uid,
                )

            self.db.commit()
            self.db.refresh(saved)

            return saved

        except AppException:
            self.db.rollback()
            raise

        except SQLAlchemyError as exc:
            self.db.rollback()

            error = (
                str(exc.orig)
                if getattr(exc, "orig", None)
                else str(exc)
            )

            logger.error(
                "SCHEDULE DB ERROR | device=%s | %s",
                device_id,
                error,
                exc_info=True,
            )

            raise AppException(
                status_code=500,
                detail=f"Database error while creating schedule: {error}",
            )

        except Exception as exc:
            self.db.rollback()

            logger.error(
                "SCHEDULE CREATE ERROR | device=%s | %s: %s",
                device_id,
                type(exc).__name__,
                exc,
                exc_info=True,
            )

            raise AppException(
                status_code=500,
                detail=(
                    "Unexpected error while creating schedule: "
                    f"{type(exc).__name__}: {exc}"
                ),
            )

    # =========================================================
    # GET
    # =========================================================

    def get_schedule(self, device_id: str) -> Schedule:

        try:
            device = self._get_device(device_id)

            schedule = self.repo.get_by_device_id(
                str(device.id)
            )

            if not schedule:
                raise AppException(
                    status_code=404,
                    detail=f"No schedule found for device '{device_id}'",
                )

            return schedule

        except AppException:
            raise

        except Exception as exc:

            logger.error(
                "SCHEDULE GET ERROR | device=%s | %s",
                device_id,
                exc,
                exc_info=True,
            )

            raise AppException(
                status_code=500,
                detail=(
                    f"Failed to fetch schedule: "
                    f"{type(exc).__name__}: {exc}"
                ),
            )

    # =========================================================
    # DELETE
    # =========================================================

    def delete_schedule(self, device_id: str) -> None:

        try:
            device = self._get_device(device_id)

            self.repo.delete_by_device_id(
                str(device.id)
            )

            self.db.commit()

            logger.info(
                "SCHEDULE DELETED | device=%s",
                device.device_uid,
            )

        except (AppException, NotFoundException):
            self.db.rollback()
            raise

        except Exception as exc:

            self.db.rollback()

            logger.error(
                "SCHEDULE DELETE ERROR | device=%s | %s",
                device_id,
                exc,
                exc_info=True,
            )

            raise AppException(
                status_code=500,
                detail=(
                    f"Failed to delete schedule: "
                    f"{type(exc).__name__}: {exc}"
                ),
            )

    # =========================================================
    # BACKGROUND CHECKER
    # =========================================================

    def check_and_run(self) -> None:
        """
        Check all active schedules.

        If current time is inside a slot:
            ON with trigger_type=schedule

        If current time is outside the slot:
            OFF only if the current running motor
            was started by schedule.
        """

        try:

            schedules = (
                self.db.query(Schedule)
                .filter(Schedule.is_active.is_(True))
                .all()
            )

            logger.info(
                "SCHEDULE CHECK | count=%s",
                len(schedules),
            )

            for schedule in schedules:

                try:

                    # -------------------------------------------------
                    # Resolve device FIRST
                    # -------------------------------------------------

                    device = self._get_device(
                        str(schedule.device_id)
                    )

                    device_uid = str(
                        device.device_uid
                    )

                    # -------------------------------------------------
                    # Current schedule time
                    # -------------------------------------------------

                    pattern = schedule.pattern or {}

                    now_dt = self._get_now_for_pattern(
                        pattern
                    )

                    now_time = now_dt.time().replace(
                        second=0,
                        microsecond=0,
                    )

                    slots = self._extract_today_slots(
                        schedule=schedule,
                        now_dt=now_dt,
                    )

                    should_run = self._should_run_now(
                        slots=slots,
                        now_time=now_time,
                    )

                    # -------------------------------------------------
                    # Motor state
                    # -------------------------------------------------

                    running_log = (
                        self.motor_service.get_running_log(
                            device_uid
                        )
                    )

                    is_running = running_log is not None

                    current_trigger = (
                        getattr(
                            running_log,
                            "trigger_type",
                            None,
                        )
                        if running_log
                        else None
                    )

                    logger.info(
                        "SCHEDULE CHECKED | "
                        "schedule=%s | "
                        "device=%s | "
                        "time=%s | "
                        "should_run=%s | "
                        "running=%s | "
                        "trigger=%s",
                        schedule.id,
                        device_uid,
                        now_dt.isoformat(),
                        should_run,
                        is_running,
                        current_trigger,
                    )

                    # =================================================
                    # SCHEDULE ON
                    # =================================================

                    if should_run and not is_running:

                        logger.info(
                            "SCHEDULE STARTING MOTOR | device=%s",
                            device_uid,
                        )

                        self.motor_service.start_motor(
                            device_id=device_uid,
                            trigger_type="schedule",
                            customer_name="Schedule",
                        )

                        logger.info(
                            "SCHEDULE MOTOR ON | "
                            "device=%s | trigger=schedule",
                            device_uid,
                        )

                    # =================================================
                    # SCHEDULE OFF
                    # =================================================

                    elif (
                        not should_run
                        and is_running
                        and current_trigger == "schedule"
                    ):

                        logger.info(
                            "SCHEDULE STOPPING MOTOR | device=%s",
                            device_uid,
                        )

                        self.motor_service.stop_motor(
                            device_id=device_uid,
                            customer_name="Schedule",
                            # Natural schedule-window end is NOT a user
                            # master OFF. Keep the saved schedule for the
                            # next configured slot/day.
                            clear_automation=False,
                        )

                        logger.info(
                            "SCHEDULE MOTOR OFF | "
                            "device=%s | trigger=schedule",
                            device_uid,
                        )

                except AppException as exc:

                    logger.error(
                        "SCHEDULE EXECUTION ERROR | "
                        "schedule=%s | device=%s | detail=%s",
                        getattr(schedule, "id", None),
                        getattr(schedule, "device_id", None),
                        getattr(
                            exc,
                            "detail",
                            str(exc),
                        ),
                        exc_info=True,
                    )

                except Exception as exc:

                    logger.error(
                        "SCHEDULE EXECUTION EXCEPTION | "
                        "schedule=%s | device=%s | %s: %s",
                        getattr(schedule, "id", None),
                        getattr(schedule, "device_id", None),
                        type(exc).__name__,
                        exc,
                        exc_info=True,
                    )

        except Exception as exc:

            logger.error(
                "SCHEDULE CRON ERROR | %s: %s",
                type(exc).__name__,
                exc,
                exc_info=True,
            )

    # =========================================================
    # TIMEZONE
    # =========================================================

    def _get_now_for_pattern(
        self,
        pattern: dict[str, Any],
    ) -> datetime:

        timezone_name = "Asia/Karachi"

        if isinstance(pattern, dict):
            timezone_name = (
                pattern.get("timezone")
                or timezone_name
            )

        try:
            return datetime.now(
                ZoneInfo(timezone_name)
            )

        except Exception:

            logger.warning(
                "INVALID TIMEZONE | %s | "
                "using Asia/Karachi",
                timezone_name,
                exc_info=True,
            )

            return datetime.now(
                ZoneInfo("Asia/Karachi")
            )

    # =========================================================
    # EXTRACT TODAY'S SLOTS
    # =========================================================

    def _extract_today_slots(
        self,
        schedule: Schedule,
        now_dt: datetime,
    ) -> list[dict[str, Any]]:

        pattern = schedule.pattern or {}

        if not isinstance(pattern, dict):

            logger.error(
                "INVALID SCHEDULE PATTERN | schedule=%s",
                schedule.id,
            )

            return []

        if pattern.get("enabled") is False:
            return []

        schedule_type = (
            schedule.schedule_type
            or pattern.get("type")
        )

        schedule_type = str(
            schedule_type or ""
        ).lower().strip()

        today_name = (
            now_dt.strftime("%A").lower()
        )

        today_day_number = now_dt.day

        # ---------------------------------------------------------
        # DAILY
        # ---------------------------------------------------------

        if schedule_type == "daily":

            start_time = (
                pattern.get("start_time")
                or pattern.get("start")
            )

            end_time = (
                pattern.get("end_time")
                or pattern.get("end")
            )

            if not start_time or not end_time:
                return []

            return [
                {
                    "start_time": start_time,
                    "end_time": end_time,
                }
            ]

        # ---------------------------------------------------------
        # WEEKLY
        # ---------------------------------------------------------

        if schedule_type == "weekly":

            days = pattern.get("days", [])

            if not isinstance(days, list):
                return []

            for day_config in days:

                if not isinstance(
                    day_config,
                    dict,
                ):
                    continue

                day_name = str(
                    day_config.get("day", "")
                ).lower().strip()

                if day_name != today_name:
                    continue

                if day_config.get(
                    "enabled"
                ) is False:
                    return []

                slots = day_config.get(
                    "slots",
                    [],
                )

                return (
                    slots
                    if isinstance(slots, list)
                    else []
                )

            return []

        # ---------------------------------------------------------
        # MONTHLY
        # ---------------------------------------------------------

        if schedule_type == "monthly":

            days = pattern.get(
                "days",
                [],
            )

            slots = pattern.get(
                "slots",
                [],
            )

            if today_day_number in days:

                return (
                    slots
                    if isinstance(slots, list)
                    else []
                )

            return []

        # ---------------------------------------------------------
        # MONTHLY CUSTOM
        # ---------------------------------------------------------

        if schedule_type == "monthly_custom":

            days = pattern.get(
                "days",
                {},
            )

            if not isinstance(days, dict):
                return []

            slots = days.get(
                str(today_day_number),
                [],
            )

            return (
                slots
                if isinstance(slots, list)
                else []
            )

        logger.warning(
            "UNKNOWN SCHEDULE TYPE | schedule=%s | type=%s",
            schedule.id,
            schedule_type,
        )

        return []

    # =========================================================
    # CHECK SLOT
    # =========================================================

    def _parse_time(
        self,
        value: Any,
    ) -> time | None:

        if value is None:
            return None

        try:

            value_string = str(
                value
            ).strip()

            # HH:MM
            if len(value_string) == 5:
                return time.fromisoformat(
                    value_string
                )

            # HH:MM:SS
            return time.fromisoformat(
                value_string
            )

        except (
            ValueError,
            TypeError,
        ):

            return None

    def _should_run_now(
        self,
        slots: list[dict[str, Any]],
        now_time: time,
    ) -> bool:

        for slot in slots:

            if not isinstance(
                slot,
                dict,
            ):
                continue

            start_value = (
                slot.get("start_time")
                or slot.get("start")
            )

            end_value = (
                slot.get("end_time")
                or slot.get("end")
            )

            start = self._parse_time(
                start_value
            )

            end = self._parse_time(
                end_value
            )

            if start is None or end is None:

                logger.error(
                    "INVALID SCHEDULE SLOT | %s",
                    slot,
                )

                continue

            # -----------------------------------------------------
            # Normal schedule
            # 09:00 -> 12:00
            # -----------------------------------------------------

            if start < end:

                if start <= now_time < end:
                    return True

            # -----------------------------------------------------
            # Overnight schedule
            # 22:00 -> 02:00
            # -----------------------------------------------------

            elif start > end:

                if (
                    now_time >= start
                    or now_time < end
                ):
                    return True

            # -----------------------------------------------------
            # start == end
            #
            # Treat as invalid/zero duration,
            # NOT 24 hours.
            # -----------------------------------------------------

            else:

                logger.warning(
                    "ZERO DURATION SCHEDULE SLOT | %s",
                    slot,
                )

        return False