
"""MQTT scenario simulator for the AeroSoil telemetry pipeline.

Run from the backend directory:
    python simulators/mqtt_scenario_simulator.py --scenario valid
    python simulators/mqtt_scenario_simulator.py --scenario duplicate
    python simulators/mqtt_scenario_simulator.py --scenario repairable
    python simulators/mqtt_scenario_simulator.py --scenario irreparable
    python simulators/mqtt_scenario_simulator.py --scenario burst --count 100
"""

import argparse
import json
import os
import time
import uuid
from datetime import datetime, timezone

import paho.mqtt.client as mqtt
from dotenv import load_dotenv

load_dotenv()

BROKER = os.getenv("MQTT_BROKER", "broker.hivemq.com")
PORT = int(os.getenv("MQTT_PORT", "1883"))
USERNAME = os.getenv("MQTT_USERNAME") or None
PASSWORD = os.getenv("MQTT_PASSWORD") or None
TOPIC = os.getenv(
    "MQTT_TOPIC",
    os.getenv("MQTT_TELEMETRY_TOPIC", "smart-irrigation/telemetry"),
)


def valid_payload(device_id=None, timestamp=None):
    """Return a payload matching the strict Telemetry model."""
    return {
        "device_id": device_id or f"ESP32-SIM-{uuid.uuid4().hex[:8]}",
        "timestamp": timestamp or int(datetime.now(timezone.utc).timestamp()),
        "sensors": {
            "soil_moisture_pct": 45.5,
            "soil_temperature_c": 26.0,
            "soil_ph": 6.8,
            "nitrogen_mg_kg": 40.0,
            "phosphorus_mg_kg": 20.0,
            "potassium_mg_kg": 30.0,
        },
        "actuators": {
            "pump_state": False,
        },
    }


def build_scenario(name, count=10):
    """Build messages for the requested scenario."""
    if name == "valid":
        return [valid_payload()]

    if name == "repairable":
        payload = valid_payload()
        payload["deviceId"] = payload.pop("device_id")
        return [payload]

    if name == "irreparable":
        payload = valid_payload()
        payload["sensors"].pop("soil_moisture_pct")
        return [payload]

    if name == "duplicate":
        # Same identity, timestamp and readings in both messages.
        payload = valid_payload(
            device_id=f"ESP32-DUP-{uuid.uuid4().hex[:8]}",
            timestamp=int(datetime.now(timezone.utc).timestamp()),
        )
        return [payload, dict(payload)]

    if name == "malformed":
        return ['{"device_id": ']

    if name == "burst":
        base_timestamp = int(datetime.now(timezone.utc).timestamp())
        return [
            valid_payload(
                device_id=f"ESP32-BURST-{uuid.uuid4().hex[:8]}",
                timestamp=base_timestamp + index,
            )
            for index in range(count)
        ]

    raise ValueError(f"Unknown scenario: {name}")


def publish_scenario(scenario, count=10, delay=0.1):
    """Connect and publish all messages in the selected scenario."""
    client = mqtt.Client(
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        client_id=f"aerosoil-simulator-{uuid.uuid4().hex[:8]}",
    )

    if USERNAME:
        client.username_pw_set(USERNAME, PASSWORD)

    try:
        print(f"[SIM] Connecting to {BROKER}:{PORT}")
        client.connect(BROKER, PORT, keepalive=60)
        client.loop_start()

        if not client.is_connected():
            # Allow a short period for the MQTT connection handshake.
            deadline = time.monotonic() + 10
            while not client.is_connected() and time.monotonic() < deadline:
                time.sleep(0.1)

        if not client.is_connected():
            raise ConnectionError("MQTT connection was not established.")

        messages = build_scenario(scenario, count=count)

        for index, payload in enumerate(messages, start=1):
            if isinstance(payload, str):
                wire_payload = payload
            else:
                wire_payload = json.dumps(
                    payload,
                    separators=(",", ":"),
                    allow_nan=False,
                )

            info = client.publish(TOPIC, wire_payload, qos=1)
            info.wait_for_publish(timeout=10)

            if not info.is_published():
                raise TimeoutError(
                    f"Publish did not complete for message {index}."
                )

            print(
                f"[SIM] Published {index}/{len(messages)} "
                f"to {TOPIC}: {wire_payload}"
            )
            time.sleep(delay)

        print(f"[SIM] Scenario '{scenario}' completed.")

    finally:
        try:
            client.loop_stop()
        finally:
            client.disconnect()


def main():
    parser = argparse.ArgumentParser(
        description="AeroSoil MQTT telemetry scenario simulator"
    )
    parser.add_argument(
        "--scenario",
        choices=[
            "valid",
            "repairable",
            "irreparable",
            "duplicate",
            "malformed",
            "burst",
        ],
        default="valid",
    )
    parser.add_argument("--count", type=int, default=10)
    parser.add_argument("--delay", type=float, default=0.1)
    args = parser.parse_args()

    if args.count < 1:
        parser.error("--count must be at least 1.")
    if args.delay < 0:
        parser.error("--delay cannot be negative.")

    publish_scenario(args.scenario, args.count, args.delay)


if __name__ == "__main__":
    main()
