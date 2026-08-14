import json
import time
from typing import Any, Optional

import paho.mqtt.client as mqtt

from app.core.config import settings
from app.core.logger import logger
from app.core.exceptions import AppException


class MQTTService:
    """
    Persistent MQTT publisher for SmartWell.

    Command topic:
        tubewell/{device_uid}/motor

    Supported trigger types:
        app
        physical
        time
        schedule

    MQTT itself does NOT decide the trigger type.
    The caller/backend service must provide it.
    """

    _instance: Optional["MQTTService"] = None

    VALID_TRIGGERS = {
        "app",
        "physical",
        "time",
        "schedule",
    }

    TRIGGER_ALIASES = {
        "timer": "time",
        "mobile": "app",
        "manual": "app",
    }

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False

        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self.broker = settings.MQTT_BROKER
        self.port = int(settings.MQTT_PORT)
        self.keepalive = int(settings.MQTT_KEEPALIVE)

        self.topic_prefix = (
            settings.MQTT_COMMAND_TOPIC_PREFIX
            .strip("/")
        )

        self.client_id = "smartwell-backend-shared-publisher"

        self.client = mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            client_id=self.client_id,
        )

        if settings.MQTT_USERNAME:
            self.client.username_pw_set(
                settings.MQTT_USERNAME,
                settings.MQTT_PASSWORD,
            )

        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect

        self._connected = False

        self._connect_and_start()

        self._initialized = True

    # =========================================================
    # TRIGGER NORMALIZATION
    # =========================================================

    @classmethod
    def normalize_trigger_type(cls, trigger_type: Any) -> str:
        """
        Convert trigger type into the canonical SmartWell value.

        timer    -> time
        mobile   -> app
        manual   -> app
        """

        value = getattr(
            trigger_type,
            "value",
            trigger_type,
        )

        value = str(value or "app").strip().lower()

        value = cls.TRIGGER_ALIASES.get(
            value,
            value,
        )

        if value not in cls.VALID_TRIGGERS:
            raise AppException(
                status_code=400,
                detail=(
                    f"Invalid trigger_type '{value}'. "
                    "Allowed values: app, physical, time, schedule"
                ),
            )

        return value

    # =========================================================
    # MQTT CALLBACKS
    # =========================================================

    def _on_connect(
        self,
        client,
        userdata,
        flags,
        reason_code,
        properties=None,
    ):
        self._connected = True

        logger.info(
            "MQTT CONNECTED | broker=%s:%s | rc=%s",
            self.broker,
            self.port,
            reason_code,
        )

    def _on_disconnect(
        self,
        client,
        userdata,
        disconnect_flags,
        reason_code,
        properties=None,
    ):
        self._connected = False

        logger.warning(
            "MQTT DISCONNECTED | rc=%s",
            reason_code,
        )

    # =========================================================
    # CONNECTION
    # =========================================================

    def _connect_and_start(self):

        try:
            logger.info(
                "Initializing MQTT Publisher | %s:%s",
                self.broker,
                self.port,
            )

            self.client.connect(
                self.broker,
                self.port,
                self.keepalive,
            )

            # Start network thread immediately.
            self.client.loop_start()

            # Wait for CONNECT.
            for _ in range(30):

                if self.client.is_connected():

                    self._connected = True

                    logger.info(
                        "MQTT publisher connection READY"
                    )

                    return

                time.sleep(0.1)

            logger.error(
                "MQTT publisher connection timeout"
            )

        except Exception as exc:

            logger.error(
                "MQTT connection failed: %s",
                exc,
                exc_info=True,
            )

    def _ensure_connected(self):

        if self.client.is_connected():

            self._connected = True

            return

        logger.warning(
            "MQTT connection not ready. Reconnecting..."
        )

        try:

            self.client.loop_start()

            self.client.reconnect()

            for _ in range(30):

                if self.client.is_connected():

                    self._connected = True

                    logger.info(
                        "MQTT reconnect SUCCESS"
                    )

                    return

                time.sleep(0.1)

        except Exception as exc:

            logger.error(
                "MQTT reconnect failed: %s",
                exc,
                exc_info=True,
            )

        raise AppException(
            status_code=502,
            detail="MQTT broker is not connected",
        )

    # =========================================================
    # TOPIC
    # =========================================================

    def command_topic(
        self,
        device_uid: str,
    ) -> str:

        return (
            f"{self.topic_prefix}/"
            f"{device_uid}/motor"
        )

    # =========================================================
    # PUBLIC MOTOR COMMAND
    # =========================================================

    @classmethod
    def publish_motor_command(
        cls,
        device_uid: str,
        action: str,
        trigger_type: str = "app",
    ) -> None:
        """
        Send ON/OFF command.

        Examples:

            MQTTService.publish_motor_command(
                "ESP32_001_TW",
                "ON",
                "app",
            )

            MQTTService.publish_motor_command(
                "ESP32_001_TW",
                "ON",
                "time",
            )

            MQTTService.publish_motor_command(
                "ESP32_001_TW",
                "ON",
                "schedule",
            )

            MQTTService.publish_motor_command(
                "ESP32_001_TW",
                "ON",
                "physical",
            )
        """

        instance = cls()

        action = str(action).strip().upper()

        if action not in {"ON", "OFF"}:
            raise AppException(
                status_code=400,
                detail="Motor action must be ON or OFF",
            )

        trigger = cls.normalize_trigger_type(
            trigger_type
        )

        payload = {
            "command": action,
            "action": action,
            "device_id": device_uid,
            "device_uid": device_uid,
            "trigger_type": trigger,
        }

        logger.info(
            "ROUTING MOTOR COMMAND | "
            "device=%s | action=%s | trigger_type=%s",
            device_uid,
            action,
            trigger,
        )

        instance.publish_command(
            device_uid=device_uid,
            payload=payload,
        )

    # =========================================================
    # LOW LEVEL PUBLISH
    # =========================================================

    def publish_command(
        self,
        device_uid: str,
        payload: dict[str, Any],
    ) -> None:

        self._ensure_connected()

        topic = self.command_topic(device_uid)

        message = json.dumps(payload)

        logger.info(
            "MQTT PUBLISH START | topic=%s | payload=%s",
            topic,
            message,
        )

        try:

            result = self.client.publish(
                topic=topic,
                payload=message,
                qos=1,
                retain=False,
            )

            if result.rc != mqtt.MQTT_ERR_SUCCESS:

                logger.error(
                    "MQTT publish failed | rc=%s",
                    result.rc,
                )

                raise AppException(
                    status_code=502,
                    detail="MQTT publish failed",
                )

            # Wait until Paho sends it.
            result.wait_for_publish(
                timeout=5
            )

            logger.info(
                "MQTT PUBLISH COMPLETE | "
                "topic=%s | mid=%s | payload=%s",
                topic,
                result.mid,
                message,
            )

        except AppException:
            raise

        except Exception as exc:

            logger.error(
                "MQTT publish exception: %s",
                exc,
                exc_info=True,
            )

            raise AppException(
                status_code=502,
                detail="MQTT delivery failed",
            )