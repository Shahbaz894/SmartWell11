import json
import re
from typing import Optional
import paho.mqtt.client as mqtt

from app.core.config import settings
from app.core.logger import logger
from app.db.session import SessionLocal
from app.services.motor_telemetry_service import MotorTelemetryService


class MQTTTelemetryConsumerService:

    def __init__(self):
        self.host = settings.MQTT_BROKER
        self.port = int(settings.MQTT_PORT)

        # Initialize Paho MQTT client with backward compatibility
        self.client = mqtt.Client(
            client_id=settings.MQTT_CLIENT_ID,
            callback_api_version=mqtt.CallbackAPIVersion.VERSION1,
        )

        # Configure authentication if credentials are provided in settings
        if getattr(settings, "MQTT_USER", None) and getattr(settings, "MQTT_PASSWORD", None):
            self.client.username_pw_set(settings.MQTT_USER, settings.MQTT_PASSWORD)

        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.telemetry_service = MotorTelemetryService()
        logger.info(f"DEBUG: Initializing MQTT Consumer to {self.host}:{self.port}")

    def start(self):
        """Starts the asynchronous MQTT loop listener."""
        try:
            logger.info(f"DEBUG: Connecting to MQTT broker at {self.host}:{self.port}...")
            self.client.connect(
                self.host,
                self.port,
                keepalive=int(getattr(settings, "MQTT_KEEPALIVE", 60)),
            )
            self.client.loop_start()
            logger.info("DEBUG: MQTT consumer loop_start() initiated successfully.")
        except Exception as e:
            logger.error(f"CRITICAL: Failed to start MQTT Consumer: {str(e)}")

    def _extract_device_id(self, topic: str) -> Optional[str]:
        """
        Dynamically extracts device_uid from incoming telemetry topic.
        Expected topic pattern: PREFIX/device_uid/SUFFIX (e.g., tubewell/ESP32_001_TW/telemetry)
        """
        prefix = getattr(settings, "MQTT_TELEMETRY_TOPIC_PREFIX", "tubewell")
        suffix = getattr(settings, "MQTT_TELEMETRY_TOPIC_SUFFIX", "telemetry")

        pattern = f"^{prefix}/([^/]+)/{suffix}$"
        match = re.match(pattern, topic)

        if match:
            return match.group(1)

        logger.warning(f"⚠️ Topic pattern mismatch: {topic} (Expected pattern: {pattern})")
        return None

    def on_connect(self, client, userdata, flags, rc):
        """Callback invoked upon connection to Mosquitto broker."""
        if rc == 0:
            prefix = getattr(settings, "MQTT_TELEMETRY_TOPIC_PREFIX", "tubewell")
            suffix = getattr(settings, "MQTT_TELEMETRY_TOPIC_SUFFIX", "telemetry")
            subscribe_topic = f"{prefix}/+/{suffix}"

            client.subscribe(subscribe_topic, qos=0)
            logger.info(f"DEBUG: Connected to MQTT broker. Subscribed to '{subscribe_topic}'")
        else:
            logger.error(f"DEBUG: MQTT Connection failed with return code {rc}")

    def on_message(self, client, userdata, msg):
        """Callback invoked when a message is received from ESP32 hardware."""
        try:
            # 1. Extract physical device_uid
            device_uid = self._extract_device_id(msg.topic)
            if not device_uid:
                return

            payload_str = msg.payload.decode("utf-8").strip()
            logger.info(f"📥 MQTT Message Received | topic={msg.topic} | device_uid={device_uid}")

            # 2. Parse JSON payload
            payload = json.loads(payload_str)

            # 3. Context-managed database session to prevent connection leaks
            with SessionLocal() as db:
                telemetry = self.telemetry_service.create_telemetry_from_mqtt(
                    db=db,
                    device_uid=device_uid,
                    payload=payload,
                )
                logger.info(f"✅ Telemetry successfully stored for device: {device_uid}")

        except json.JSONDecodeError as json_err:
            logger.error(f"❌ Malformed JSON payload received on topic {msg.topic}: {json_err}")
        except Exception as exc:
            logger.error(f"❌ Error processing MQTT telemetry message: {exc}", exc_info=True)

    def stop(self):
        """Gracefully disconnects and stops the MQTT loop."""
        logger.info("Stopping MQTT Consumer...")
        self.client.loop_stop()
        self.client.disconnect()