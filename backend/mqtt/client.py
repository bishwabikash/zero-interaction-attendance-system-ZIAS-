"""MQTT client bridging ESP32 nodes → Redis events."""

import asyncio
import json
import threading
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import paho.mqtt.client as mqtt
import redis.asyncio as redis

from api.config import settings


class MQTTClient:
    """Paho MQTT client whose sync callbacks marshal work to an asyncio loop."""

    def __init__(self) -> None:
        try:
            self.client = mqtt.Client(
                client_id=f"zias-backend-{datetime.utcnow().timestamp():.0f}",
                callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            )
            self._paho_v2 = True
        except (AttributeError, TypeError):
            self.client = mqtt.Client(client_id=f"zias-backend-{datetime.utcnow().timestamp():.0f}")
            self._paho_v2 = False

        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message
        self.client.on_disconnect = self._on_disconnect

        if settings.MQTT_USERNAME:
            self.client.username_pw_set(settings.MQTT_USERNAME, settings.MQTT_PASSWORD)

        if getattr(settings, "MQTT_TLS", False):
            self.client.tls_set()

        self.connected = False
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._loop_thread: Optional[threading.Thread] = None
        self._redis: Optional[redis.Redis] = None

    def _on_connect(self, client, userdata, flags, reason_code, properties=None):
        rc = reason_code if isinstance(reason_code, int) else getattr(reason_code, "value", 0)
        if rc == 0:
            print(f"[mqtt] connected to {settings.MQTT_BROKER}:{settings.MQTT_PORT}")
            self.connected = True
            for topic in (
                f"{settings.MQTT_TOPIC_PREFIX}/devices/+/sensor",
                f"{settings.MQTT_TOPIC_PREFIX}/mobile/+/beacon",
                f"{settings.MQTT_TOPIC_PREFIX}/devices/+/status",
            ):
                client.subscribe(topic, qos=1)
                print(f"[mqtt] subscribed {topic}")
        else:
            print(f"[mqtt] connection failed rc={rc}")
            self.connected = False

    def _on_disconnect(self, *args, **_kwargs):
        self.connected = False
        print("[mqtt] disconnected; auto-reconnect active")

    def _on_message(self, client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            print(f"[mqtt] bad payload on {msg.topic}: {exc}")
            return

        parts = msg.topic.split("/")
        try:
            device_or_user = parts[2]
        except IndexError:
            return

        if msg.topic.endswith("/sensor"):
            event = self._normalize_sensor(device_or_user, payload)
        elif msg.topic.endswith("/beacon"):
            event = self._normalize_beacon(device_or_user, payload)
        elif msg.topic.endswith("/status"):
            event = self._normalize_status(device_or_user, payload)
        else:
            return

        self._schedule(self._publish_to_redis(event))

    @staticmethod
    def _now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()

    def _normalize_sensor(self, device_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "type": "sensor",
            "device_id": device_id,
            "cluster_id": payload.get("cluster_id"),
            "rfid": payload.get("rfid") or payload.get("id"),
            "event_type": payload.get("event_type", "activated"),
            "sensor_active": bool(payload.get("sensor", True)),
            "device_time_ms": payload.get("timestamp"),
            "received_at": self._now_iso(),
        }

    def _normalize_beacon(self, student_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "type": "ble",
            "student_id": student_id,
            "beacon_uuid": payload.get("beacon_uuid"),
            "rssi": payload.get("rssi"),
            "event_type": payload.get("event_type", "approaching"),
            "location": payload.get("location") or {},
            "app_version": payload.get("app_version", ""),
            "received_at": self._now_iso(),
        }

    def _normalize_status(self, device_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "type": "status",
            "device_id": device_id,
            "status": payload.get("status", "online"),
            "has_rfid": bool(payload.get("has_rfid")),
            "has_pir": bool(payload.get("has_pir")),
            "has_ble": bool(payload.get("has_ble")),
            "has_camera": bool(payload.get("has_camera")),
            "ip": payload.get("ip"),
            "rssi": payload.get("rssi"),
            "firmware_version": payload.get("firmware_version"),
            "received_at": self._now_iso(),
        }

    def _schedule(self, coro):
        if self._loop and self._loop.is_running():
            asyncio.run_coroutine_threadsafe(coro, self._loop)
        else:
            print("[mqtt] no asyncio loop, event dropped")

    async def _publish_to_redis(self, event: Dict[str, Any]) -> None:
        if self._redis is None:
            self._redis = redis.from_url(settings.REDIS_URL)
        payload = json.dumps(event, default=str)
        try:
            await self._redis.publish("zias:events", payload)
            key = f"zias:state:{event.get('device_id') or event.get('student_id') or 'unknown'}"
            await self._redis.set(key, payload, ex=settings.ATTENDANCE_WINDOW_SECONDS)
        except Exception as exc:
            print(f"[mqtt] redis publish failed: {exc}")

    def _run_loop(self) -> None:
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_forever()
        finally:
            self._loop.close()

    def publish(self, topic: str, payload: Dict[str, Any], qos: int = 1) -> None:
        self.client.publish(
            f"{settings.MQTT_TOPIC_PREFIX}/{topic}",
            json.dumps(payload, default=str),
            qos=qos,
        )

    def start(self) -> None:
        if not self._loop_thread:
            self._loop_thread = threading.Thread(target=self._run_loop, daemon=True, name="mqtt-loop")
            self._loop_thread.start()

        try:
            self.client.connect(settings.MQTT_BROKER, settings.MQTT_PORT, keepalive=30)
            self.client.loop_start()
            print("[mqtt] client started")
        except Exception as exc:
            print(f"[mqtt] failed to start: {exc}")

    def stop(self) -> None:
        try:
            self.client.loop_stop()
            self.client.disconnect()
        finally:
            if self._loop and self._loop.is_running():
                self._loop.call_soon_threadsafe(self._loop.stop)
        print("[mqtt] client stopped")

    def is_connected(self) -> bool:
        return self.connected


mqtt_client = MQTTClient()
