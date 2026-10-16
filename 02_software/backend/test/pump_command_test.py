
import json
import os
from pathlib import Path

import paho.mqtt.client as mqtt
from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent

env_file = BACKEND_DIR / ".env"
env_example = BACKEND_DIR / ".env.example"

load_dotenv(env_file if env_file.exists() else env_example)

BROKER = os.getenv("MQTT_BROKER", "broker.hivemq.com")
PORT = int(os.getenv("MQTT_PORT", "1883"))
USERNAME = os.getenv("MQTT_USERNAME", "").strip()
PASSWORD = os.getenv("MQTT_PASSWORD", "")

PUMP_TOPIC = os.getenv(
    "MQTT_PUMP_TOPIC",
    "smart-irrigation/actuators/pump"
)


def on_connect(client, userdata, flags, reason_code, properties):
    if reason_code == 0:
        print(f"[CONNECTED] {BROKER}:{PORT}")
        result, _ = client.subscribe(PUMP_TOPIC, qos=1)

        if result == mqtt.MQTT_ERR_SUCCESS:
            print(f"[LISTENING] {PUMP_TOPIC}")
        else:
            print(f"[ERROR] Subscribe failed: {result}")
    else:
        print(f"[ERROR] Connection failed: {reason_code}")


def on_message(client, userdata, msg):
    try:
        data = json.loads(msg.payload.decode("utf-8"))

        if not isinstance(data, dict):
            print("[INVALID] JSON must be an object.")
            return

        state = data.get("pump_state")

        if not isinstance(state, bool):
            print("[INVALID] pump_state must be true or false.")
            return

        status = "ON" if state else "OFF"
        print(f"[RECEIVED] Pump command: {status}")
        print(f"[TOPIC] {msg.topic}")

    except (UnicodeDecodeError, json.JSONDecodeError):
        print("[INVALID] Message is not valid JSON.")


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