import asyncio
from datetime import datetime
from sqlalchemy.orm import Session

from app.repositories.motor_timer_repository import MotorTimerRepository
from app.core.logger import logger
from app.core.exceptions import (
    MotorAlreadyRunning,
    MotorNotRunning,
)

from app.services.motor_service import MotorService


class MotorTimerService:

    @staticmethod
    async def start_timer(
        db: Session,
        device_id: str,
        customer_name: str,
        start_time: datetime,
        stop_time: datetime,
    ):
        # ---------------------------------------------------------
        # Validate duration BEFORE starting motor
        # ---------------------------------------------------------
        duration_seconds = (
            stop_time - start_time
        ).total_seconds()

        duration_minutes = int(
            duration_seconds / 60
        )

        if duration_minutes <= 0:
            raise ValueError(
                "Invalid duration: stop_time must be later than start_time"
            )

        # ---------------------------------------------------------
        # Check existing timer
        # ---------------------------------------------------------
        running = MotorTimerRepository.get_running_timer(
            db,
            device_id,
        )

        if running:
            raise MotorAlreadyRunning()

        logger.info(
            "START TIMER => device=%s duration=%s minutes",
            device_id,
            duration_minutes,
        )

        # ---------------------------------------------------------
        # START MOTOR THROUGH MotorService
        #
        # This is important because MotorService:
        # 1. Creates MotorLog
        # 2. Sends MQTT ON
        # 3. Uses trigger_type="time"
        # ---------------------------------------------------------
        motor_service = MotorService(db)

        motor_log = motor_service.start_motor(
            device_id=device_id,
            trigger_type="time",
            customer_name=(
                customer_name.strip()
                if customer_name and customer_name.strip()
                else "Timer"
            ),
        )

        logger.info(
            "TIMER MOTOR STARTED => "
            "device=%s motor_log_id=%s trigger_type=time",
            device_id,
            motor_log.id,
        )

        # ---------------------------------------------------------
        # SAVE TIMER
        # ---------------------------------------------------------
        try:
            timer = MotorTimerRepository.create(
                db=db,
                device_id=device_id,
                customer_name=customer_name,
                start_time=start_time,
                stop_time=stop_time,
                duration_minutes=duration_minutes,
            )

        except Exception:

            # -----------------------------------------------------
            # Timer database save failed.
            #
            # MotorService already created MotorLog and started
            # the motor, so close the motor session as rollback.
            # -----------------------------------------------------
            try:
                motor_service.stop_motor(
                    device_id=device_id,
                    customer_name="Timer",
                    clear_automation=False,
                )

            except Exception:
                logger.exception(
                    "FAILED TO ROLLBACK TIMER MOTOR START => "
                    "device=%s",
                    device_id,
                )

            raise

        # ---------------------------------------------------------
        # AUTO STOP
        # ---------------------------------------------------------
        asyncio.create_task(
            MotorTimerService.auto_stop(
                db=db,
                timer_id=timer.id,
                device_id=device_id,
                duration_minutes=duration_minutes,
            )
        )

        logger.info(
            "TIMER CREATED => "
            "device=%s timer_id=%s motor_log_id=%s duration=%s",
            device_id,
            timer.id,
            motor_log.id,
            duration_minutes,
        )

        return timer

    # =============================================================
    # AUTO STOP
    # =============================================================

    @staticmethod
    async def auto_stop(
        db: Session,
        timer_id: int,
        device_id: str,
        duration_minutes: int,
    ):
        try:

            logger.info(
                "AUTO STOP WAIT => "
                "device=%s duration=%s min",
                device_id,
                duration_minutes,
            )

            await asyncio.sleep(
                duration_minutes * 60
            )

            # -----------------------------------------------------
            # Check timer still exists/running
            # -----------------------------------------------------
            running = MotorTimerRepository.get_running_timer(
                db,
                device_id,
            )

            if not running:
                logger.info(
                    "AUTO STOP SKIPPED => "
                    "no running timer | device=%s",
                    device_id,
                )
                return

            # -----------------------------------------------------
            # STOP MOTOR THROUGH MotorService
            #
            # This:
            # 1. Sends MQTT OFF
            # 2. Finds running MotorLog
            # 3. Sets end_time
            # 4. Calculates duration
            # 5. Sets status=OFF
            # -----------------------------------------------------
            motor_service = MotorService(db)

            motor_log = motor_service.stop_motor(
                device_id=device_id,
                customer_name="Timer",
                clear_automation=False,
            )

            # -----------------------------------------------------
            # Stop timer record
            # -----------------------------------------------------
            MotorTimerRepository.stop_timer(
                db,
                running,
            )

            logger.info(
                "MOTOR AUTO STOPPED => "
                "device=%s timer_id=%s motor_log_id=%s",
                device_id,
                timer_id,
                getattr(motor_log, "id", None),
            )

        except Exception as exc:

            logger.error(
                "AUTO STOP ERROR => "
                "device=%s error=%s",
                device_id,
                exc,
                exc_info=True,
            )

    # =============================================================
    # MANUAL TIMER STOP
    # =============================================================
    @staticmethod
    def stop_now(
    db: Session,
    device_id: str,
):
        # ---------------------------------------------------------
        # Find active timer
        # ---------------------------------------------------------
        timer = MotorTimerRepository.get_running_timer(
            db,
            device_id,
        )

        # ---------------------------------------------------------
        # Stop motor through MotorService
        #
        # This sends MQTT OFF and closes the active MotorLog.
        # ---------------------------------------------------------
        motor_service = MotorService(db)

        motor_log = None

        try:
            motor_log = motor_service.stop_motor(
                device_id=device_id,
                customer_name="Manual Stop",
                clear_automation=False,
            )

        except Exception as exc:
            logger.warning(
                "MOTOR STOP WARNING => "
                "device=%s error=%s",
                device_id,
                exc,
                exc_info=True,
            )

            # If the motor is already stopped, we still want
            # to cancel the active timer.
            #
            # However, if this is a real motor-stop failure,
            # MotorService should ideally distinguish that case
            # from "motor already stopped".

        # ---------------------------------------------------------
        # Stop active timer
        # ---------------------------------------------------------
        if timer:
            MotorTimerRepository.stop_timer(
                db,
                timer,
            )

            logger.info(
                "TIMER STOPPED MANUALLY => "
                "device=%s timer_id=%s",
                device_id,
                timer.id,
            )
        else:
            logger.info(
                "NO ACTIVE TIMER => device=%s",
                device_id,
            )

        # ---------------------------------------------------------
        # MASTER OFF
        #
        # Explicit manual OFF cancels saved automation.
        # ---------------------------------------------------------
        motor_service.clear_all_automation(
            device_id
        )

        logger.info(
            "MASTER MANUAL OFF COMPLETE => "
            "device=%s motor_log_id=%s timer_cancelled=%s",
            device_id,
            getattr(motor_log, "id", None),
            timer is not None,
        )

        return {
            "message": "Motor stopped and timer cancelled",
            "device_id": device_id,
            "timer_cancelled": timer is not None,
            "motor_log_id": getattr(
                motor_log,
                "id",
                None,
            ),
        }