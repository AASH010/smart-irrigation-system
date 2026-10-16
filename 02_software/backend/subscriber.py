
import json
import os
import time
from pathlib import Path

import paho.mqtt.client as mqtt
from dotenv import load_dotenv


# ============================================================
# Configuration
# ============================================================

BACKEND_DIR = Path(__file__).resolve().parent

# Prefer a local .env file; fall back to .env.example.
ENV_FILE = BACKEND_DIR / ".env"
ENV_EXAMPLE_FILE = BACKEND_DIR / ".env.example"

if ENV_FILE.exists():
    load_dotenv(ENV_FILE)
else:
    load_dotenv(ENV_EXAMPLE_FILE)

BROKER = os.getenv("MQTT_BROKER", "broker.hivemq.com")
PORT = int(os.getenv("MQTT_PORT", "1883"))
USERNAME = os.getenv("MQTT_USERNAME", "").strip()
PASSWORD = os.getenv("MQTT_PASSWORD", "")
TIMEOUT = float(os.getenv("MQTT_TIMEOUT", "10"))

TOPIC = os.getenv(
    "MQTT_TELEMETRY_TOPIC",
    "smart-irrigation/telemetry"
)

CLIENT_ID = "aerosoil-backend-subscriber"


# ============================================================
# Telemetry Validation
# ============================================================

REQUIRED_SENSOR_FIELDS = (
    "soil_moisture_pct",
    "soil_temperature_c",
    "soil_ph",
    "nitrogen_mg_kg",
    "phosphorus_mg_kg",
    "potassium_mg_kg",
)

NPK_FIELDS = (
    "nitrogen_mg_kg",
    "phosphorus_mg_kg",
    "potassium_mg_kg",
)


def is_number(value):
    """Accept JSON numbers, but reject booleans and non-finite values."""
    import math

    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
    )


def validate_telemetry(data):
    """Validate the agreed telemetry structure and field types."""

    if not isinstance(data, dict):
        return False, "JSON payload must be an object."

    if not isinstance(data.get("device_id"), str) or not data["device_id"]:
        return False, "'device_id' must be a non-empty string."

    timestamp = data.get("timestamp")
    if (
        not isinstance(timestamp, int)
        or isinstance(timestamp, bool)
        or timestamp < 0
    ):
        return False, "'timestamp' must be a non-negative Unix timestamp in seconds."

    sensors = data.get("sensors")
    if not isinstance(sensors, dict):
        return False, "'sensors' must be an object."

    missing = [
        field for field in REQUIRED_SENSOR_FIELDS
        if field not in sensors
    ]
    if missing:
        return False, f"Missing sensor fields: {', '.join(missing)}."

    for field in (
        "soil_moisture_pct",
        "soil_temperature_c",
        "soil_ph",
    ):
        if not is_number(sensors[field]):
            return False, f"'{field}' must be a numeric value."

    for field in NPK_FIELDS:
        value = sensors[field]
        if value is not None and not is_number(value):
            return False, f"'{field}' must be numeric or JSON null."

    actuators = data.get("actuators")
    if not isinstance(actuators, dict):
        return False, "'actuators' must be an object."

    if not isinstance(actuators.get("pump_state"), bool):
        return False, "'actuators.pump_state' must be a Boolean."

    return True, "Valid telemetry."


# ============================================================
# MQTT Callbacks
# ============================================================

def on_connect(client, userdata, flags, reason_code, properties):
    """Subscribe to telemetry after a successful broker connection."""

    if reason_code == 0:
        print(f"[INFO] Connected to MQTT broker: {BROKER}:{PORT}")

        result, _ = client.subscribe(TOPIC, qos=1)

        if result == mqtt.MQTT_ERR_SUCCESS:
            print(f"[INFO] Subscribed to: {TOPIC}")
        else:
            print(f"[ERROR] Failed to subscribe. Code: {result}")
    else:
        print(f"[ERROR] MQTT connection failed: {reason_code}")


def on_disconnect(client, userdata, disconnect_flags, reason_code, properties):
    """Report disconnection; Paho manages reconnection while its loop runs."""

    print(f"[INFO] Disconnected from MQTT broker. Code: {reason_code}")


def on_message(client, userdata, msg):
    """Decode, validate, and display telemetry safely."""

    try:
        payload = msg.payload.decode("utf-8")
        data = json.loads(payload)

        valid, message = validate_telemetry(data)

        if not valid:
            print(f"\n[INVALID TELEMETRY] {message}")
            print(f"[INFO] Topic: {msg.topic}")
            return

        sensors = data["sensors"]
        actuators = data["actuators"]

        print("\n--- AeroSoil Telemetry ---")
        print(f"Device ID:       {data['device_id']}")
        print(f"Timestamp:       {data['timestamp']} (Unix seconds)")
        print(f"Soil Moisture:   {sensors['soil_moisture_pct']}%")
        print(f"Soil Temperature:{sensors['soil_temperature_c']} °C")
        print(f"Soil pH:         {sensors['soil_ph']}")

        print("\nNPK Readings:")
        print(f"Nitrogen:        {sensors['nitrogen_mg_kg']} mg/kg")
        print(f"Phosphorus:      {sensors['phosphorus_mg_kg']} mg/kg")
        print(f"Potassium:       {sensors['potassium_mg_kg']} mg/kg")

        pump_state = actuators["pump_state"]
        print(f"\nPump State:      {'ON' if pump_state else 'OFF'}")
        print(f"Topic:           {msg.topic}")
        print("--------------------------")

    except UnicodeDecodeError:
        print("[ERROR] Message is not valid UTF-8.")
    except json.JSONDecodeError:
        print("[ERROR] Message does not contain valid JSON.")
    except Exception as error:
        print(f"[ERROR] Failed to process telemetry: {error}")


# ============================================================
# Main Subscriber
# ============================================================

def main():
    client = mqtt.Client(
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        client_id=CLIENT_ID,
        protocol=mqtt.MQTTv311,
    )

    if USERNAME:
        client.username_pw_set(USERNAME, PASSWORD or None)

    client.on_connect = on_connect
    client.on_disconnect = on_disconnect
    client.on_message = on_message

    print(f"[INFO] Connecting to {BROKER}:{PORT}...")
    print(f"[INFO] Telemetry topic: {TOPIC}")

    try:
        client.connect(BROKER, PORT, keepalive=60)
        client.loop_forever(retry_first_connection=True)

    except KeyboardInterrupt:
        print("\n[INFO] Subscriber stopped by user.")

    except (OSError, ValueError, mqtt.MQTTException) as error:
        print(f"[ERROR] MQTT subscriber failed: {error}")

    finally:
        client.disconnect()
        print("[INFO] Subscriber shutdown complete.")


if __name__ == "__main__":
    main()