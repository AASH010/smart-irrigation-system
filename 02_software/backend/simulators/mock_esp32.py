
import json
import os
import random
import time
from pathlib import Path

import paho.mqtt.client as mqtt
from dotenv import load_dotenv

# Configuration
BACKEND_DIR = Path(__file__).resolve().parent
ENV_FILE = BACKEND_DIR / ".env"
EXAMPLE_FILE = BACKEND_DIR / ".env.example"

load_dotenv(ENV_FILE if ENV_FILE.exists() else EXAMPLE_FILE)

MQTT_BROKER = os.getenv("MQTT_BROKER", "broker.hivemq.com")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_USERNAME = os.getenv("MQTT_USERNAME", "").strip()
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD", "")
MQTT_TIMEOUT = int(os.getenv("MQTT_TIMEOUT", "10"))

MQTT_TOPIC = os.getenv(
    "MQTT_TELEMETRY_TOPIC",
    "smart-irrigation/telemetry",
)

CLIENT_ID = "mock-esp32-sensor-node-01"
PUBLISH_INTERVAL_SECONDS = 5


def on_connect(client, userdata, flags, reason_code, properties):
    if reason_code.is_failure:
        print(f"[ERROR] MQTT connection failed: {reason_code}")
    else:
        print(f"[CONNECTED] {MQTT_BROKER}:{MQTT_PORT}")
        print(f"[INFO] Publishing to: {MQTT_TOPIC}")


def on_disconnect(
    client, userdata, disconnect_flags, reason_code, properties
):
    print(f"[DISCONNECTED] Reason: {reason_code}")


def generate_mock_sensor_data():
    return {
        "device_id": "esp32_station_01",
        "timestamp": int(time.time()),
        "sensors": {
            "soil_moisture_pct": round(random.uniform(25.0, 65.0), 2),
            "soil_temperature_c": round(random.uniform(20.0, 38.0), 2),
            "soil_ph": round(random.uniform(6.0, 7.8), 2),
            "nitrogen_mg_kg": None,
            "phosphorus_mg_kg": None,
            "potassium_mg_kg": None,
        },
        "actuators": {
            "pump_state": False
        },
    }


def main():
    client = mqtt.Client(
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        client_id=CLIENT_ID,
        protocol=mqtt.MQTTv311,
    )

    if MQTT_USERNAME:
        client.username_pw_set(
            MQTT_USERNAME,
            MQTT_PASSWORD or None,
        )

    client.on_connect = on_connect
    client.on_disconnect = on_disconnect

    try:
        print(f"[INFO] Connecting to {MQTT_BROKER}:{MQTT_PORT}...")
        client.connect(
            MQTT_BROKER,
            MQTT_PORT,
            keepalive=60,
        )
        client.loop_start()

        deadline = time.monotonic() + MQTT_TIMEOUT
        while not client.is_connected() and time.monotonic() < deadline:
            time.sleep(0.1)

        if not client.is_connected():
            raise ConnectionError("MQTT connection timed out")

        print(
            f"[INFO] Mock ESP32 started. "
            f"Interval: {PUBLISH_INTERVAL_SECONDS}s"
        )

        while True:
            payload = json.dumps(generate_mock_sensor_data())
            result = client.publish(MQTT_TOPIC, payload, qos=1)

            if result.rc != mqtt.MQTT_ERR_SUCCESS:
                print(f"[ERROR] Publish failed: {result.rc}")
            else:
                try:
                    result.wait_for_publish(timeout=MQTT_TIMEOUT)
                    if result.is_published():
                        print(f"[PUBLISHED] {payload}")
                    else:
                        print("[WARNING] Publish was not confirmed in time")
                except (ValueError, RuntimeError) as error:
                    print(f"[WARNING] Publish confirmation error: {error}")

            time.sleep(PUBLISH_INTERVAL_SECONDS)

    except KeyboardInterrupt:
        print("\n[INFO] Stopping Mock ESP32...")
    except (OSError, ValueError, ConnectionError, mqtt.MQTTException) as error:
        print(f"[ERROR] MQTT error: {error}")
    finally:
        client.disconnect()
        client.loop_stop()
        print("[INFO] Publisher stopped.")


if __name__ == "__main__":
    main()
