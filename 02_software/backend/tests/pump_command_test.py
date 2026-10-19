
import json
import os
from pathlib import Path

import paho.mqtt.client as mqtt
from dotenv import load_dotenv

# Correct path: backend/, not backend/test/
BACKEND_DIR = Path(__file__).resolve().parents[1]
ENV_FILE = BACKEND_DIR / ".env"
EXAMPLE_FILE = BACKEND_DIR / ".env.example"

load_dotenv(ENV_FILE if ENV_FILE.exists() else EXAMPLE_FILE)

BROKER = os.getenv("MQTT_BROKER", "broker.hivemq.com")
PORT = int(os.getenv("MQTT_PORT", "1883"))
USERNAME = os.getenv("MQTT_USERNAME", "").strip()
PASSWORD = os.getenv("MQTT_PASSWORD", "")
TIMEOUT = int(os.getenv("MQTT_TIMEOUT", "10"))

PUMP_TOPIC = os.getenv(
    "MQTT_PUMP_TOPIC",
    "smart-irrigation/actuators/pump",
)


def on_connect(client, userdata, flags, reason_code, properties):
    if reason_code.is_failure:
        print(f"[ERROR] Connection failed: {reason_code}")
        return

    print(f"[CONNECTED] {BROKER}:{PORT}")

    result, _ = client.subscribe(PUMP_TOPIC, qos=1)
    if result == mqtt.MQTT_ERR_SUCCESS:
        print(f"[LISTENING] {PUMP_TOPIC}")
    else:
        print(f"[ERROR] Subscribe failed: {result}")


def on_message(client, userdata, msg):
    try:
        data = json.loads(msg.payload.decode("utf-8"))

        if not isinstance(data, dict):
            print("[INVALID] JSON payload must be an object.")
            return

        state = data.get("pump_state")

        # type(...) ensures values such as 0 and 1 are not accepted as Booleans.
        if type(state) is not bool:
            print("[INVALID] pump_state must be true or false.")
            return

        status = "ON" if state else "OFF"
        print(f"[RECEIVED] Pump command: {status}")
        print(f"[TOPIC] {msg.topic}")
        print("[NOTE] Simulation only; no physical pump is controlled.")

    except (UnicodeDecodeError, json.JSONDecodeError):
        print("[INVALID] Message is not valid UTF-8 JSON.")


def on_disconnect(
    client, userdata, disconnect_flags, reason_code, properties
):
    print(f"[DISCONNECTED] Reason: {reason_code}")


def main():
    client = mqtt.Client(
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        client_id="aerosoil-pump-test-receiver",
        protocol=mqtt.MQTTv311,
    )

    if USERNAME:
        client.username_pw_set(USERNAME, PASSWORD or None)

    client.on_connect = on_connect
    client.on_message = on_message
    client.on_disconnect = on_disconnect

    try:
        print(f"[INFO] Connecting to {BROKER}:{PORT}...")
        client.connect(BROKER, PORT, keepalive=60)
        client.loop_forever(retry_first_connection=True)

    except KeyboardInterrupt:
        print("\n[INFO] Pump command test stopped.")
    except (OSError, ValueError, mqtt.MQTTException) as error:
        print(f"[ERROR] MQTT error: {error}")
    finally:
        client.disconnect()


if __name__ == "__main__":
    main()
