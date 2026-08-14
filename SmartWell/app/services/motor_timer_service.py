import asyncio
from datetime import datetime
from sqlalchemy.orm import Session

from app.repositories.motor_timer_repository import MotorTimerRepository
from app.services.mqtt_service import MQTTService
from app.core.logger import logger
from app.core.exceptions import (
    MotorAlreadyRunning,
    MotorNotRunning,
)


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
        # Validate duration BEFORE MQTT
        # ---------------------------------------------------------
        duration_seconds = (
            stop_time - start_time
        ).total_seconds()

        duration_minutes = int(duration_seconds / 60)

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
        # TIMER MUST SEND trigger_type=time
        # ---------------------------------------------------------
        MQTTService.publish_motor_command(
            device_uid=device_id,
            action="ON",
            trigger_type="time",
        )

        logger.info(
            "TIMER MQTT ON SENT => device=%s trigger_type=time",
            device_id,
        )

        # ---------------------------------------------------------
        # Save timer
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
            # If timer DB save fails, stop the motor so we don't
            # leave hardware running without a timer record.
            try:
                MQTTService.publish_motor_command(
                    device_uid=device_id,
                    action="OFF",
                    trigger_type="time",
                )
            except Exception:
                logger.exception(
                    "Failed to rollback TIMER motor ON => device=%s",
                    device_id,
                )

            raise

        # ---------------------------------------------------------
        # Schedule automatic OFF
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
            "TIMER CREATED => device=%s timer_id=%s duration=%s",
            device_id,
            timer.id,
            duration_minutes,
        )

        return timer

    @staticmethod
    async def auto_stop(
        db: Session,
        timer_id: int,
        device_id: str,
        duration_minutes: int,
    ):
        try:
            logger.info(
                "AUTO STOP WAIT => device=%s duration=%s min",
                device_id,
                duration_minutes,
            )

            await asyncio.sleep(duration_minutes * 60)

            running = MotorTimerRepository.get_running_timer(
                db,
                device_id,
            )

            if not running:
                logger.info(
                    "AUTO STOP SKIPPED => no running timer | device=%s",
                    device_id,
                )
                return

            # -----------------------------------------------------
            # TIMER OFF MUST ALSO BE marked as time
            # -----------------------------------------------------
            MQTTService.publish_motor_command(
                device_uid=device_id,
                action="OFF",
                trigger_type="time",
            )

            MotorTimerRepository.stop_timer(
                db,
                running,
            )

            logger.info(
                "MOTOR AUTO STOPPED => device=%s trigger_type=time",
                device_id,
            )

        except Exception as exc:
            logger.error(
                "AUTO STOP ERROR => device=%s error=%s",
                device_id,
                exc,
                exc_info=True,
            )

    @staticmethod
    def stop_now(
        db: Session,
        device_id: str,
    ):
        timer = MotorTimerRepository.get_running_timer(
            db,
            device_id,
        )

        if not timer:
            raise MotorNotRunning()

        # ---------------------------------------------------------
        # Manual stop of a timer remains a timer-originated stop.
        # ---------------------------------------------------------
        MQTTService.publish_motor_command(
            device_uid=device_id,
            action="OFF",
            trigger_type="time",
        )

        MotorTimerRepository.stop_timer(
            db,
            timer,
        )

        logger.info(
            "MOTOR STOPPED MANUALLY => device=%s trigger_type=time",
            device_id,
        )

        return timer