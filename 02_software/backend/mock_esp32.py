
import json
import random
import time
from pathlib import Path

import paho.mqtt.client as mqtt
from dotenv import load_dotenv
import os


# ============================================================
# Configuration
# ============================================================

BACKEND_DIR = Path(__file__).resolve().parent
ENV_FILE = BACKEND_DIR / ".env.example"

# Load MQTT configuration
load_dotenv(ENV_FILE)

MQTT_BROKER = os.getenv("MQTT_BROKER", "broker.hivemq.com")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_USERNAME = os.getenv("MQTT_USERNAME", "")
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD", "")
MQTT_TOPIC = os.getenv(
    "MQTT_TELEMETRY_TOPIC",
    "smart-irrigation/telemetry"
)

CLIENT_ID = "mock-esp32-sensor-node-01"
PUBLISH_INTERVAL_SECONDS = 5


# ============================================================
# MQTT Callbacks
# ============================================================

def on_connect(client, userdata, flags, reason_code, properties=None):
    if reason_code == 0:
        print(f"[INFO] Connected to MQTT Broker: {MQTT_BROKER}")
        print(f"[INFO] Telemetry topic: {MQTT_TOPIC}")
    else:
        print(f"[ERROR] MQTT connection failed: {reason_code}")


def on_disconnect(client, userdata, disconnect_flags, reason_code, properties=None):
    print(f"[INFO] Disconnected from MQTT Broker. Code: {reason_code}")


# ============================================================
# Mock Telemetry Generator
# ============================================================

def generate_mock_sensor_data():
    """Generate simulated telemetry using the agreed JSON structure."""

    return {
        "device_id": "esp32-node-01",
        "timestamp": int(time.time()),
        "sensors": {
            "soil_moisture_pct": round(random.uniform(25.0, 65.0), 2),
            "soil_temperature_c": round(random.uniform(20.0, 38.0), 2),
            "soil_ph": round(random.uniform(6.0, 7.8), 2),
            "nitrogen_mg_kg": None,
            "phosphorus_mg_kg": None,
            "potassium_mg_kg": None
        },
        "actuators": {
            "pump_state": False
        }
    }


# ============================================================
# Main Publisher Loop
# ============================================================

def run_mock_esp32():
    client = mqtt.Client(
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        client_id=CLIENT_ID,
        protocol=mqtt.MQTTv5
    )

    # Apply credentials only when both are configured.
    if MQTT_USERNAME and MQTT_PASSWORD:
        client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)

    client.on_connect = on_connect
    client.on_disconnect = on_disconnect

    print(f"[INFO] Connecting to {MQTT_BROKER}:{MQTT_PORT}...")

    try:
        client.connect(MQTT_BROKER, MQTT_PORT, keepalive=60)
    except (OSError, ValueError) as exc:
        print(f"[ERROR] Could not connect to broker: {exc}")
        return

    client.loop_start()

    try:
        while True:
            payload = generate_mock_sensor_data()
            payload_str = json.dumps(payload)

            result = client.publish(
                MQTT_TOPIC,
                payload_str,
                qos=1
            )

            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                print(f"[PUBLISHED] {payload_str}")
            else:
                print(f"[ERROR] Publish failed. Code: {result.rc}")

            time.sleep(PUBLISH_INTERVAL_SECONDS)

    except KeyboardInterrupt:
        print("\n[INFO] Stopping Mock ESP32 publisher...")

    finally:
        client.disconnect()
        client.loop_stop()
        print("[INFO] Publisher stopped.")


if __name__ == "__main__":
    run_mock_esp32()
