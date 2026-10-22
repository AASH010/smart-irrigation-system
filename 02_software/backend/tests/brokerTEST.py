
import os
import sys
from pathlib import Path

import paho.mqtt.client as mqtt
from dotenv import load_dotenv

# Locate and load the shared configuration template.
BACKEND_DIR = Path(__file__).resolve().parents[1]
ENV_FILE = BACKEND_DIR / ".env.example"
load_dotenv(dotenv_path=ENV_FILE, override=True)

# Read MQTT settings from .env.example
MQTT_BROKER = os.getenv("MQTT_BROKER")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_TIMEOUT = float(os.getenv("MQTT_TIMEOUT", "10"))

if not MQTT_BROKER:
    print("[ERROR] MQTT_BROKER is missing from .env.example")
    sys.exit(1)

connected = False
connection_error = None


def on_connect(client, userdata, flags, reason_code, properties=None):
    global connected, connection_error

    if reason_code == 0:
        connected = True
        print(f"[SUCCESS] Connected to MQTT Broker: {MQTT_BROKER}")
    else:
        connection_error = f"Connection refused: {reason_code}"
        print(f"[ERROR] {connection_error}")


def main():
    global connection_error

    client = mqtt.Client(
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        client_id="smart_irrigation_broker_test"
    )
    client.on_connect = on_connect

    try:
        client.connect(MQTT_BROKER, MQTT_PORT, keepalive=60)
        client.loop_start()

        if not client.is_connected():
            # Wait for the actual connection callback.
            import time
            deadline = time.monotonic() + MQTT_TIMEOUT

            while not connected and connection_error is None:
                if time.monotonic() >= deadline:
                    print("[ERROR] Connection timed out.")
                    sys.exit(1)

                time.sleep(0.1)

        if not connected:
            sys.exit(1)

    except (OSError, ValueError) as exc:
        print(f"[ERROR] MQTT connection failed: {exc}")
        sys.exit(1)

    finally:
        client.loop_stop()
        client.disconnect()


if __name__ == "__main__":
    main()

# expecited output:
# [SUCCESS] Connected to MQTT Broker: <MQTT_BROKER>