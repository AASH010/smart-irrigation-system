import json
import random
import time
from datetime import datetime
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
        print(f"Connected to MQTT Broker successfully! (Code: {rc})")
    else:
        print(f"Failed to connect, return code {rc}")


def on_disconnect(client, userdata, rc, properties=None):
    print(f"Disconnected from MQTT Broker (Code: {rc}). Reconnecting...")


# ============================================================
# Mock Data Generator
# ============================================================

def generate_mock_sensor_data():
    """
    Generate logical simulated sensor readings for soil moisture, 
    temperature, pH, and null NPK values.
    """
    return {
        "device_id": "esp32-node-01",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "soil_moisture_percent": round(random.uniform(25.0, 65.0), 2),
        "temperature_celsius": round(random.uniform(20.0, 38.0), 2),
        "ph_level": round(random.uniform(6.0, 7.8), 2),
        "npk": {
            "nitrogen": None,
            "phosphorus": None,
            "potassium": None
        }
    }


# ============================================================
# Main Publisher Loop
# ============================================================

def run_mock_esp32():
    
    # Initialize MQTT Client with v5 protocol
    client = mqtt.Client(
        client_id=CLIENT_ID, 
        protocol=mqtt.MQTTv5
    )
    
    client.on_connect = on_connect
    client.on_disconnect = on_disconnect

    print(f"Connecting to broker {MQTT_BROKER}:{MQTT_PORT}...")
    
    try:
        client.connect(MQTT_BROKER, MQTT_PORT, keepalive=60)
    except Exception as e:
        print(f"Critical error: Could not connect to broker: {e}")
        return

    # Start network loop in background
    client.loop_start()

    print(
        f"Mock ESP32 Publisher started. "
        f"Publishing to topic: '{MQTT_TOPIC}' "
        f"every {PUBLISH_INTERVAL_SECONDS} seconds..."
    )

    try:
        while True:
            payload = generate_mock_sensor_data()
            payload_str = json.dumps(payload)
            
            # Publish telemetry message
            result = client.publish(MQTT_TOPIC, payload_str, qos=1)
            
            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                print(f"Published -> {payload_str}")
            else:
                print(f"Failed to publish message. Error code: {result.rc}")
            
            time.sleep(PUBLISH_INTERVAL_SECONDS)

    except KeyboardInterrupt:
        print("\nStopping Mock ESP32 publisher gracefully...")
        client.loop_stop()
        client.disconnect()
        print("Disconnected. Exiting program.")


if __name__ == "__main__":
    run_mock_esp32()
