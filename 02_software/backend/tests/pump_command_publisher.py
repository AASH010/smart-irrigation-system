
import json
import os
import time
import threading
from pathlib import Path

import paho.mqtt.client as mqtt
from dotenv import load_dotenv


# ============================================================
# Configuration
# ============================================================

BACKEND_DIR = Path(__file__).resolve().parents[1]

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

connected = threading.Event()
connection_error = threading.Event()


# ============================================================
# MQTT Callbacks
# ============================================================

def on_connect(client, userdata, flags, reason_code, properties):
    if reason_code == 0:
        connected.set()
        print(f"[CONNECTED] {BROKER}:{PORT}")
        print(f"[READY] Pump topic: {PUMP_TOPIC}")
    else:
        connection_error.set()
        print(f"[ERROR] Connection failed: {reason_code}")


def on_disconnect(client, userdata, disconnect_flags, reason_code, properties):
    connected.clear()
    print(f"[DISCONNECTED] Reason: {reason_code}")


# ============================================================
# Main Publisher
# ============================================================

def main():
    client = mqtt.Client(
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        client_id="aerosoil-pump-test-sender",
        protocol=mqtt.MQTTv311,
    )

    client.on_connect = on_connect
    client.on_disconnect = on_disconnect

    if USERNAME:
        client.username_pw_set(USERNAME, PASSWORD or None)

    try:
        print(f"[INFO] Connecting to {BROKER}:{PORT}...")
        client.connect(BROKER, PORT, keepalive=60)
        client.loop_start()

        deadline = time.monotonic() + 10

        while not connected.is_set() and not connection_error.is_set():
            if time.monotonic() >= deadline:
                print("[ERROR] Connection timed out.")
                return
            time.sleep(0.1)

        if not connected.is_set():
            return

        while True:
            choice = input(
                "\nEnter 1 = Pump ON, 0 = Pump OFF, q = Quit: "
            ).strip().lower()

            if choice == "q":
                break

            if choice not in ("0", "1"):
                print("[ERROR] Enter 1, 0, or q.")
                continue

            payload = json.dumps({
                "pump_state": choice == "1"
            })

            info = client.publish(
                PUMP_TOPIC,
                payload,
                qos=1
            )

            info.wait_for_publish(timeout=10)

            if info.is_published():
                print(f"[PUBLISHED] Topic: {PUMP_TOPIC}")
                print(f"[PAYLOAD] {payload}")
            else:
                print("[ERROR] Publish was not confirmed.")

    except (OSError, ValueError, RuntimeError) as error:
        print(f"[ERROR] MQTT operation failed: {error}")

    except KeyboardInterrupt:
        print("\n[INFO] Publisher stopped.")

    finally:
        client.loop_stop()
        if client.is_connected():
            client.disconnect()
        print("[INFO] Publisher shutdown complete.")


if __name__ == "__main__":
    main()