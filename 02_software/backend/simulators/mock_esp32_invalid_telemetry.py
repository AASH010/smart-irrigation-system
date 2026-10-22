
import json
import random
import time
import uuid
from datetime import datetime, timezone

import paho.mqtt.client as mqtt


# MQTT Configuration
BROKER = "broker.hivemq.com"
PORT = 1883
TOPIC = "smart-irrigation/telemetry"

DEVICE_ID = "ESP32-MOCK-INVALID"
INTERVAL_SECONDS = 2


def valid_payload():
    """
    Legacy flat payload.

    The recovery processor should normalize this known layout
    into sensors/actuators and convert the ISO timestamp.
    """
    return {
        "device_id": DEVICE_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "soil_moisture_pct": 45.5,
        "soil_temperature_c": 26.0,
        "soil_ph": 6.8,
        "nitrogen_mg_kg": 40.0,
        "phosphorus_mg_kg": 20.0,
        "potassium_mg_kg": 30.0,
        "pump_state": False,
    }


def generate_invalid_payload():
    """Generate a repairable legacy payload or an invalid payload."""

    payload = valid_payload()

    cases = [
        "legacy_valid",
        "missing_field",
        "wrong_type",
        "moisture_out_of_range",
        "temperature_wrong_type",
        "invalid_ph",
        "negative_nutrient",
        "invalid_pump_state",
        "invalid_timestamp",
        "invalid_json",
        "empty_device_id",
    ]

    case = random.choice(cases)

    if case == "legacy_valid":
        # Valid values in the legacy flat layout.
        # Expected result after recovery: saved or duplicate.
        pass

    elif case == "missing_field":
        payload.pop("soil_moisture_pct")

    elif case == "wrong_type":
        payload["soil_moisture_pct"] = "very wet"

    elif case == "moisture_out_of_range":
        payload["soil_moisture_pct"] = random.choice(
            [-10, 150, 999]
        )

    elif case == "temperature_wrong_type":
        payload["soil_temperature_c"] = "hot"

    elif case == "invalid_ph":
        payload["soil_ph"] = random.choice([-1, 20, 100])

    elif case == "negative_nutrient":
        payload["nitrogen_mg_kg"] = -50

    elif case == "invalid_pump_state":
        payload["pump_state"] = "maybe"

    elif case == "invalid_timestamp":
        payload["timestamp"] = "not-a-timestamp"

    elif case == "invalid_json":
        return (
            case,
            '{"device_id": "ESP32-MOCK-INVALID", '
            '"soil_moisture_pct": ',
        )

    elif case == "empty_device_id":
        payload["device_id"] = ""

    return case, json.dumps(
        payload,
        ensure_ascii=False,
        allow_nan=False,
    )


def on_connect(client, userdata, flags, reason_code, properties):
    if reason_code == 0:
        print(f"Connected to MQTT broker: {BROKER}:{PORT}")
        print(f"Publishing test data to: {TOPIC}")
        print("Case 'legacy_valid' tests automatic normalization.")
    else:
        print(f"MQTT connection failed: {reason_code}")


def main():
    client = mqtt.Client(
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        client_id=f"aerosoil-invalid-mock-{uuid.uuid4().hex[:8]}",
        protocol=mqtt.MQTTv311,
    )

    client.on_connect = on_connect

    try:
        client.connect(BROKER, PORT, keepalive=60)
        client.loop_start()

        counter = 0

        while True:
            counter += 1
            case, message = generate_invalid_payload()

            info = client.publish(
                TOPIC,
                message,
                qos=1,
            )

            info.wait_for_publish(timeout=5)

            print(
                f"[{counter}] Case: {case} | "
                f"Published: {message}"
            )

            time.sleep(INTERVAL_SECONDS)

    except KeyboardInterrupt:
        print("\nStopped by user.")

    except Exception as exc:
        print(f"Mock ESP32 error: {exc}")

    finally:
        client.loop_stop()
        client.disconnect()


if __name__ == "__main__":
    main()
