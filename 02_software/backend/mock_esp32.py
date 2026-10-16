import json
import random
import time
import paho.mqtt.client as mqtt

# ============================================================
# Configuration & Constants
# ============================================================

MQTT_BROKER = "broker.hivemq.com"
MQTT_PORT = 1883
MQTT_TOPIC = "smart-irrigation/telemetry"

CLIENT_ID = "mock-esp32-sensor-node-01"
PUBLISH_INTERVAL_SECONDS = 5


# ============================================================
# MQTT Callbacks
# ============================================================

def on_connect(client, userdata, flags, rc, properties=None):
    if rc == 0:
        print(f"[INFO] Connected to MQTT Broker: {MQTT_BROKER}")
    else:
        print(f"[ERROR] MQTT connection failed: {rc}")


def on_disconnect(client, userdata, rc, properties=None):
    print(f"[INFO] Disconnected from MQTT Broker. Code: {rc}")


# ============================================================
# Mock Telemetry Generator
# ============================================================

def generate_mock_sensor_data():
    """
    Generate mock telemetry using the agreed JSON schema.
    NPK readings are unavailable and therefore set to None,
    which is serialized as JSON null.
    """

    return {
        "device_id": "esp32-node-01",
        "timestamp": int(time.time()),
        "sensors": {
            "soil_moisture_pct": round(
                random.uniform(25.0, 65.0), 2
            ),
            "soil_temperature_c": round(
                random.uniform(20.0, 38.0), 2
            ),
            "soil_ph": round(
                random.uniform(6.0, 7.8), 2
            ),
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
        client_id=CLIENT_ID,
        protocol=mqtt.MQTTv5
    )

    client.on_connect = on_connect
    client.on_disconnect = on_disconnect

    print(
        f"[INFO] Connecting to "
        f"{MQTT_BROKER}:{MQTT_PORT}..."
    )

    try:
        client.connect(
            MQTT_BROKER,
            MQTT_PORT,
            keepalive=60
        )
    except Exception as e:
        print(f"[ERROR] Could not connect to broker: {e}")
        return

    client.loop_start()

    print(
        f"[INFO] Mock ESP32 started. "
        f"Publishing to '{MQTT_TOPIC}' "
        f"every {PUBLISH_INTERVAL_SECONDS} seconds."
    )

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
                print(
                    f"[ERROR] Publish failed. "
                    f"Code: {result.rc}"
                )

            time.sleep(PUBLISH_INTERVAL_SECONDS)

    except KeyboardInterrupt:
        print("\n[INFO] Stopping Mock ESP32 publisher...")

    finally:
        client.disconnect()
        client.loop_stop()
        print("[INFO] Publisher stopped.")


if __name__ == "__main__":
    run_mock_esp32()
    
